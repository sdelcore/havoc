"""Launch RViz with the sensors layout preloaded.

Separate from spawn.launch.py so headless/CI uses of the sim don't drag
in RViz. Typical use:

    # terminal 1: sim + bridge (headless ok)
    docker compose exec ros bash -lc \\
      'source install/setup.bash && ros2 launch havoc_description spawn.launch.py'
    # terminal 2: RViz (needs X11)
    docker compose exec ros bash -lc \\
      'source install/setup.bash && ros2 launch havoc_description view.launch.py'
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    pkg_desc = get_package_share_directory('havoc_description')

    config_arg = DeclareLaunchArgument(
        'config',
        default_value='sensors.rviz',
        description='Which RViz config to load (e.g. sensors.rviz, slam.rviz).',
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', PathJoinSubstitution([pkg_desc, 'rviz',
                                               LaunchConfiguration('config')])],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    return LaunchDescription([config_arg, rviz])
