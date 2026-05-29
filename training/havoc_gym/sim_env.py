"""Gymnasium env wrapping a running Gazebo via ROS topics.

Requires spawn.launch.py + autonomous.launch.py up; env publishes on
the mux's cmd_vel_rl slot. Reset teleports the car via the
/world/havoc_sim/set_pose gz service.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional

import gymnasium as gym
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from tf2_msgs.msg import TFMessage

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
    start_sample_half: float = 1.5  # start poses sampled in [-this, +this]^2
    cmd_vel_topic: str = "/cmd_vel_rl"
    gt_pose_topic: str = "/havoc/gt_pose"
    goal_topic: str = "/goal_pose"
    pose_wait_timeout: float = 5.0  # max seconds to wait for first gt_pose
    teleport_settle_timeout: float = 2.0  # post-teleport pose-arrival wait
    gz_world: str = "havoc_sim"
    gz_entity: str = "havoc"


class HavocSimEnv(gym.Env):
    """Continuous-control env: drive to a random point inside the arena."""

    metadata = {"render_modes": []}

    def __init__(self, config: Optional[EnvConfig] = None):
        super().__init__()
        self.cfg = config or EnvConfig()

        if not shutil.which("gz"):
            raise RuntimeError(
                "gz CLI not on PATH — reset() calls /world/<w>/set_pose via "
                "`gz service`. Source ros-jazzy-ros-gz."
            )

        # Continuous Twist action, normalized to [-1, 1] on both axes so
        # the policy doesn't have to learn the physical scale.
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(2,), dtype=np.float32,
        )
        # Unbounded obs space — normalization is the policy's job.
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32,
        )

        # ROS plumbing — started lazily on first reset.
        self._node: Optional[Node] = None
        self._executor: Optional[SingleThreadedExecutor] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._spin_stop = threading.Event()

        # Latest ground-truth TF message. Lock guards reads from step()
        # against the spin thread's writes.
        self._latest_tf: Optional[TFMessage] = None
        self._tf_counter = 0  # increments per arrival; reset()-side waits on it
        self._latest_lock = threading.Lock()

        # Finite-difference velocity tracking.
        self._prev_pose_xy: Optional[np.ndarray] = None
        self._prev_pose_t: Optional[float] = None

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
        self._wait_for_pose()  # make sure the bridge is actually publishing

        # Random start pose inside a smaller sub-arena so the car has
        # room to maneuver from any orientation without immediately
        # hitting a wall.
        start_x, start_y = self.np_random.uniform(
            -self.cfg.start_sample_half, self.cfg.start_sample_half, size=2,
        )
        start_yaw = self.np_random.uniform(-np.pi, np.pi)

        # Stop the car. Without this, residual /cmd_vel from the last
        # episode keeps it driving while we're teleporting and reading
        # the start pose, which corrupts the finite-difference velocity.
        self._cmd_pub.publish(Twist())

        self._gz_set_pose(start_x, start_y, z=0.1, yaw=start_yaw)
        self._wait_for_fresh_pose()  # confirm teleport landed in TF stream

        # Velocity tracker uses Δposition between snapshots — wipe it so
        # the first post-teleport snapshot reports vx=vy=0 instead of
        # "car moved 3 m in one tick" garbage.
        self._prev_pose_xy = None
        self._prev_pose_t = None

        self._goal_xy = self.np_random.uniform(
            -self.cfg.goal_sample_half, self.cfg.goal_sample_half, size=2,
        ).astype(np.float32)
        self._publish_goal(self._goal_xy)

        state = self._snapshot_state()
        self._prev_xy = np.array([state.x, state.y], dtype=np.float32)
        self._steps = 0

        obs = build_observation(state, *self._goal_xy)
        info = {
            "goal": self._goal_xy.tolist(),
            "start_pose": [float(start_x), float(start_y), float(start_yaw)],
        }
        return obs, info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        action = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        twist = Twist()
        twist.linear.x = float(action[0]) * self.cfg.max_linear
        twist.angular.z = float(action[1]) * self.cfg.max_angular
        self._cmd_pub.publish(twist)

        # Real-time stepping. Replacing with gz-service pause/step is
        # what unlocks faster-than-real-time training — separate PR.
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
            TFMessage, self.cfg.gt_pose_topic, self._on_gt_pose, 10,
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

    def _on_gt_pose(self, msg: TFMessage) -> None:
        with self._latest_lock:
            self._latest_tf = msg
            self._tf_counter += 1

    def _wait_for_pose(self) -> None:
        """Block until we've seen at least one TF message (sim is live)."""
        deadline = time.monotonic() + self.cfg.pose_wait_timeout
        while time.monotonic() < deadline:
            with self._latest_lock:
                if self._latest_tf is not None:
                    return
            time.sleep(0.05)
        raise RuntimeError(
            f"No message on {self.cfg.gt_pose_topic} within "
            f"{self.cfg.pose_wait_timeout}s — is the sim running and the "
            "ros_gz_bridge config including the gt_pose entry?"
        )

    def _wait_for_fresh_pose(self) -> None:
        """Wait for a TF message that arrived after this call started.

        Used after teleport so that snapshots return the post-teleport
        pose rather than a buffered stale one.
        """
        with self._latest_lock:
            baseline = self._tf_counter
        deadline = time.monotonic() + self.cfg.teleport_settle_timeout
        while time.monotonic() < deadline:
            with self._latest_lock:
                if self._tf_counter > baseline:
                    return
            time.sleep(0.02)
        raise RuntimeError(
            f"No fresh {self.cfg.gt_pose_topic} message within "
            f"{self.cfg.teleport_settle_timeout}s of teleport"
        )

    def _snapshot_state(self) -> CarState:
        """Read latest ground-truth pose + finite-difference velocity."""
        with self._latest_lock:
            tf = self._latest_tf
        if tf is None or len(tf.transforms) == 0:
            return CarState(0.0, 0.0, 0.0, 0.0, 0.0)

        # transform[0] = havoc model in world frame. The Pose_V ->
        # TFMessage bridge drops gz entity names, but dynamic_pose/info
        # emits the moving entity first, and the bridge preserves order.
        # Empirically verified by teleport-and-readback during PR #24.
        t = tf.transforms[0].transform
        x, y = float(t.translation.x), float(t.translation.y)
        q = t.rotation
        yaw = float(np.arctan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        ))

        now = time.monotonic()
        vx = vy = 0.0
        if self._prev_pose_xy is not None and self._prev_pose_t is not None:
            dt = now - self._prev_pose_t
            if dt > 1e-6:
                vx = (x - float(self._prev_pose_xy[0])) / dt
                vy = (y - float(self._prev_pose_xy[1])) / dt
        self._prev_pose_xy = np.array([x, y], dtype=np.float32)
        self._prev_pose_t = now

        return CarState(x=x, y=y, yaw=yaw, vx=vx, vy=vy)

    def _publish_goal(self, goal_xy: np.ndarray) -> None:
        msg = PoseStamped()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.header.frame_id = "map"
        msg.pose.position.x = float(goal_xy[0])
        msg.pose.position.y = float(goal_xy[1])
        msg.pose.orientation.w = 1.0
        self._goal_pub.publish(msg)

    def _gz_set_pose(self, x: float, y: float, z: float = 0.1,
                     yaw: float = 0.0) -> None:
        """Teleport the entity via /world/<w>/set_pose. Yaw in radians.

        Uses the gz CLI in a subprocess. Slow-ish (~0.5 s) but only runs
        once per episode at reset, so it's not on the hot path. Raises
        if gz reports the request failed.
        """
        qz = float(np.sin(yaw / 2.0))
        qw = float(np.cos(yaw / 2.0))
        req = (
            f'name: "{self.cfg.gz_entity}", '
            f"position: {{x: {x}, y: {y}, z: {z}}}, "
            f"orientation: {{z: {qz}, w: {qw}}}"
        )
        result = subprocess.run(
            [
                "gz", "service",
                "-s", f"/world/{self.cfg.gz_world}/set_pose",
                "--reqtype", "gz.msgs.Pose",
                "--reptype", "gz.msgs.Boolean",
                "--timeout", "1000",
                "--req", req,
            ],
            capture_output=True, text=True, timeout=5.0,
        )
        # gz returns "data: true" on success, "data: false" on failure.
        # Non-zero exit code or "data: false" both mean the teleport
        # didn't land — fail loudly so a bad entity name doesn't
        # silently leave the car wherever it was.
        if result.returncode != 0 or "data: true" not in result.stdout:
            raise RuntimeError(
                f"gz set_pose failed (rc={result.returncode}): "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
