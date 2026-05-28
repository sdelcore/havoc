"""ConstantPolicy: emits a fixed Twist at the tick rate.

The simplest concrete BasePolicy. Useful as:
  - a CI smoke test that the policy spine works end-to-end
  - a manual "drive forward at fixed speed" demo
  - what `circle.launch.py` used to do, via the new abstraction
    (set `linear_speed:=0.5 angular_speed:=0.5` for a 1 m radius circle)

Parameters:
  linear_speed  (float, m/s)   default 0.3
  angular_speed (float, rad/s) default 0.0
"""

from typing import Optional

import rclpy
from geometry_msgs.msg import Twist

from havoc_policies.base import BasePolicy


class ConstantPolicy(BasePolicy):
    def __init__(self):
        super().__init__('constant', rate_hz=20.0)
        self._linear = self.declare_parameter('linear_speed', 0.3).value
        self._angular = self.declare_parameter('angular_speed', 0.0).value

    def compute_action(self) -> Optional[Twist]:
        twist = Twist()
        twist.linear.x = float(self._linear)
        twist.angular.z = float(self._angular)
        return twist


def main():
    rclpy.init()
    node = ConstantPolicy()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
