"""Bring up the policy spine: twist_mux + an optional policy executable.

Usage:
  ros2 launch havoc_bringup autonomous.launch.py policy:=constant
  ros2 launch havoc_bringup autonomous.launch.py policy:=constant linear_speed:=0.5 angular_speed:=0.5
  ros2 launch havoc_bringup autonomous.launch.py policy:=none

The mux always comes up. The chosen `policy` executable (from
havoc_policies) is launched alongside it. `policy:=none` brings up only
the mux; useful when you want to drive teleop in a separate terminal,
or test multiple policies one at a time without re-launching the mux.

For teleop, run in a separate `docker compose exec -it` shell:
  ros2 launch havoc_bringup teleop.launch.py
This launches teleop_twist_keyboard remapped to `cmd_vel_teleop`, which
the mux picks up at the highest priority — overriding whatever
autonomous policy is currently driving.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


# Policies bundled with havoc_policies, plus 'none' for mux-only.
KNOWN_POLICIES = ['none', 'constant']


def generate_launch_description():
    twist_mux_yaml = os.path.join(
        get_package_share_directory('havoc_policies'),
        'config', 'twist_mux.yaml',
    )

    policy_arg = DeclareLaunchArgument(
        'policy',
        default_value='none',
        choices=KNOWN_POLICIES,
        description=(
            'Which policy executable to launch alongside the mux. '
            '"none" leaves the mux running with no in-launch policy '
            '(useful when driving teleop in a separate terminal).'
        ),
    )

    # ConstantPolicy params — only used when policy:=constant. Declared
    # at launch level so they're settable from the command line:
    #   ros2 launch ... policy:=constant linear_speed:=0.5
    linear_arg = DeclareLaunchArgument(
        'linear_speed', default_value='0.3',
        description='ConstantPolicy linear velocity (m/s).',
    )
    angular_arg = DeclareLaunchArgument(
        'angular_speed', default_value='0.0',
        description='ConstantPolicy angular velocity (rad/s).',
    )

    twist_mux = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        parameters=[twist_mux_yaml],
        # cmd_vel_out is twist_mux's default output topic; remap to the
        # canonical /cmd_vel that the bridge forwards to Gazebo.
        remappings=[('cmd_vel_out', '/cmd_vel')],
        output='screen',
    )

    constant_policy = Node(
        package='havoc_policies',
        executable='constant',
        name='constant_policy',
        parameters=[{
            'linear_speed': LaunchConfiguration('linear_speed'),
            'angular_speed': LaunchConfiguration('angular_speed'),
        }],
        condition=IfCondition(PythonExpression(
            ["'", LaunchConfiguration('policy'), "' == 'constant'"],
        )),
        output='screen',
    )

    return LaunchDescription([
        policy_arg, linear_arg, angular_arg,
        twist_mux, constant_policy,
    ])
