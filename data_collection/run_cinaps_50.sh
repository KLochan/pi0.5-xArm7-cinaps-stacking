#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source /opt/ros/jazzy/setup.bash
source "$HOME/xarm_ws/install/setup.bash"
exec /usr/bin/python3 "$SCRIPT_DIR/collect_cinaps_50.py"
