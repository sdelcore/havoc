"""Observation builder for the policy.

Layout (v0):
  [x, y, yaw, vx, vy, dx_goal, dy_goal]  — world frame, float32
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
