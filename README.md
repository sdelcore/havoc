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

- **RTOS**: Zephyr on SAM E70
- **ROS 2**: Jazzy via micro-ROS agent (UART/USB-CDC)
- **Perception**: Intel RealSense D435i -> librealsense -> ROS 2 topics
- **SLAM**: TBD
- **Pilot model**: TBD
- **Training**: Desktop GPU (nightman, 4090)

## Repository Layout

```
havoc/
├── mcu/          # Zephyr firmware for SAM E70 (west/CMake)
├── ros/          # ROS 2 packages (colcon)
├── training/     # Model training pipeline (Python)
├── flake.nix     # Nix dev shell
└── AGENTS.md     # Agent guidelines (CLAUDE.md -> symlink)
```

## Development

```bash
nix develop
```

## Status

**Planning** — architecture locked, parts being researched. No code yet.

## License

MIT
