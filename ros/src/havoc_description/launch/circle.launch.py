import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    pkg_desc = get_package_share_directory('havoc_description')

    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_desc, 'launch', 'spawn.launch.py')
        ),
    )

    # linear.x=0.5 m/s with angular.z=0.5 rad/s gives a circle of radius
    # 1.0 m around the spawn point.
    drive_in_circle = ExecuteProcess(
        cmd=[
            'ros2', 'topic', 'pub', '--rate', '10', '/cmd_vel',
            'geometry_msgs/msg/Twist',
            '{linear: {x: 0.5}, angular: {z: 0.5}}',
        ],
        output='screen',
    )

    # Hold the publisher until Gazebo and the bridge have a moment to
    # come up - otherwise the first few messages drop on the floor.
    delayed_drive = TimerAction(period=5.0, actions=[drive_in_circle])

    return LaunchDescription([spawn, delayed_drive])
