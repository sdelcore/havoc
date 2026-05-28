"""Smoke-test that every launch file in the package parses.

Same pattern as havoc_description/test/test_launches.py: `ros2 launch
--print` exits 0 only when the launch file is import-clean and the
launch description constructs without error. Catches typos and missing
substitutions before a user hits them.
"""

import shutil
import subprocess

import pytest


LAUNCH_FILES = [
    'autonomous.launch.py',
    'teleop.launch.py',
]


@pytest.mark.parametrize('launch_file', LAUNCH_FILES)
def test_launch_parses(launch_file):
    assert shutil.which('ros2'), 'ros2 CLI missing - source /opt/ros/jazzy/setup.bash'

    result = subprocess.run(
        ['ros2', 'launch', '--print', 'havoc_bringup', launch_file],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f'launch parse failed for {launch_file}\n'
        f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'
    )


def test_autonomous_accepts_constant_policy():
    """`policy:=constant` should parse the conditional Node successfully."""
    result = subprocess.run(
        ['ros2', 'launch', '--print', 'havoc_bringup',
         'autonomous.launch.py', 'policy:=constant'],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f'parse with policy:=constant failed\n'
        f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'
    )
    # The conditional should have evaluated true and the constant node
    # appears in the launch tree.
    assert 'constant' in result.stdout.lower(), \
        f'expected constant policy node in launch tree: {result.stdout[:500]}'
