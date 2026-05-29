"""Gymnasium env wrapping a running Gazebo via ROS topics.

Requires spawn.launch.py + autonomous.launch.py up; env publishes on
the mux's cmd_vel_rl slot. v0 does not reset the sim — see README.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import gymnasium as gym
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav_msgs.msg import Odometry
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from havoc_gym.observation import OBS_DIM, CarState, build_observation
from havoc_gym.reward import ArenaBounds, step_reward


@dataclass(frozen=True)
class EnvConfig:
    """Tunable knobs. Kept out of __init__ to avoid a 12-arg constructor."""
    dt: float = 0.1                 # seconds per env step
    max_steps: int = 200            # truncation horizon
    max_linear: float = 0.5         # m/s — action[0]=1 maps to this
    max_angular: float = 1.0        # rad/s — action[1]=1 maps to this
    goal_sample_half: float = 3.5   # goals sampled in [-this, +this]^2
    cmd_vel_topic: str = "/cmd_vel_rl"
    odom_topic: str = "/odom"
    goal_topic: str = "/goal_pose"
    odom_wait_timeout: float = 5.0  # max seconds to wait for first /odom


class HavocSimEnv(gym.Env):
    """Continuous-control env: drive to a random point inside the arena."""

    metadata = {"render_modes": []}

    def __init__(self, config: Optional[EnvConfig] = None):
        super().__init__()
        self.cfg = config or EnvConfig()

        # Continuous Twist action, normalized to [-1, 1] for both axes
        # so the policy doesn't have to learn the physical scale.
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(2,), dtype=np.float32,
        )
        # Obs space matches observation.OBS_DIM. Unbounded — the policy
        # is responsible for normalization. Keeps things simple.
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32,
        )

        # ROS plumbing — set up lazily on first reset so multiple envs
        # can be constructed without immediately fighting over rclpy.
        self._node: Optional[Node] = None
        self._executor: Optional[SingleThreadedExecutor] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._spin_stop = threading.Event()

        # Latest sensor data. Lock guards both fields against the spin
        # thread writing while step() reads them.
        self._latest_odom: Optional[Odometry] = None
        self._latest_lock = threading.Lock()

        self._cmd_pub = None
        self._goal_pub = None

        # Episode state
        self._goal_xy = np.zeros(2, dtype=np.float32)
        self._prev_xy = np.zeros(2, dtype=np.float32)
        self._steps = 0

    # ---- gym.Env contract ----

    def reset(self, *, seed: Optional[int] = None,
              options: Optional[dict] = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._ensure_started()

        # New random goal inside the arena. No sim-state reset in v0.
        self._goal_xy = self.np_random.uniform(
            -self.cfg.goal_sample_half, self.cfg.goal_sample_half, size=2,
        ).astype(np.float32)
        self._publish_goal(self._goal_xy)

        # Wait until we've at least seen one /odom, then snapshot the
        # starting position so the first step's progress signal is sane.
        self._wait_for_odom()
        state = self._snapshot_state()
        self._prev_xy = np.array([state.x, state.y], dtype=np.float32)
        self._steps = 0

        obs = build_observation(state, *self._goal_xy)
        return obs, {"goal": self._goal_xy.tolist()}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        # Clip + scale: action in [-1, 1] -> physical Twist values.
        action = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        twist = Twist()
        twist.linear.x = float(action[0]) * self.cfg.max_linear
        twist.angular.z = float(action[1]) * self.cfg.max_angular
        self._cmd_pub.publish(twist)

        # Let the sim advance by one env tick. Blocking-sleep is fine
        # for v0 — the alternative is gz-service step control which is
        # the next PR.
        time.sleep(self.cfg.dt)

        state = self._snapshot_state()
        curr_xy = np.array([state.x, state.y], dtype=np.float32)

        reward, terminated, oob = step_reward(
            self._prev_xy, curr_xy, self._goal_xy, ArenaBounds(),
        )
        terminated = terminated or oob

        self._prev_xy = curr_xy
        self._steps += 1
        truncated = self._steps >= self.cfg.max_steps

        obs = build_observation(state, *self._goal_xy)
        info = {
            "goal": self._goal_xy.tolist(),
            "distance_to_goal": float(np.linalg.norm(self._goal_xy - curr_xy)),
            "out_of_bounds": bool(oob),
        }
        return obs, float(reward), bool(terminated), bool(truncated), info

    def close(self) -> None:
        if self._spin_thread is not None:
            self._spin_stop.set()
            self._spin_thread.join(timeout=2.0)
        if self._executor is not None:
            self._executor.shutdown()
        if self._node is not None:
            self._node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    # ---- internals ----

    def _ensure_started(self) -> None:
        """Idempotent: bring up rclpy + node + pubs/subs + spin thread."""
        if self._node is not None:
            return
        if not rclpy.ok():
            rclpy.init()

        self._node = rclpy.create_node("havoc_gym_env")
        self._cmd_pub = self._node.create_publisher(
            Twist, self.cfg.cmd_vel_topic, 10,
        )
        self._goal_pub = self._node.create_publisher(
            PoseStamped, self.cfg.goal_topic, 1,
        )
        self._node.create_subscription(
            Odometry, self.cfg.odom_topic, self._on_odom, 10,
        )

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_stop.clear()
        self._spin_thread = threading.Thread(
            target=self._spin_loop, name="havoc_gym_env_spin", daemon=True,
        )
        self._spin_thread.start()

    def _spin_loop(self) -> None:
        while not self._spin_stop.is_set():
            self._executor.spin_once(timeout_sec=0.05)

    def _on_odom(self, msg: Odometry) -> None:
        with self._latest_lock:
            self._latest_odom = msg

    def _wait_for_odom(self) -> None:
        deadline = time.monotonic() + self.cfg.odom_wait_timeout
        while time.monotonic() < deadline:
            with self._latest_lock:
                if self._latest_odom is not None:
                    return
            time.sleep(0.05)
        raise RuntimeError(
            f"No message on {self.cfg.odom_topic} within "
            f"{self.cfg.odom_wait_timeout}s — is the sim running?"
        )

    def _snapshot_state(self) -> CarState:
        with self._latest_lock:
            msg = self._latest_odom
        if msg is None:
            # Shouldn't happen after _wait_for_odom, but guards against
            # the rare case where we're mid-shutdown.
            return CarState(0.0, 0.0, 0.0, 0.0, 0.0)
        p = msg.pose.pose.position
        # Yaw from the quaternion. Cheap closed-form since roll/pitch
        # are negligible for a ground robot.
        q = msg.pose.pose.orientation
        yaw = float(np.arctan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        ))
        v = msg.twist.twist.linear
        return CarState(
            x=float(p.x), y=float(p.y), yaw=yaw,
            vx=float(v.x), vy=float(v.y),
        )

    def _publish_goal(self, goal_xy: np.ndarray) -> None:
        msg = PoseStamped()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position.x = float(goal_xy[0])
        msg.pose.position.y = float(goal_xy[1])
        msg.pose.orientation.w = 1.0
        self._goal_pub.publish(msg)
