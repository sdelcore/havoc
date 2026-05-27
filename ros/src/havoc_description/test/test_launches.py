"""Smoke-test every launch file in the package: does `ros2 launch --print`
load it without error? Catches Python syntax / import / parameter
construction errors before they hit a user trying to start the sim.

This is intentionally NOT a full integration test (no Gazebo, no
runtime). For a full E2E test (spawn the sim, verify topics flow), we
would use launch_testing and need xvfb + a long timeout - that lives
elsewhere when we add it.
"""

import shutil
import subprocess

import pytest


LAUNCH_FILES = [
    'spawn.launch.py',
    'circle.launch.py',
    'view.launch.py',
    'slam.launch.py',
]


@pytest.mark.parametrize('launch_file', LAUNCH_FILES)
def test_launch_parses(launch_file):
    """`ros2 launch --print <pkg> <file>` should exit 0 for every launch."""
    assert shutil.which('ros2'), 'ros2 CLI missing - source /opt/ros/jazzy/setup.bash'

    result = subprocess.run(
        ['ros2', 'launch', '--print', 'havoc_description', launch_file],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f'launch parse failed for {launch_file}\n'
        f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'
    )
