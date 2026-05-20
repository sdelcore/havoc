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

All builds happen inside the zephyr container:

```bash
docker compose -f sim/docker-compose.yml up -d zephyr
docker compose -f sim/docker-compose.yml exec zephyr bash -lc \
  'cd /workspace && west build -b native_sim app -p'
./mcu/build/zephyr/zephyr.exe                # run on host
```

Expected boot log:

```
*** Booting Zephyr OS build v4.4.0 ***
[00:00:00.000,000] <inf> havoc_mcu: havoc_mcu starting
[00:00:00.000,000] <inf> havoc_mcu: count=0
[00:00:00.110,000] <inf> havoc_mcu: count=1
...
```

The binary statically links `libmicroros.a` and the UDP transport, but
`main.c` doesn't call any micro-ROS APIs yet - proving the link is M3's
scope; publishers / subscribers / executor wiring come in M4+.

`west build -t run` aggressively buffers the run target's stdout (ninja
holds it until the subprocess exits, which Zephyr never does) - run
`zephyr.exe` directly on the host instead.
