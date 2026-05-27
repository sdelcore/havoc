"""Spawn the car in Gazebo with the bridge + state publisher.

Launch arguments:
  headless (default: false)
    When true, pass -s to gz sim so the Gazebo GUI never opens.
    Sensor rendering still happens (it uses OGRE), so for fully
    display-less environments (CI, headless servers) wrap the whole
    launch in `xvfb-run -a -- ros2 launch ...` — that gives OGRE a
    virtual display without spawning a real window.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

import xacro


def generate_launch_description():
    pkg_desc = get_package_share_directory('havoc_description')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    urdf_xacro = os.path.join(pkg_desc, 'urdf', 'havoc.urdf.xacro')
    bridge_config = os.path.join(pkg_desc, 'config', 'ros_gz_bridge.yaml')
    world_file = os.path.join(pkg_desc, 'worlds', 'havoc_sim.sdf')

    robot_description = xacro.process_file(urdf_xacro).toxml()

    headless_arg = DeclareLaunchArgument(
        'headless', default_value='false',
        description='If true, run gz sim server-only (-s), no GUI window.',
    )

    # When headless=true, the gz_args string becomes "-r -s <world>"
    # so gz sim skips its GUI entirely. Otherwise "-r <world>".
    gz_args = PythonExpression([
        "'-r -s ' if '", LaunchConfiguration('headless'),
        "' == 'true' else '-r '", " + '", world_file, "'",
    ])

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        # havoc_sim.sdf loads the Sensors + IMU systems on top of the
        # usual physics/scene-broadcaster set; required for the URDF's
        # rgbd_camera and imu sensors to publish.
        launch_arguments={'gz_args': gz_args}.items(),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    spawn = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description', '-name', 'havoc', '-z', '0.1'],
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': bridge_config}],
    )

    return LaunchDescription([
        headless_arg, gz_sim, robot_state_publisher, spawn, bridge,
    ])
