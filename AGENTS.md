# Agent Guidelines for Havoc

## Required Reading

Before starting any work, read:
1. This file (`AGENTS.md`)
2. `README.md` — Architecture overview and repo layout
3. The relevant subsystem README (`mcu/`, `ros/`, or `training/`)

## Repository Structure

Monorepo with three subsystems:

| Directory | Language | Build System |
|-----------|----------|-------------|
| `mcu/` | C | west + CMake (Zephyr) |
| `ros/` | C++ / Python | colcon (ROS 2 Jazzy) |
| `training/` | Python | pip / pyproject.toml |

Use `nix develop` for the dev shell. Do not install toolchains globally.

## Agent Workflow

### Key Rules

- **Never push to main.** Create a branch and open a PR.
- **Nix-first.** All toolchains come from `flake.nix`. If something is missing, add it to the flake.
- **Respect subsystem boundaries.** MCU firmware, ROS packages, and training code are separate concerns. A PR should generally touch one subsystem unless there is a cross-cutting interface change.

### Planning Tasks

1. Read the README and relevant subsystem docs
2. Explore the relevant code area
3. Ask clarifying questions about scope
4. Get user confirmation before implementing

### Implementation Tasks

1. Enter the Nix dev shell
2. Follow existing code patterns
3. Test changes incrementally
4. Update README or subsystem docs if adding new components

## Terminology

- **MCU**: SAM E70 running Zephyr — handles all real-time control
- **Companion**: Linux SBC (Pi 5 or Orin Nano) — handles perception and planning
- **Watchdog**: MCU timer that zeros throttle if the companion stops sending commands
- **micro-ROS**: ROS 2 bridge between MCU (UART/USB-CDC) and companion
