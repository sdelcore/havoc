"""Sanity-check that two HavocSimEnv instances stay isolated.

Spawns one env per ROS_DOMAIN_ID, each in its own thread, runs a few
forward-policy episodes concurrently. Prints per-env progress so you
can see them advancing in parallel.

Prereqs (from inside the docker ros container):

  # for each env_id you want to run:
  ros2 launch havoc_description spawn.launch.py env_id:=N &
  ros2 launch havoc_bringup autonomous.launch.py env_id:=N &

Then:
  python3 scripts/verify_parallel.py --env-ids 0 1

The script sets ROS_DOMAIN_ID and GZ_PARTITION per worker thread via
subprocess workers (one Python process per env) so each worker's
rclpy.init binds to the right domain.
"""

import argparse
import multiprocessing as mp
import os
import sys


def _run_one(env_id: int, episodes: int, policy: str) -> None:
    """Body of one env worker. Runs in its own subprocess so each
    process has its own rclpy context bound to its own ROS domain.
    """
    os.environ["ROS_DOMAIN_ID"] = str(env_id)
    os.environ["GZ_PARTITION"] = f"havoc_e{env_id}"

    # Imported here, not at module load, so the env vars are set before
    # rclpy.init runs.
    import gymnasium as gym
    import numpy as np

    import havoc_gym  # noqa: F401 — registers HavocSim-v0

    env = gym.make("HavocSim-v0")
    try:
        for ep in range(episodes):
            obs, info = env.reset()
            ret = 0.0
            for t in range(10_000):
                if policy == "random":
                    action = env.action_space.sample()
                else:
                    action = np.array([0.6, 0.0], dtype=np.float32)
                obs, r, term, trunc, info = env.step(action)
                ret += r
                if term or trunc:
                    break
            print(
                f"[env {env_id}] ep {ep}: steps={t + 1:>3d}  return={ret:>+8.2f}  "
                f"final_dist={info['distance_to_goal']:>5.2f}  "
                f"terminated={term}  truncated={trunc}",
                flush=True,
            )
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-ids", type=int, nargs="+", default=[0, 1],
        help="Which env slots to run. Each needs its own sim+mux already up.",
    )
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument(
        "--policy", choices=["forward", "random"], default="forward",
    )
    args = parser.parse_args()

    # "spawn" start method so each worker gets a fresh interpreter — no
    # rclpy state leakage between workers.
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_run_one, args=(eid, args.episodes, args.policy))
        for eid in args.env_ids
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    if any(p.exitcode != 0 for p in procs):
        sys.exit(1)


if __name__ == "__main__":
    main()
