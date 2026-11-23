#!/usr/bin/env bash
# Copies the UR5e and Robotiq 2F-85 models from MuJoCo Menagerie into assets/.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
studio="$here/../../skills/mujoco-studio/scripts/studio.sh"
mkdir -p "$here/assets"
for name in universal_robots_ur5e robotiq_2f85; do
  src="$(bash "$studio" menagerie "$name" | tail -n 1)"
  mkdir -p "$here/assets/$name"
  cp "$src"/*.xml "$here/assets/$name/"
  cp -r "$src/assets" "$here/assets/$name/"
  cp "$src/LICENSE" "$here/assets/$name/"
done
echo "models are in $here/assets"
