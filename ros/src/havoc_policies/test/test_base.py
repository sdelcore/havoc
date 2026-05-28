"""Unit tests for BasePolicy.

Verifies the contract: a subclass's compute_action() is called by the
tick timer at the configured rate, and the returned Twist is published
on `cmd_vel_<name>`. None returns are dropped silently (the mux
fallback case).
"""

from typing import Optional

import pytest
import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import SingleThreadedExecutor

from havoc_policies.base import BasePolicy


class _RecordingSubscriber:
    """Helper: subscribes to a Twist topic and records messages."""

    def __init__(self, node, topic):
        self.received = []
        node.create_subscription(Twist, topic, self.received.append, 10)


@pytest.fixture
def rclpy_ctx():
    rclpy.init()
    yield
    rclpy.shutdown()


def _spin_for(executor, seconds, dt=0.01):
    """Pump the executor for `seconds` of wall time."""
    import time
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=dt)


class _ConstantStub(BasePolicy):
    """Minimal subclass that emits a fixed twist for testing."""

    def __init__(self):
        super().__init__('stub', rate_hz=50.0)
        self._x = 0.7

    def compute_action(self) -> Optional[Twist]:
        t = Twist()
        t.linear.x = self._x
        return t


class _SometimesNoneStub(BasePolicy):
    """Emits None on alternating ticks to exercise the silent-drop path."""

    def __init__(self):
        super().__init__('stub_optional', rate_hz=50.0)
        self._toggle = False

    def compute_action(self) -> Optional[Twist]:
        self._toggle = not self._toggle
        if self._toggle:
            t = Twist()
            t.linear.x = 0.1
            return t
        return None


def test_subclass_publishes_on_cmd_vel_name(rclpy_ctx):
    """compute_action()'s return is published on cmd_vel_<name>."""
    policy = _ConstantStub()
    recorder_node = rclpy.create_node('recorder')
    rec = _RecordingSubscriber(recorder_node, 'cmd_vel_stub')

    executor = SingleThreadedExecutor()
    executor.add_node(policy)
    executor.add_node(recorder_node)
    _spin_for(executor, 0.3)  # ~15 ticks at 50 Hz

    assert len(rec.received) > 5, \
        f'expected several twists in 0.3 s, got {len(rec.received)}'
    assert all(abs(m.linear.x - 0.7) < 1e-6 for m in rec.received)

    policy.destroy_node()
    recorder_node.destroy_node()


def test_none_return_is_not_published(rclpy_ctx):
    """When compute_action returns None, no message is sent."""
    policy = _SometimesNoneStub()
    recorder_node = rclpy.create_node('recorder')
    rec = _RecordingSubscriber(recorder_node, 'cmd_vel_stub_optional')

    executor = SingleThreadedExecutor()
    executor.add_node(policy)
    executor.add_node(recorder_node)
    _spin_for(executor, 0.4)  # ~20 ticks; expect ~10 messages

    # All received messages should be the linear.x=0.1 ones — None ticks
    # produce nothing. So count is roughly half the tick count.
    assert 3 < len(rec.received) < 18, \
        f'expected ~half of ticks to publish, got {len(rec.received)}'
    assert all(abs(m.linear.x - 0.1) < 1e-6 for m in rec.received)

    policy.destroy_node()
    recorder_node.destroy_node()
