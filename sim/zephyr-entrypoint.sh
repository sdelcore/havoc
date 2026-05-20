#!/usr/bin/env bash
# Container entrypoint: ensure the zeth TAP interface exists before
# starting the user command. Zephyr's native_sim eth_native_tap driver
# attaches to a TAP named "zeth"; if the interface doesn't already
# exist on the host (shared via network_mode: host), native_sim aborts
# net stack init.
set -euo pipefail

if ! ip link show zeth > /dev/null 2>&1; then
    ip tuntap add dev zeth mode tap
    ip addr add 192.0.2.2/24 dev zeth
    ip link set dev zeth up
fi

exec "$@"
