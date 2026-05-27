"""End-to-end SLAM integration test.

Launches `slam.launch.py` headless (via xvfb wrapping at the colcon
level), drives the car with a Twist publisher, and verifies that
RTAB-Map produces output (`/map` published, `/info.ref_id` > 0).

Heavy: ~70 s per run. Worth it because it's the only test that
exercises Gazebo + sensors + bridge + RTAB-Map together end-to-end.

Skipped if `xvfb-run` isn't on PATH - the havoc-ros docker image
includes it. On a bare host, `apt install xvfb`.

Process management is by-name pkill rather than process groups - the
xvfb-run + ros2 launch wrapping doesn't keep child PIDs reliably
attached to one group, and stale Gazebo/RTAB-Map processes pollute
subsequent test runs. The kill list below is the complete set of
things slam.launch.py spawns.
"""

import os
import shutil
import signal
import subprocess
import time

import pytest

# Process name fragments to pkill at teardown - everything slam.launch.py
# can spawn, including the xvfb wrapper and its Xvfb child.
TEARDOWN_PROCS = [
    'ros2 launch havoc_description',
    'gz sim',
    'parameter_bridge',
    'rtabmap',
    'rgbd_sync',
    'robot_state_publisher',
    'ros_gz_sim',
    'Xvfb',
    'xvfb-run',
    'topic pub --rate 10 /cmd_vel',
]


def _setup_env():
    """Return a bash command prefix that sources the ROS env.

    COLCON_PREFIX_PATH is set both by `colcon test` (CI) and by
    sourcing a workspace's setup.bash (docker dev container), so it's
    the right discovery mechanism for both. /workspace/install is the
    last-ditch fallback for raw `python3 -m pytest` runs in the dev
    container before the env is sourced.
    """
    candidates = (os.environ.get('COLCON_PREFIX_PATH') or '/workspace/install').split(':')
    workspace = next(
        (p for p in candidates if p and os.path.exists(os.path.join(p, 'setup.bash'))),
        '/workspace/install',
    )
    return f'. /opt/ros/jazzy/setup.bash && . {workspace}/setup.bash'


def _kill_all():
    """SIGKILL every process matching our teardown names. Idempotent."""
    for name in TEARDOWN_PROCS:
        subprocess.run(['pkill', '-9', '-f', name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)  # let zombies reap


@pytest.fixture(scope='module', autouse=True)
def slam_stack():
    if not shutil.which('xvfb-run'):
        pytest.skip('xvfb-run not on PATH (apt install xvfb)')

    # Clean slate in case a previous run left orphans.
    _kill_all()

    # NOTE: NOT passing headless:=true. Gazebo's `-s` server-only mode
    # skips initializing the rendering pipeline, which means the
    # rgbd_camera sensor never produces frames in this docker container.
    # Wrapping in xvfb-run with a virtual display gives Gazebo a screen
    # to render against; no actual GUI window opens, just the server +
    # offscreen sensor rendering. Effectively headless from the user's
    # POV, just not via gz's `-s` flag.
    launch_cmd = (
        'xvfb-run -a --server-args="-screen 0 1024x768x24" '
        f'bash -c "{_setup_env()} && '
        'exec ros2 launch havoc_description slam.launch.py"'
    )
    # IMPORTANT: pipe to a file, not subprocess.PIPE. ros2 launch +
    # rtabmap are very chatty; with PIPE and no reader, the 64 KB pipe
    # buffer fills and the subprocess blocks mid-startup. Tail the log
    # if a test fails - it's at /tmp/slam_e2e.log.
    launch_log = open('/tmp/slam_e2e.log', 'w')
    launch_proc = subprocess.Popen(
        launch_cmd, shell=True,
        stdout=launch_log, stderr=subprocess.STDOUT,
    )

    # Give Gazebo, the bridge, robot_state_publisher, rgbd_sync, and
    # rtabmap time to come up. ~15 s in practice.
    time.sleep(20)

    # Drive the car so SLAM has motion + parallax to consume.
    drive_cmd = (
        f'bash -c "{_setup_env()} && '
        'exec ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist '
        '\'{linear: {x: 0.3}, angular: {z: 0.5}}\'"'
    )
    drive_proc = subprocess.Popen(
        drive_cmd, shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Let it drive long enough for RTAB-Map to add several nodes.
    time.sleep(25)

    yield {'launch': launch_proc, 'drive': drive_proc}

    # Brutal teardown. SIGINT first for grace, then SIGKILL by name.
    try:
        drive_proc.send_signal(signal.SIGINT)
        launch_proc.send_signal(signal.SIGINT)
        time.sleep(2)
    except Exception:
        pass
    _kill_all()


def _topic_check(name, timeout=20):
    """Use ros2 topic info + echo-with-timeout to verify a topic publishes."""
    # First confirm the topic exists.
    info = subprocess.run(
        ['bash', '-c', f'{_setup_env()} && ros2 topic info {name}'],
        capture_output=True, text=True, timeout=10,
    )
    if info.returncode != 0 or 'Publisher count: 0' in info.stdout:
        return False, f'topic {name} has no publisher: {info.stdout}{info.stderr}'

    # Then sample one message. --timeout is per-message wait.
    echo = subprocess.run(
        ['bash', '-c',
         f'{_setup_env()} && timeout {timeout} ros2 topic echo --once {name}'],
        capture_output=True, text=True, timeout=timeout + 5,
    )
    if echo.returncode != 0:
        return False, f'echo {name} failed (rc={echo.returncode}): {echo.stderr[:300]}'
    return True, echo.stdout


def test_map_topic_publishes():
    ok, msg = _topic_check('/map', timeout=30)
    assert ok, msg
    assert 'header' in msg, f'/map message had no header: {msg[:200]}'


def test_rtabmap_graph_has_nodes():
    ok, msg = _topic_check('/info', timeout=10)
    assert ok, msg

    ref_id = None
    for line in msg.splitlines():
        line = line.strip()
        if line.startswith('ref_id:'):
            try:
                ref_id = int(line.split(':', 1)[1].strip())
            except ValueError:
                pass
            break
    assert ref_id is not None, f'no ref_id in /info: {msg[:200]}'
    assert ref_id > 0, f'RTAB-Map graph empty after 25 s driving (ref_id={ref_id})'
