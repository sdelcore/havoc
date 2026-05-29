"""SAC training on HavocSimEnv via SubprocVecEnv.

Each subprocess gets its own ROS_DOMAIN_ID and GZ_PARTITION so the N
envs talk to N independent sims (you bring those up separately — see
scripts/launch_parallel_sims.sh). The training loop is plain
Stable-Baselines3 SAC; no fancy tuning, defaults plus a Gymnasium env.

Usage (from inside the docker `ros` container, in a separate shell
after launch_parallel_sims.sh has had ~25 s to come up):

  cd /training && python3 scripts/train.py \
      --n-envs 4 \
      --total-timesteps 200_000 \
      --save-dir models/sac_v1 \
      --tb-dir runs/sac_v1

Watch progress:
  tensorboard --logdir /training/runs

Throughput estimate at dt=0.1: ~10 steps/sec/env. With 4 envs in
parallel, ~40 aggregate steps/sec → 100K steps in ~40 min wall.
Faster-than-real-time training needs gz pause/step in the env, which
is a separate PR.
"""

import argparse
import os
import sys
from pathlib import Path


def make_env(env_id: int):
    """Factory that SubprocVecEnv calls once per subprocess.

    Returns a no-arg callable so SB3 can defer construction. The
    closure captures env_id; the os.environ assignment happens inside
    the subprocess (after `spawn` fork), so each subprocess sees a
    different ROS_DOMAIN_ID / GZ_PARTITION before any rclpy import.
    """
    def _init():
        os.environ["ROS_DOMAIN_ID"] = str(env_id)
        os.environ["GZ_PARTITION"] = f"havoc_e{env_id}"

        # Late imports so the env-var writes above land before anything
        # in the rclpy / havoc_gym stack reads them.
        import gymnasium as gym
        import havoc_gym  # noqa: F401 — registers HavocSim-v0
        return gym.make("HavocSim-v0")
    return _init


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-envs", type=int, default=4,
                        help="Number of parallel sim envs (must each be already up)")
    parser.add_argument("--start-env-id", type=int, default=0,
                        help="First env_id to connect; uses [start, start+n_envs)")
    parser.add_argument("--total-timesteps", type=int, default=200_000)
    parser.add_argument("--save-dir", type=Path, default=Path("models/sac"))
    parser.add_argument("--tb-dir", type=Path, default=Path("runs/sac"))
    parser.add_argument("--checkpoint-freq", type=int, default=10_000,
                        help="Save checkpoint every N env steps (per-env)")
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--buffer-size", type=int, default=200_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--resume", type=Path, default=None,
                        help="Path to a .zip checkpoint to resume from")
    args = parser.parse_args()

    # SB3 imports are heavy; defer until argparse is done so --help is
    # instant and a bad arg fails before the slow import.
    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.vec_env import SubprocVecEnv

    args.save_dir.mkdir(parents=True, exist_ok=True)
    args.tb_dir.mkdir(parents=True, exist_ok=True)

    env_ids = list(range(args.start_env_id, args.start_env_id + args.n_envs))
    print(f"connecting to env_ids: {env_ids}", flush=True)

    # start_method="spawn" so each subprocess starts clean — necessary
    # for the env-var writes in make_env to land before rclpy.init.
    vec_env = SubprocVecEnv(
        [make_env(eid) for eid in env_ids],
        start_method="spawn",
    )

    if args.resume is not None:
        print(f"resuming from {args.resume}", flush=True)
        model = SAC.load(args.resume, env=vec_env, tensorboard_log=str(args.tb_dir))
    else:
        model = SAC(
            "MlpPolicy",
            vec_env,
            learning_rate=args.learning_rate,
            buffer_size=args.buffer_size,
            batch_size=args.batch_size,
            tensorboard_log=str(args.tb_dir),
            seed=args.seed,
            verbose=1,
        )

    # SB3's CheckpointCallback save_freq is in *vec_env steps* (i.e.
    # divided by n_envs internally). Express the arg in per-env steps
    # so behavior is independent of n_envs.
    callback = CheckpointCallback(
        save_freq=max(1, args.checkpoint_freq // args.n_envs),
        save_path=str(args.save_dir),
        name_prefix="sac",
    )

    try:
        model.learn(total_timesteps=args.total_timesteps, callback=callback)
    except KeyboardInterrupt:
        print("interrupted — saving final model", flush=True)

    final_path = args.save_dir / "sac_final.zip"
    model.save(str(final_path))
    print(f"saved final model to {final_path}", flush=True)

    vec_env.close()


if __name__ == "__main__":
    main()
