"""Havoc training: Gymnasium envs + future RL training scripts.

The pure-Python pieces (observation builder, reward function) live as
sim-agnostic functions so they can be reused identically by:
  - the Gym env that wraps Gazebo (this PR)
  - a future Isaac env (so a checkpoint trained in either sim uses the
    exact same obs/reward at evaluation time)
  - the inference-side ROS policy (when an RLPolicy lands in
    havoc_policies, it imports the *same* obs builder)

`HavocSimEnv` is the env that talks to a running Gazebo via ROS topics.
"""

import gymnasium as gym

# Register lazily — gym resolves the entry_point string at gym.make()
# time, which means importing havoc_gym (e.g. from a pure-Python unit
# test) does NOT pull in rclpy. The ROS deps only load when something
# actually instantiates the env.
gym.register(
    id="HavocSim-v0",
    entry_point="havoc_gym.sim_env:HavocSimEnv",
)
