#!/usr/bin/env bash
# studio.sh — set up and drive the MuJoCo Studio live viewer for an agent.
#
#   studio.sh setup [--update]      install mujoco into a venv, fetch Google's robotics plugin
#   studio.sh new DIR               create a scene folder from the starter templates
#   studio.sh start DIR [PORT]      serve the scene in DIR (replaces any running viewer); prints the URL
#   studio.sh status                did the last save reload cleanly? exit 1 if not
#   studio.sh context               live joint positions, speeds and selection, as JSON
#   studio.sh url                   address of the running viewer
#   studio.sh stop                  stop the viewer
#   studio.sh python ARGS...        the venv's python, with offscreen rendering enabled
#   studio.sh menagerie NAME...     fetch robot folders from MuJoCo Menagerie; prints their paths
#   studio.sh paths                 where the upstream skills and scripts are
set -euo pipefail

DATA="${XDG_DATA_HOME:-$HOME/.local/share}/mujoco-studio"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/mujoco-studio"
VENV="${MUJOCO_STUDIO_VENV:-$HOME/.venvs/mujoco-studio}"
PLUGIN="$DATA/robotics-plugin"
MENAGERIE="$DATA/menagerie"
STUDIOD="$PLUGIN/plugins/robotics/skills/mujoco-studio-sidecar/scripts/studiod.py"
SESSION="$STATE/session.json"
LOG="$STATE/studiod.log"
PY="$VENV/bin/python"

die() { echo "studio.sh: $*" >&2; exit 1; }
need_setup() { [ -x "$PY" ] && [ -f "$STUDIOD" ] || die "not set up yet: run 'studio.sh setup' first"; }
session() { [ -f "$SESSION" ] && python3 -I -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ''))" "$SESSION" "$1" 2>/dev/null || true; }
running() { local pid; pid="$(session pid)"; [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }
get() { curl --noproxy '*' -s -m 10 "http://127.0.0.1:$(session control_port)$1"; }

cmd_setup() {
  mkdir -p "$DATA" "$STATE"
  if [ ! -x "$PY" ]; then
    if command -v uv >/dev/null; then uv venv -q --python 3.12 "$VENV"; else python3 -m venv "$VENV"; fi
  fi
  if command -v uv >/dev/null; then uv pip install -q --python "$PY" --upgrade "mujoco>=4.0.1" pillow
  else "$PY" -m pip install -q --upgrade "mujoco>=4.0.1" pillow; fi
  if [ ! -d "$PLUGIN/.git" ]; then
    git clone -q --depth 1 https://github.com/google-deepmind/robotics-antigravity-plugin.git "$PLUGIN"
  elif [ "${1:-}" = "--update" ]; then
    git -C "$PLUGIN" pull -q --ff-only
  fi
  "$PY" -c "import mujoco, mujoco.studio, mujoco_studio_wasm; print('mujoco', mujoco.__version__, 'with Studio web viewer: ok')"
  cmd_paths
}

cmd_paths() {
  need_setup
  echo "sidecar skill:  $PLUGIN/plugins/robotics/skills/mujoco-studio-sidecar/SKILL.md"
  echo "plugin skills:  $PLUGIN/plugins/robotics/skills/<name>/SKILL.md"
  echo "mujoco skills:  $("$PY" -c "import mujoco, pathlib; print(pathlib.Path(mujoco.__file__).parent / 'doc' / 'skills')")/<name>/SKILL.md"
  echo "python:         $PY"
  echo "daemon log:     $LOG"
}

cmd_stop() {
  local pid; pid="$(session pid)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for _ in $(seq 1 50); do kill -0 "$pid" 2>/dev/null || break; python3 -c "import time; time.sleep(0.1)"; done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid"
    echo "stopped viewer (pid $pid)"
  else
    echo "no viewer running"
  fi
  rm -f "$SESSION"
}

cmd_start() {
  need_setup
  [ $# -ge 1 ] || die "usage: studio.sh start DIR [PORT]"
  local dir port; mkdir -p "$1"; dir="$(cd "$1" && pwd)"; port="${2:-8080}"
  mkdir -p "$STATE"
  running && cmd_stop >/dev/null
  # Keep the same address when possible; fall back to any free port.
  python3 -I -c "import socket,sys; s=socket.socket(); s.bind(('127.0.0.1', int(sys.argv[1])))" "$port" 2>/dev/null || port=0
  rm -f "$SESSION"; : > "$LOG"
  setsid nohup "$PY" "$STUDIOD" --workspace_dir="$dir" --runtime_dir="$STATE" \
    --session_file="$SESSION" --http_port="$port" >> "$LOG" 2>&1 < /dev/null &
  local pid=$!
  for _ in $(seq 1 300); do
    grep -q "Ready:" "$LOG" 2>/dev/null && break
    kill -0 "$pid" 2>/dev/null || { tail -n 30 "$LOG" >&2; die "the viewer exited during startup (log above)"; }
    python3 -c "import time; time.sleep(0.1)"
  done
  grep -q "Ready:" "$LOG" || { tail -n 30 "$LOG" >&2; die "the viewer did not become ready in 30 s (log above)"; }
  python3 -c "import time; time.sleep(1)"
  cmd_status
}

cmd_new() {
  [ $# -ge 1 ] || die "usage: studio.sh new DIR"
  [ -e "$1/sim_plugin.py" ] && die "$1 already has a sim_plugin.py"
  mkdir -p "$1"
  cp "$(dirname "$(dirname "$(readlink -f "$0")")")"/templates/*.py "$1"/
  echo "created $(cd "$1" && pwd): edit scene.py, then run test_scene.py from that folder"
}

cmd_url() { running || die "no viewer running"; echo "http://localhost:$(session http_port)/"; }

cmd_status() {
  running || die "no viewer running (start one with 'studio.sh start DIR')"
  get /_studio/status | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
parts = ("scene", "messages", "sim_plugin", "viewer_plugin")
bad = [p for p in parts if not d.get(p, {}).get("ok", False)]
print("workspace:", d.get("workspace_dir"))
print("viewer:    http://localhost:%s/" % d.get("http_port"))
for p in parts:
    print("%-14s %s" % (p + ":", "ok" if p not in bad else "FAILED"))
for p in bad:
    print("\n--- %s error ---\n%s" % (p, d.get(p, {}).get("error")))
sys.exit(1 if bad else 0)'
}

cmd_context() {
  running || die "no viewer running"
  local out
  # The capture can fail when contacts change mid-read; a retry succeeds.
  for _ in 1 2 3 4; do
    out="$(get '/_studio/context?fresh=1')" && [ "${out:0:1}" = "{" ] && { echo "$out"; return 0; }
    python3 -c "import time; time.sleep(0.3)"
  done
  die "could not capture the simulation state"
}

cmd_python() { need_setup; MUJOCO_GL="${MUJOCO_GL:-egl}" exec "$PY" "$@"; }

cmd_menagerie() {
  [ $# -ge 1 ] || die "usage: studio.sh menagerie NAME... (folder names from github.com/google-deepmind/mujoco_menagerie)"
  mkdir -p "$DATA"
  if [ ! -d "$MENAGERIE/.git" ]; then
    git clone -q --depth 1 --filter=blob:none --sparse https://github.com/google-deepmind/mujoco_menagerie.git "$MENAGERIE"
    git -C "$MENAGERIE" sparse-checkout set "$@"
  else
    git -C "$MENAGERIE" sparse-checkout add "$@"
  fi
  for name in "$@"; do
    [ -d "$MENAGERIE/$name" ] || die "no folder '$name' in MuJoCo Menagerie"
    echo "$MENAGERIE/$name"
  done
}

case "${1:-}" in
  setup) shift; cmd_setup "$@" ;;
  new) shift; cmd_new "$@" ;;
  start) shift; cmd_start "$@" ;;
  status) cmd_status ;;
  context) cmd_context ;;
  url) cmd_url ;;
  stop) cmd_stop ;;
  python) shift; cmd_python "$@" ;;
  menagerie) shift; cmd_menagerie "$@" ;;
  paths) cmd_paths ;;
  *) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
