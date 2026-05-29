"""Verify HavocSimEnv against a running sim.

Drives N episodes of random actions and prints per-episode return /
length. Purpose is to validate the env contract end-to-end (rclpy
plumbing, obs shape, reward signs, termination) before wiring an
actual RL algorithm in the next PR.

Prereqs (in the docker `ros` container):
  ros2 launch havoc_description spawn.launch.py        # terminal 1
  ros2 launch havoc_bringup autonomous.launch.py       # terminal 2 (no policy — env publishes on cmd_vel_rl)

Then in a separate shell with the training package installed:
  python -m havoc_gym.scripts.verify_env --episodes 3
"""

import argparse

import gymnasium as gym
import numpy as np

import havoc_gym  # noqa: F401 — registers HavocSim-v0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument(
        "--policy", choices=["random", "forward", "spin"], default="random",
        help="Action source. 'forward' constant-forwards; 'spin' rotates.",
    )
    args = parser.parse_args()

    env = gym.make("HavocSim-v0")
    rng = np.random.default_rng(0)

    try:
        for ep in range(args.episodes):
            obs, info = env.reset()
            ret = 0.0
            for t in range(10_000):
                if args.policy == "random":
                    action = env.action_space.sample()
                elif args.policy == "forward":
                    action = np.array([0.6, 0.0], dtype=np.float32)
                else:  # spin
                    action = np.array([0.0, 0.5], dtype=np.float32)
                obs, r, term, trunc, info = env.step(action)
                ret += r
                if term or trunc:
                    break
            print(
                f"ep {ep}: steps={t + 1:>3d}  return={ret:>+8.2f}  "
                f"final_dist={info['distance_to_goal']:>5.2f}  "
                f"terminated={term}  truncated={trunc}  "
                f"oob={info['out_of_bounds']}"
            )
    finally:
        env.close()


if __name__ == "__main__":
    main()
