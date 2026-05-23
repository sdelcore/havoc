# Havoc

Autonomous 1/10 scale RC car with split compute architecture.

## Architecture

Split compute — Linux can crash, car coasts safely to a stop.

| Layer | Hardware | Role |
|-------|----------|------|
| MCU | SAM E70 (Cortex-M7, Zephyr) | PWM, odometry, IMU, watchdog, manual override |
| Companion | Pi 5 (dev) / Orin Nano (autonomous) | Perception, SLAM, pilot model, ROS 2 |

The steering deadline lives on the M7, not in soft real-time Linux. The MCU zeros throttle
if `/cmd_vel` stalls >200 ms.

## Software Stack

- **RTOS**: Zephyr v4.4 on SAM E70 — firmware does PWM, encoders, IMU,
  manual override, 200 ms `/cmd_vel` stall watchdog. micro-ROS over
  UDP (currently to a docker agent in sim, will be UART/USB-CDC to
  the companion on hardware).
- **ROS 2**: Jazzy. Gazebo Harmonic sim with ackermann plugin,
  RGBD camera, IMU, bridged via `ros_gz_bridge`.
- **Perception**: Intel RealSense D435i → librealsense → ROS 2 topics
  (sim uses Gazebo's RGBD camera plugin in the meantime).
- **SLAM**: RTAB-Map (per the Autonomy Plan; not yet implemented).
- **Pilot model**: TBD (E2E CNN, per the Autonomy Plan).
- **Training**: Desktop GPU (nightman, 4090).

## Repository Layout

```
havoc/
├── mcu/                       # Zephyr firmware for SAM E70 (west/CMake)
├── ros/src/havoc_description/ # ROS 2 robot model + sim launch + world
├── sim/                       # Docker images and compose for sim
├── training/                  # Model training pipeline (Python, TBD)
├── .github/workflows/         # CI: lint + ROS build + Zephyr build
├── flake.nix                  # Nix dev shell
└── AGENTS.md                  # Agent guidelines (CLAUDE.md -> symlink)
```

## Development

```bash
nix develop                 # host shell with west, cmake, ninja
cd sim && docker compose up # ros + zephyr + micro-ros-agent containers
```

See `sim/README.md` for the sim workflow, `mcu/README.md` for firmware
builds.

## Status

**Active development.** Firmware skeleton complete in sim (publisher,
subscriber, stall watchdog, status echo). ROS-side has the ackermann
sim, sensors, and Gazebo test world. SLAM/planning/perception are the
next major chunks of work — see the Autonomy Plan in `~/Obsidian/sdelcore/Projects/Havoc/`.
Hardware build is parts-research phase.

## License

MIT
