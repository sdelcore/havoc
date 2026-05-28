"""Pure-Python observation builder. No ROS / no Gazebo dependencies.

The same function builds the obs vector at training time (inside the
Gym env) and at inference time (inside RLPolicy when it ships). Having
a single source of truth here is what makes the env/policy pair
correct-by-construction — there's no way for the policy to see a
differently-shaped obs than what it was trained on.

Obs layout (v0):
  [x_world, y_world, yaw, vx, vy, dx_goal, dy_goal]

  - position / yaw are in the world (map) frame
  - velocities are in the world frame
  - goal delta is goal_xy - position_xy (also world frame)

Why no depth/scan yet: state-based first, vision later. See PR #21
discussion. Adding depth rays is a tuple-extension here + a wider obs
space in sim_env.
"""

from dataclasses import dataclass

import numpy as np

OBS_DIM = 7


@dataclass(frozen=True)
class CarState:
    """The minimum sensor-derived state the env needs at one tick."""
    x: float
    y: float
    yaw: float  # radians
    vx: float
    vy: float


def build_observation(state: CarState, goal_x: float, goal_y: float) -> np.ndarray:
    """Build the OBS_DIM-vector consumed by the policy.

    Returned dtype is float32 to match torch / SB3 defaults — important
    because gymnasium will silently cast otherwise and we'd lose
    precision twice for no reason.
    """
    return np.array([
        state.x, state.y, state.yaw,
        state.vx, state.vy,
        goal_x - state.x, goal_y - state.y,
    ], dtype=np.float32)
