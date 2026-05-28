"""Tests for the pure-Python reward function."""

import numpy as np
import pytest

from havoc_gym.reward import (
    ArenaBounds,
    CRASH_PENALTY,
    GOAL_BONUS,
    GOAL_RADIUS,
    PROGRESS_GAIN,
    TIME_PENALTY,
    step_reward,
)


def _xy(x, y):
    return np.array([x, y], dtype=np.float32)


def test_closing_distance_gives_positive_progress():
    prev = _xy(0.0, 0.0)
    curr = _xy(1.0, 0.0)
    goal = _xy(5.0, 0.0)
    reward, term, oob = step_reward(prev, curr, goal)
    # Closed 1 m → progress = 1.0 * gain - time penalty.
    expected = 1.0 * PROGRESS_GAIN - TIME_PENALTY
    assert reward == pytest.approx(expected, abs=1e-5)
    assert not term
    assert not oob


def test_drifting_away_gives_negative_progress():
    prev = _xy(0.0, 0.0)
    curr = _xy(-1.0, 0.0)
    goal = _xy(5.0, 0.0)
    reward, _, _ = step_reward(prev, curr, goal)
    # Distance went from 5 to 6 → progress = -1.
    expected = -1.0 * PROGRESS_GAIN - TIME_PENALTY
    assert reward == pytest.approx(expected, abs=1e-5)


def test_reaching_goal_terminates_with_bonus():
    prev = _xy(0.5, 0.0)
    curr = _xy(GOAL_RADIUS - 0.01, 0.0)  # just inside the goal radius
    goal = _xy(0.0, 0.0)
    reward, term, oob = step_reward(prev, curr, goal)
    assert term
    assert not oob
    assert reward > GOAL_BONUS * 0.9  # bonus dominates


def test_out_of_bounds_terminates_with_penalty():
    bounds = ArenaBounds(x_half=4.5, y_half=4.5)
    prev = _xy(4.0, 0.0)
    curr = _xy(5.0, 0.0)  # past the +x wall
    goal = _xy(10.0, 0.0)
    reward, term, oob = step_reward(prev, curr, goal, bounds)
    assert oob
    # OOB returns (term=False, oob=True). The env coalesces them, but
    # the reward function reports them separately so callers can log.
    assert not term
    assert reward < CRASH_PENALTY * 0.5  # crash penalty dominates


def test_step_penalty_when_stationary():
    """Standing still: progress=0, only the time penalty applies."""
    prev = _xy(1.0, 1.0)
    curr = _xy(1.0, 1.0)
    goal = _xy(5.0, 5.0)
    reward, _, _ = step_reward(prev, curr, goal)
    assert reward == pytest.approx(-TIME_PENALTY, abs=1e-5)
