# training — Havoc ML / RL

Gymnasium environments and (eventually) RL training scripts for the
Havoc autonomous RC car. Standalone Python package — does **not** use
colcon or live under `ros/`. Brought into the ROS docker container via
the `../training:/training` bind mount in `sim/docker-compose.yml`.

## What's here so far

```
training/
├── pyproject.toml           # pip-installable package "havoc_gym"
├── havoc_gym/
│   ├── observation.py       # pure Python — obs builder
│   ├── reward.py            # pure Python — reward function
│   └── sim_env.py           # gymnasium env that wraps Gazebo via ROS
├── scripts/
│   └── verify_env.py        # sanity-check the env end-to-end
└── tests/
    ├── test_observation.py
    └── test_reward.py
```

The pure-Python pieces (observation, reward) are deliberately
sim-agnostic — same functions will be reused by a future Isaac env and
by the inference-side `RLPolicy` when it ships. The thing that's hard
to get right between training and deploy is *consistency* of obs/reward
across contexts; keeping them in pure-Python modules with no ROS or
Gazebo imports makes that consistency a static guarantee.

## Setup

The docker `ros` container ships with `uv` and the bind mount in
place. Inside it:

```bash
docker compose exec ros bash -lc 'cd /training && uv pip install -e .'
```

`UV_SYSTEM_PYTHON=1` + `UV_BREAK_SYSTEM_PACKAGES=1` are baked into the
image, so the install lands in the container's system Python without
a venv (single-purpose container — venv is just noise). Editable
install so iterating on the Python code doesn't need re-install.

## Verify the env contract

You need a running sim + the policy spine bringing up the mux. The
env publishes to `/cmd_vel_rl` (mux RL slot, priority 30):

```bash
# terminal 1: sim
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_description spawn.launch.py'

# terminal 2: mux (no in-launch policy — env owns cmd_vel_rl)
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_bringup autonomous.launch.py policy:=none'

# terminal 3: drive a few episodes of random actions
docker compose exec ros bash -lc \
  'source install/setup.bash && cd /training && python3 scripts/verify_env.py --episodes 3'
```

Expected output: per-episode steps + return + final distance to goal +
termination reason. With `--policy forward`, the car will drive
straight until it crosses the (-4.5, 4.5) arena bound and the episode
terminates with `oob=True`.

## Known v0 limitation

The env **doesn't reset the simulator** between episodes — it only
samples a new goal. The next PR (`gz-service reset for HavocSimEnv`)
will add proper `set_pose` teleport so episode start states are
controlled.

For now, running the second episode of `verify_env.py` lands the car
wherever the previous one ended; expect immediate out-of-bounds
termination on subsequent episodes after the first one drives off the
edge. This is enough to validate the gym contract; not enough to
actually train a policy. That's intentional — train-time reset is its
own PR.

## Run the unit tests

```bash
docker compose exec ros bash -lc 'cd /training && python3 -m pytest tests/ -v'
```

The pure-Python tests don't need a running sim — they verify the
sim-agnostic observation builder and reward function in isolation.

## What's coming

- v0.1: `gz-service`-based sim reset; clean episode boundaries.
- v0.2: SAC training script via Stable-Baselines3.
- v0.3: parallel envs via SubprocVecEnv + per-env `ROS_DOMAIN_ID`.
- v0.4: depth-camera obs (pixels), wider obs space, larger network.
- v0.5: domain randomization for sim-to-real transfer.
