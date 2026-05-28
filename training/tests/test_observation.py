"""Tests for the pure-Python observation builder."""

import numpy as np

from havoc_gym.observation import OBS_DIM, CarState, build_observation


def test_obs_shape_and_dtype():
    state = CarState(x=1.0, y=2.0, yaw=0.5, vx=0.3, vy=0.0)
    obs = build_observation(state, goal_x=5.0, goal_y=6.0)
    assert obs.shape == (OBS_DIM,)
    assert obs.dtype == np.float32


def test_goal_delta_is_world_frame():
    """Goal delta should be `goal - pos`, not pos-relative."""
    state = CarState(x=1.0, y=2.0, yaw=0.0, vx=0.0, vy=0.0)
    obs = build_observation(state, goal_x=4.0, goal_y=5.0)
    # Last two entries: dx, dy.
    assert obs[5] == 3.0
    assert obs[6] == 3.0


def test_yaw_appears_at_known_position():
    state = CarState(x=0.0, y=0.0, yaw=1.234, vx=0.0, vy=0.0)
    obs = build_observation(state, goal_x=0.0, goal_y=0.0)
    assert obs[2] == np.float32(1.234)


def test_velocity_passthrough():
    state = CarState(x=0.0, y=0.0, yaw=0.0, vx=0.7, vy=-0.4)
    obs = build_observation(state, goal_x=0.0, goal_y=0.0)
    assert obs[3] == np.float32(0.7)
    assert obs[4] == np.float32(-0.4)
