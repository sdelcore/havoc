# training — Havoc ML / RL

Standalone Python package (uv, not colcon). Bind-mounted into the
docker `ros` container at `/training` via `sim/docker-compose.yml`.

## Layout

```
training/
├── pyproject.toml
├── havoc_gym/
│   ├── observation.py    # obs builder (no ROS deps)
│   ├── reward.py         # reward fn (no ROS deps)
│   └── sim_env.py        # HavocSimEnv: wraps Gazebo via rclpy
├── scripts/verify_env.py
└── tests/
```

`observation.py` and `reward.py` are kept ROS-free so the same
functions can later back an Isaac env and the inference-side RLPolicy
unchanged — single source of truth for the obs/reward contract.

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

## Reset behavior

`reset()` teleports the car to a random pose inside a 1.5 m sub-arena
and samples a new goal in the 3.5 m goal sub-arena. The teleport uses
the `/world/havoc_sim/set_pose` gz service via the `gz` CLI (slow but
runs once per episode). Ground-truth world pose is read from the
`/havoc/gt_pose` topic — a ros_gz bridge of
`/world/havoc_sim/dynamic_pose/info` (Pose_V → TFMessage). Velocity is
finite-differenced between consecutive pose snapshots; `/odom` isn't
used because the ackermann plugin dead-reckons it and doesn't observe
teleports.

## Parallel envs

Each parallel env needs its own sim, mux, and DDS partition so they
don't share `/cmd_vel` or `/havoc/gt_pose`. The mechanism is two env
vars: `ROS_DOMAIN_ID` (DDS partition for ROS topics) and
`GZ_PARTITION` (gz transport partition for gz services). Both launch
files take an `env_id` arg that sets both:

```bash
ros2 launch havoc_description spawn.launch.py env_id:=1   # sim slot 1
ros2 launch havoc_bringup autonomous.launch.py env_id:=1  # mux slot 1
```

Slot 0 is the regular single-sim case (and the default). For N slots,
use `scripts/launch_parallel_sims.sh`:

```bash
docker compose exec ros bash -lc 'cd /training && ./scripts/launch_parallel_sims.sh 4'
```

The training env reads `ROS_DOMAIN_ID` and `GZ_PARTITION` from its
process environment — no per-env code changes — so when SB3's
`SubprocVecEnv` lands, each subprocess just sets the env vars before
importing `havoc_gym` and the right sim slot is connected
automatically.

To verify parallelism end-to-end:

```bash
# bring up two sim+mux pairs
./scripts/launch_parallel_sims.sh 2
sleep 25
# run two envs concurrently against them
python3 scripts/verify_parallel.py --env-ids 0 1 --policy forward
```

Each env's car drives independently in its own sim.

## Run the unit tests

```bash
docker compose exec ros bash -lc 'cd /training && python3 -m pytest tests/ -v'
```

Sim not required — these test `observation.py` + `reward.py` directly.

## What's coming

- v0.2: SAC training script via Stable-Baselines3 (uses the parallel
  envs shipped here).
- v0.4: depth-camera obs (pixels), wider obs space, larger network.
- v0.5: domain randomization for sim-to-real transfer.
