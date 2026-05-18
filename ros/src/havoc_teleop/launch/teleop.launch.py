import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    pkg_desc = get_package_share_directory('havoc_description')

    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_desc, 'launch', 'spawn.launch.py')
        ),
    )

    # teleop_twist_keyboard is intentionally not launched here - it needs an
    # interactive TTY, so run it from a second `docker compose exec -it` shell.
    return LaunchDescription([spawn])
