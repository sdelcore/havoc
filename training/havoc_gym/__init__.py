"""Havoc training: Gymnasium envs + RL scripts. See training/README.md."""

import gymnasium as gym

# Lazy entry_point so importing havoc_gym doesn't pull in rclpy — the
# ROS deps load only at gym.make() time. Keeps the pure-Python tests
# runnable on a non-ROS host.
gym.register(
    id="HavocSim-v0",
    entry_point="havoc_gym.sim_env:HavocSimEnv",
)
