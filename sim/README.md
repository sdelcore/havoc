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

## Build the ROS workspace

The repo's `ros/` directory is bind-mounted at `/workspace` inside the
container, so colcon builds land there and survive container restarts:

```bash
docker compose exec ros bash -lc 'cd /workspace && colcon build --symlink-install'
```

## Spawn the car in Gazebo

```bash
docker compose exec ros bash -lc \
  'cd /workspace && source install/setup.bash && ros2 launch havoc_description spawn.launch.py'
```

This loads `havoc.urdf.xacro`, starts Gazebo with an empty world,
spawns the car, and starts the `ros_gz_bridge` so ROS `/cmd_vel`
messages reach the in-Gazebo ackermann controller.

## Drive in a circle

```bash
docker compose exec ros bash -lc \
  'cd /workspace && source install/setup.bash && ros2 launch havoc_description circle.launch.py'
```

This is `spawn.launch.py` + a delayed `ros2 topic pub` that publishes a
constant `Twist(linear.x=0.5, angular.z=0.5)`, giving roughly a 1 m
radius circle.

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

This directory contains cross-subsystem sim orchestration (the Docker
images and compose file). ROS-side artifacts (URDF, launch files, etc.)
live in `ros/src/havoc_description/` and are bind-mounted into the
container.
