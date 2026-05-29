"""Step reward: progress to goal + bonus on reach − time − crash."""

from dataclasses import dataclass

import numpy as np

GOAL_RADIUS = 0.3        # m — within this counts as goal reached
GOAL_BONUS = 100.0       # one-shot reward when goal_radius is crossed
PROGRESS_GAIN = 1.0      # reward per meter closed toward the goal
CRASH_PENALTY = -50.0    # subtracted when out-of-bounds
TIME_PENALTY = 0.01      # small per-step cost to discourage stalling


@dataclass(frozen=True)
class ArenaBounds:
    """Half-extent square arena, axis-aligned. (-x_half, +x_half) etc."""
    x_half: float = 4.5
    y_half: float = 4.5


def step_reward(
    prev_xy: np.ndarray,
    curr_xy: np.ndarray,
    goal_xy: np.ndarray,
    bounds: ArenaBounds = ArenaBounds(),
) -> tuple[float, bool, bool]:
    """Compute (reward, terminated, out_of_bounds) for one tick.

    Args:
      prev_xy: car position at the start of the step.
      curr_xy: car position after the step.
      goal_xy: target position.
      bounds: arena half-extents.

    Returns:
      reward: scalar.
      terminated: True if the goal was reached this step.
      out_of_bounds: True if the car left the arena (also terminates).
    """
    prev_dist = float(np.linalg.norm(goal_xy - prev_xy))
    curr_dist = float(np.linalg.norm(goal_xy - curr_xy))

    # Dense shaping: positive when we get closer, negative when we drift.
    # `prev - curr` is positive when curr < prev (closer), as desired.
    progress = (prev_dist - curr_dist) * PROGRESS_GAIN

    reward = progress - TIME_PENALTY

    terminated = curr_dist < GOAL_RADIUS
    if terminated:
        reward += GOAL_BONUS

    out_of_bounds = (
        abs(curr_xy[0]) > bounds.x_half or abs(curr_xy[1]) > bounds.y_half
    )
    if out_of_bounds:
        reward += CRASH_PENALTY

    return reward, terminated, out_of_bounds
