"""Launch teleop_twist_keyboard remapped onto the mux's teleop input.

Intended to run in its own `docker compose exec -it` shell — the keyboard
node needs an interactive TTY of its own. The autonomous.launch.py file
brings up the mux; this one feeds it.

Usage:
  # terminal A
  ros2 launch havoc_bringup autonomous.launch.py policy:=constant

  # terminal B (interactive)
  ros2 launch havoc_bringup teleop.launch.py

Tap any drive key and teleop's `cmd_vel_teleop` outvotes the constant
policy at the mux. Stop tapping, the mux times the teleop source out
(0.5 s in config) and the constant policy resumes.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    teleop = Node(
        package='teleop_twist_keyboard',
        executable='teleop_twist_keyboard',
        name='teleop_twist_keyboard',
        # Default publishes to /cmd_vel; remap to the mux's teleop input.
        remappings=[('/cmd_vel', '/cmd_vel_teleop')],
        # Inherit the launching shell's stdio so the keyboard prompt is
        # visible and key presses reach the node.
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([teleop])
