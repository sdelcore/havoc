"""Evaluate a trained SAC checkpoint against a single HavocSimEnv.

Runs N episodes with the policy in deterministic mode and prints
per-episode return + final goal distance, plus aggregate success rate
(fraction of episodes where terminated=True and not out-of-bounds).

Prereqs (in the docker `ros` container):
  ros2 launch havoc_description spawn.launch.py        # terminal 1
  ros2 launch havoc_bringup autonomous.launch.py       # terminal 2

Then:
  cd /training && python3 scripts/eval.py \
      --checkpoint models/sac_v1/sac_final.zip \
      --episodes 10
"""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--env-id", type=int, default=0,
                        help="Which env slot to connect to (default 0)")
    parser.add_argument("--stochastic", action="store_true",
                        help="Sample actions instead of arg-maxing (deterministic=False)")
    args = parser.parse_args()

    import os
    os.environ.setdefault("ROS_DOMAIN_ID", str(args.env_id))
    os.environ.setdefault("GZ_PARTITION", f"havoc_e{args.env_id}")

    import gymnasium as gym
    import numpy as np
    from stable_baselines3 import SAC

    import havoc_gym  # noqa: F401

    env = gym.make("HavocSim-v0")
    model = SAC.load(str(args.checkpoint), env=env)

    returns = []
    lengths = []
    successes = 0
    oob_count = 0

    try:
        for ep in range(args.episodes):
            obs, info = env.reset()
            ret = 0.0
            for t in range(10_000):
                action, _ = model.predict(obs, deterministic=not args.stochastic)
                obs, r, term, trunc, info = env.step(action)
                ret += r
                if term or trunc:
                    break
            # term=True covers both goal-reached AND out-of-bounds in
            # the env's wrapper layer; use info to disambiguate.
            success = term and not info.get("out_of_bounds", False)
            successes += int(success)
            oob_count += int(info.get("out_of_bounds", False))
            returns.append(ret)
            lengths.append(t + 1)
            print(
                f"ep {ep}: steps={t + 1:>3d}  return={ret:>+8.2f}  "
                f"final_dist={info['distance_to_goal']:>5.2f}  "
                f"terminated={term}  truncated={trunc}  oob={info.get('out_of_bounds')}",
                flush=True,
            )
    finally:
        env.close()

    print()
    print(f"episodes:        {args.episodes}")
    print(f"mean return:     {np.mean(returns):>+8.2f} ± {np.std(returns):.2f}")
    print(f"mean length:     {np.mean(lengths):>5.1f} steps")
    print(f"success rate:    {successes}/{args.episodes} ({100 * successes / args.episodes:.0f}%)")
    print(f"oob rate:        {oob_count}/{args.episodes} ({100 * oob_count / args.episodes:.0f}%)")


if __name__ == "__main__":
    main()
