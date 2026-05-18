import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

import xacro


def generate_launch_description():
    pkg_desc = get_package_share_directory('havoc_description')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    urdf_xacro = os.path.join(pkg_desc, 'urdf', 'havoc.urdf.xacro')
    bridge_config = os.path.join(pkg_desc, 'config', 'ros_gz_bridge.yaml')

    robot_description = xacro.process_file(urdf_xacro).toxml()

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': '-r empty.sdf'}.items(),
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

    return LaunchDescription([gz_sim, robot_state_publisher, spawn, bridge])
