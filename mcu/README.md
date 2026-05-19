# mcu — Zephyr firmware

Real-time firmware for the SAM E70 (Cortex-M7) that handles PWM, encoders,
IMU fusion, the `/cmd_vel` stall watchdog, and manual RC override. See the
top-level README for the split-compute rationale.

Toolchain comes from `flake.nix` — always work inside `nix develop`. The
flake pins Zephyr v4.4.0 and provides `west`, the SDK, CMake, ninja, and
the Zephyr Python env.

## Workspace layout

This directory is a [west](https://docs.zephyrproject.org/latest/develop/west/index.html)
workspace (Zephyr T2 topology):

```
mcu/
├── manifest/west.yml   # the manifest - what to clone (committed)
├── .west/              # workspace marker + local config (gitignored)
├── zephyr/             # Zephyr source, cloned by `west update` (gitignored)
├── modules/            # HALs, libs, samples deps (gitignored)
└── app/                # our applications
```

Only `manifest/west.yml`, the per-app sources, and this README are tracked
in git. Everything else is reproducible from the manifest.

## First-time bootstrap

```bash
nix develop                        # in repo root
cd mcu
west update                        # clones zephyr + imported modules (~2 GB)
west list                          # sanity check
```

The Zephyr revision in `manifest/west.yml` must match `zephyr.url` in the
top-level `flake.nix`. If you bump one, bump the other.

## Building an app (`native_sim`)

Once apps exist under `app/`:

```bash
cd mcu
west build -b native_sim app
west build -t run
```
