#!/usr/bin/env bash
# Launch N parallel (sim + mux) pairs, each isolated by ROS_DOMAIN_ID and
# GZ_PARTITION via the env_id launch arg. Logs go to /tmp/sim_e<N>.log
# and /tmp/mux_e<N>.log. Each sim is wrapped in xvfb-run so it renders
# off-screen — no display required.
#
# Usage:
#   ./scripts/launch_parallel_sims.sh 4        # bring up env_id 0..3
#   ./scripts/launch_parallel_sims.sh 4 5      # bring up env_id 5..8
#
# Tear down:
#   pkill -9 -f 'ros2 launch'
#   pkill -9 -f 'gz sim'
#   pkill -9 -f Xvfb
#
# Run from inside the docker `ros` container with the workspace sourced.
set -euo pipefail

N="${1:?usage: $0 <count> [start_id]}"
START="${2:-0}"

if ! command -v xvfb-run >/dev/null; then
    echo "xvfb-run not on PATH — apt install xvfb" >&2
    exit 1
fi

for i in $(seq 0 $((N - 1))); do
    EID=$((START + i))
    echo "launching env_id=${EID}"
    xvfb-run -a --server-args="-screen 0 640x480x24" \
        bash -lc "ros2 launch havoc_description spawn.launch.py env_id:=${EID}" \
        > "/tmp/sim_e${EID}.log" 2>&1 &
    bash -lc "ros2 launch havoc_bringup autonomous.launch.py env_id:=${EID}" \
        > "/tmp/mux_e${EID}.log" 2>&1 &
done

echo "launched ${N} envs. Tail /tmp/sim_e*.log / /tmp/mux_e*.log for status."
echo "Wait ~25 s before connecting envs."
