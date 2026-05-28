"""Abstract base class for driving policies.

A policy reads observations (whatever it needs — pose, goal, scan, etc.)
and publishes a `geometry_msgs/Twist` at a fixed rate. Every policy
publishes on its own topic `cmd_vel_<name>`; `twist_mux` arbitrates the
collection onto the canonical `/cmd_vel` based on priority and timeout.

Subclasses implement `compute_action()`. They subscribe to whichever
inputs they need themselves — the base class deliberately doesn't
prescribe an observation contract, because different policies want
different inputs (an end-to-end RL policy wants raw state; pure pursuit
wants a Path).
"""

from abc import ABC, abstractmethod
from typing import Optional

from geometry_msgs.msg import Twist
from rclpy.node import Node


class BasePolicy(Node, ABC):
    """Base class for a /cmd_vel-producing policy.

    Args:
      name: short identifier. Determines node name (`{name}_policy`) and
        output topic (`cmd_vel_{name}`). Must match the corresponding
        entry in twist_mux.yaml.
      rate_hz: publish rate of the action loop.
    """

    def __init__(self, name: str, rate_hz: float = 20.0):
        super().__init__(f'{name}_policy')
        self._name = name
        self._cmd_pub = self.create_publisher(Twist, f'cmd_vel_{name}', 10)
        # 20 Hz default matches Nav2's controller_frequency and gives the
        # MCU watchdog (~200 ms tolerance) comfortable headroom.
        self._timer = self.create_timer(1.0 / rate_hz, self._tick)

    def _tick(self) -> None:
        action = self.compute_action()
        # None means "I have nothing to say right now" — twist_mux will
        # time us out and fall through to the next-priority source.
        if action is not None:
            self._cmd_pub.publish(action)

    @abstractmethod
    def compute_action(self) -> Optional[Twist]:
        """Return the next Twist to publish, or None to stay silent."""
