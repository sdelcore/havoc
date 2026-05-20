# mcu — Zephyr firmware

Real-time firmware for the SAM E70 (Cortex-M7) that handles PWM, encoders,
IMU fusion, the `/cmd_vel` stall watchdog, and manual RC override. See the
top-level README for the split-compute rationale.

The flake pins Zephyr **v4.4.0** (latest at time of writing). Upstream
`micro_ros_zephyr_module` officially supports up to v4.1 (issue #158);
we run on v4.4 by patching the relevant header-path and CONFIG_ARCH_POSIX
gaps in our forks of `micro_ros_zephyr_module` and `rcutils`.

## Build environment

Two contexts:

- **`nix develop` (host)** — provides `west`, the Zephyr Python env, and
  basic toolchain. Used for `west init` / `west update` / `west list` and
  general workspace queries.
- **`docker compose exec zephyr` (container)** — `sim/Dockerfile.zephyr`
  layers the Zephyr SDK + colcon + micro-ROS Python deps onto the ROS
  Jazzy base. All actual builds happen here. `nix` is too far from the
  micro-ROS build environment (no colcon-cmake plugin, glibc layout
  mismatches) — fighting that was an early dead end.

## Workspace layout

This directory is a [west](https://docs.zephyrproject.org/latest/develop/west/index.html)
workspace (Zephyr T2 topology):

```
mcu/
├── manifest/west.yml   # the manifest - what to clone (committed)
├── .west/              # workspace marker + local config (gitignored)
├── zephyr/             # Zephyr source, cloned by `west update` (gitignored)
├── modules/            # HALs, libs, micro-ROS fork (gitignored)
└── app/                # our application sources
```

Only `manifest/west.yml`, the per-app sources, and this README are tracked
in git.

## First-time bootstrap

```bash
# In repo root - one-time docker image build:
cd sim && docker compose build zephyr && cd ..

# Clone Zephyr + dependencies into mcu/ (uses host west, ~8 GB of repos):
nix develop --command bash -lc 'cd mcu && west init -l manifest/ && west update'
```

The Zephyr revision in `manifest/west.yml` must match `zephyr.url` in the
top-level `flake.nix`. If you bump one, bump the other.

The manifest also pins **forks** of `micro_ros_zephyr_module` and (via the
module's own makefile) `rcutils`, both at `fix-native-sim` branches.
These forks carry the patches needed for `native_sim` to compile - upstream
only supports cross-compile targets like `disco_l475_iot1`. The patches
live on `sdelcore/micro_ros_zephyr_module` and `sdelcore/rcutils`; we'll
revert to upstream when the issues / PRs land.

## Building the app

```bash
cd sim && docker compose up -d zephyr microros-agent
docker compose exec zephyr bash -lc \
  'cd /workspace && west build -b native_sim/native/64 app -p'
```

The board target is **`native_sim/native/64`**, not plain `native_sim`.
The default native_sim is i686 (-m32), which makes gcc emit
`__x86.get_pc_thunk.bx` thunks that native_sim's link-time
`--gc-sections` discards - a 32-bit-only problem.

## Running end-to-end (publisher + agent + ROS)

`mcu/app/` publishes `std_msgs/Int32` on `/havoc_counter` at 1 Hz via
the micro-ROS UDP transport. The path is:

```
Zephyr binary  --UDP/zeth-->  micro-ROS agent  --DDS-->  ROS 2 graph
```

Two pieces are needed; the third (zeth TAP) is auto-created by the
container's entrypoint:

1. **Agent.** `microros-agent` compose service runs
   `microros/micro-ros-agent:jazzy` and listens on UDP `:8888`.
   `docker compose up -d microros-agent` starts it.

2. **Zephyr binary.**
   ```bash
   docker compose exec zephyr /workspace/build/zephyr/zephyr.exe
   ```
   On boot the binary overrides `default_params.ip = "192.0.2.2"`
   (from `CONFIG_MICROROS_AGENT_IP`) and opens the UDP transport.

The `zeth` TAP interface (192.0.2.0/24, host = 192.0.2.2, Zephyr =
192.0.2.1) is created automatically by `sim/zephyr-entrypoint.sh`
the first time the zephyr container starts. The container has
`NET_ADMIN` + `/dev/net/tun` from the compose file so the script
can call `ip tuntap`.

Verify with `ros2 topic echo` from the ros container:

```bash
docker compose exec ros bash -lc \
  'source /opt/ros/jazzy/setup.bash && ros2 topic echo /havoc_counter'
```

Expected: `data: 0`, `data: 1`, ... at 1 Hz.

`west build -t run` aggressively buffers the run target's stdout (ninja
holds it until the subprocess exits, which Zephyr never does) - run
`zephyr.exe` directly instead.
