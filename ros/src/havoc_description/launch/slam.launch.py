"""RTAB-Map (visual-inertial SLAM) on top of the standard sim.

Includes `spawn.launch.py` (Gazebo + bridge + robot_state_publisher),
then brings up `rtabmap_sync/rgbd_sync` (combines RGB + depth + info
into a single time-aligned RGBDImage message) and `rtabmap_slam/rtabmap`
(the SLAM itself, producing /map and the `map -> odom` TF edge).

Frames used:
  map  ← published by rtabmap (this launch)
  odom ← published by the ackermann plugin (from spawn.launch.py)
  base_footprint ← URDF root
  camera_optical_link ← REP-103 image frame, source of sensor data

Topics consumed:
  /camera/image, /camera/depth_image, /camera/camera_info (RGBD)
  /imu (visual-inertial constraints)
  /odom (wheel odometry from the ackermann plugin)

Typical session:
  # terminal 1
  ros2 launch havoc_description slam.launch.py
  # terminal 2
  ros2 launch havoc_description view.launch.py
  # terminal 3 (drive)
  ros2 run teleop_twist_keyboard teleop_twist_keyboard
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg_desc = get_package_share_directory('havoc_description')

    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_desc, 'launch', 'spawn.launch.py')
        ),
    )

    # rgbd_sync: triples (rgb, depth, camera_info) into a single
    # rtabmap_msgs/RGBDImage on /rgbd_image, time-aligned. RTAB-Map
    # is much happier subscribing to that than the three loose topics.
    rgbd_sync = Node(
        package='rtabmap_sync',
        executable='rgbd_sync',
        name='rgbd_sync',
        output='screen',
        parameters=[{
            'approx_sync': True,
            'use_sim_time': True,
            'queue_size': 10,
        }],
        remappings=[
            ('rgb/image',       '/camera/image'),
            ('depth/image',     '/camera/depth_image'),
            ('rgb/camera_info', '/camera/camera_info'),
        ],
    )

    # rtabmap_slam: the SLAM core. Subscribes to the synced RGBD plus
    # IMU and wheel odometry; produces the map and the map->odom TF.
    rtabmap = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'frame_id': 'base_footprint',
            'odom_frame_id': 'odom',
            'map_frame_id': 'map',
            'subscribe_depth': False,
            'subscribe_rgb':   False,
            'subscribe_rgbd':  True,
            'subscribe_odom_info': False,  # no visual odometry node
            'subscribe_imu':   True,
            'approx_sync':     True,
            'queue_size':      10,
            # Reset DB on each launch so we start mapping fresh. Set to
            # False when we move to localization mode in phase 2.
            'Mem/IncrementalMemory': 'true',
            'database_path':         '/tmp/rtabmap.db',
        }],
        remappings=[
            ('rgbd_image',  '/rgbd_image'),
            ('imu',         '/imu'),
            ('odom',        '/odom'),
        ],
        arguments=['-d'],  # delete DB on launch
    )

    return LaunchDescription([spawn, rgbd_sync, rtabmap])
