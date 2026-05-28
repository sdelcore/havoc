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

This loads `havoc.urdf.xacro`, starts Gazebo with the `havoc_sim.sdf`
world (a 10×10 m arena with four walls and a handful of obstacles
for SLAM to chew on), spawns the car, starts `robot_state_publisher`,
and starts the `ros_gz_bridge` so:

- ROS `/cmd_vel` reaches the in-Gazebo ackermann controller (input)
- Gazebo's RGBD camera + IMU output reaches ROS as `/camera/*` + `/imu` (sensors)

## Visualize in RViz

```bash
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_description view.launch.py'
```

Loads `rviz/sensors.rviz` with TF + RobotModel + RGB image + depth
point cloud + IMU axis preconfigured. Run this in a second terminal
alongside `spawn.launch.py`. Needs X11 (see Display forwarding below).

## The policy spine

A *policy* is anything that publishes `geometry_msgs/Twist`. The
`havoc_policies` package defines a `BasePolicy` ABC and concrete
subclasses (currently `ConstantPolicy`; pure pursuit / Nav2 / RL /
explorer to come). Each policy publishes on its own `cmd_vel_<name>`
topic; `twist_mux` arbitrates them by priority and timeout onto the
canonical `/cmd_vel`. Priorities (in `havoc_policies/config/twist_mux.yaml`):

| Slot | Priority | Topic | Notes |
|---|---|---|---|
| teleop | 100 | `cmd_vel_teleop` | Human override, always wins |
| nav2 | 50 | `cmd_vel_nav2` | Reserved (no node yet) |
| pure_pursuit | 40 | `cmd_vel_pure_pursuit` | Reserved |
| rl | 30 | `cmd_vel_rl` | Reserved |
| explorer | 20 | `cmd_vel_explorer` | Reserved |
| constant | 10 | `cmd_vel_constant` | Lowest — demo / smoke fixture |

`autonomous.launch.py` always brings up the mux; the `policy` arg picks
which in-launch policy (if any) drives.

## Drive in a circle (via the policy spine)

```bash
# terminal 1: sim
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_description spawn.launch.py'

# terminal 2: policy spine + constant policy
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_bringup autonomous.launch.py \
     policy:=constant linear_speed:=0.5 angular_speed:=0.5'
```

`linear=0.5 angular=0.5` gives roughly a 1 m radius circle. There's
also a legacy `havoc_description/launch/circle.launch.py` (spawn + a
`Timer`-delayed `ros2 topic pub` direct to `/cmd_vel`) that does the
same thing without going through the mux — use it when you want to
isolate the bridge/ackermann path from policy code.

## Drive with the keyboard (via the policy spine)

Three terminals — sim, mux, and keyboard. The mux runs alongside any
other policy you want; keyboard's priority (100) outvotes everything
else for as long as you're tapping keys.

```bash
# terminal 1: sim
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_description spawn.launch.py'

# terminal 2: policy spine (no in-launch policy)
docker compose exec ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_bringup autonomous.launch.py'

# terminal 3: keyboard, remapped onto the mux's teleop input
docker compose exec -it ros bash -lc \
  'source install/setup.bash && ros2 launch havoc_bringup teleop.launch.py'
```

Focus terminal 3 and use `i`/`,` for forward/reverse, `j`/`l` for
left/right, `k` to stop.

You can also drive the keyboard alongside an autonomous policy
(e.g. `policy:=constant` in terminal 2). Stop tapping keys, the mux
times the teleop source out after 0.5 s and falls back to the
autonomous source. That handoff pattern is what makes the spine useful
for safe RL training and evaluation.

## Headless

For CI or display-less machines, wrap the launch in `xvfb-run`:

```bash
docker compose exec ros bash -lc \
  'source install/setup.bash && xvfb-run -a ros2 launch havoc_description spawn.launch.py'
```

`xvfb-run -a` gives OGRE (the renderer Gazebo uses for sensor images)
a virtual display — without it, depth/RGB topics stay silent. No
window actually opens because there's nobody to display to.

There's also a `headless:=true` arg that adds `-s` to `gz sim` (server
only). **Caveat:** `-s` also disables Gazebo's rendering pipeline, so
sensor topics go silent. Only useful if you don't need sensors. For
SLAM/perception work — use the `xvfb-run` recipe above instead.

`view.launch.py` (RViz) intentionally can't run headless — it's a GUI.

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
