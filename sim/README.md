# sim — ROS 2 Jazzy + Gazebo Harmonic in Docker

The simulator runs in Docker rather than directly on NixOS to avoid the
pain of packaging ROS 2 with Nix. On the target Pi this same image is
representative of the production environment (Ubuntu 24.04 + apt ROS 2
Jazzy).

The host only needs `docker` and `docker compose` (already system-level
on NixOS hosts via `virtualisation.docker.enable`).

## Bring it up

From the repo root:

```bash
cd sim
docker compose up -d --build
```

First build pulls `ros:jazzy-ros-base` (~1 GB) and apt-installs
`ros-jazzy-ros-gz`, which brings Gazebo Harmonic and the ros_gz bridge.
Expect 5–10 minutes the first time; subsequent runs are instant.

## Get a shell

```bash
docker compose exec ros bash
```

Sanity checks inside the container:

```bash
ros2 doctor
gz sim --version    # should report Harmonic (8.x)
```

## Display forwarding

The compose file forwards X11 so Gazebo's GUI can open from inside the
container. On NixOS you may need to allow connections from local Docker
clients once per session:

```bash
xhost +local:docker
```

## Tear down

```bash
docker compose down
```

## Scope

This directory contains cross-subsystem sim orchestration. The ROS-side
sim artifacts (Gazebo worlds, URDF, bridge configs) live in
`ros/src/havoc_sim` once that package exists.
