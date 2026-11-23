---
name: mujoco-studio
description: Use when the user asks to create, simulate, show, visualize or tweak a MuJoCo scene or robot simulation (MJCF, MjSpec, Menagerie robots, pick-and-place, "give me a link to see it"), or when a MuJoCo Studio viewer, studiod daemon or sim_plugin.py is involved. Not for Gazebo, Isaac Sim or other simulators.
---

# MuJoCo Studio from Claude

## Overview

Google's open-source robotics plugin and MuJoCo's own skills already cover scene
authoring and a live, hot-reloading 3D web viewer. They were written for
Antigravity. This skill is the adapter: `scripts/studio.sh` replaces the
Antigravity-only parts, `templates/` is a working starter scene, and the notes
below say which upstream instructions to follow and which to ignore.

**Deliverable:** a scene folder the user can keep, a headless check that the
behaviour asked for really happens, and the viewer address.

All commands below are `bash <this skill's base directory>/scripts/studio.sh <command>`.

## Quick reference

| Command | Use |
|---|---|
| `setup` | Once per machine. Installs `mujoco>=4.0.1` and `pillow` in `~/.venvs/mujoco-studio` and fetches Google's plugin. Safe to re-run. |
| `paths` | Where the upstream skills are. |
| `new DIR` | Create a scene folder from the starter templates. |
| `python ARGS` | The venv's Python with offscreen rendering on. Runs in the current directory, so `cd` into the scene folder first. |
| `start DIR [PORT]` | Serve the scene in `DIR`; replaces any running viewer. Prints the address. |
| `status` | After every save: did scene and plugins reload? Prints the traceback and exits 1 if not. |
| `context` | Live state as JSON (shape below). |
| `menagerie NAME...` | Fetch robot folders from MuJoCo Menagerie; prints their paths. |
| `url` / `stop` | Address of the viewer / stop it. |

## Workflow

1. Run `paths`. If it says not set up, run `setup`.
2. `new DIR`. Use the folder the user names; otherwise
   `./mujoco-scenes/<short-name>/` in the current project. Never a temp folder.
3. Write the scene and controller in `scene.py`. It has no Studio imports, so
   it can be tested headless. Keep its three entry points (`build_spec()`,
   `Controller.reset()`, `Controller.step()`); `sim_plugin.py` already wires
   them to the viewer and rarely needs editing.
4. Edit `test_scene.py` to assert the outcome the user asked for in numbers
   (object positions, speeds, timing), run it with `python test_scene.py` from
   the scene folder until it passes, and look at the picture it saves.
5. `start DIR`, then `status`.
6. Confirm the live simulation does the task: poll `context` about once a
   second across one full cycle of the routine and check the same numbers the
   headless test asserts.
7. Reply with the address from `url`, what you verified, and anything faked or
   simplified.

Read upstream skills only for what the templates do not cover (paths come from
`paths`): MuJoCo's `spec_editing` for building scenes, `python` for model and
data access, `studio` for extra events and messages, `gui` for a panel,
`rendering` for cameras and pictures. The plugin's `motion-planning` and
`mujoco-audit` skills have scripts for collision-free planning and physics
checks.

## Where upstream and this skill differ

| Upstream says | Do this |
|---|---|
| Reply with `[MuJoCo Studio](sidecar://...)` | Give the `http://localhost:PORT/` address. In VS Code: command palette, "Simple Browser: Show". |
| Launch `studiod.py` yourself, `IsDaemon`, `BypassSandbox` | `start DIR`. It backgrounds the daemon and waits until ready. |
| Session file under `$TMPDIR`, `curl .../_studio/status` | `status` and `context`. State lives in `~/.local/state/mujoco-studio`. |
| "Aux pane", "Send to Agent Chat", rules files | Antigravity only. Ignore. |
| Save edits immediately, postpone tests | Test headless first, then start the viewer. |
| Do not load an existing XML with `MjSpec.from_file` in a plugin | That rule is about scene files. Robots are assets: load them with `from_file` and list them in `scene.WATCH`. |
| Always add panel controls; offer to bake to `scene.xml` | Add a panel only when the user wants to tweak parameters live. Bake only if asked. |
| Skills that call Gemini models (`rgb-object-localization`) | Need `GEMINI_API_KEY`. Say so; do not assume it is set. |

## Robots

Use MuJoCo Menagerie models; do not hand-build a known robot.

```python
# After: studio.sh menagerie universal_robots_ur5e robotiq_2f85
# Copy each robot's XML and its assets/ folder into <scene>/assets/<name>/
# (skip MJX variants and preview images; the whole folder can be 30 MB+).
arm = mujoco.MjSpec.from_file(str(ASSETS / 'universal_robots_ur5e' / 'ur5e.xml'))
HOME = ...  # Copy qpos and ctrl from the arm's 'home' keyframe in its XML first.
for key in list(arm.keys):
  arm.delete(key)  # Keyframe sizes no longer match once anything is attached.

# Arm without a hand (UR5e, ...): attach a gripper at the arm's attachment site.
gripper = mujoco.MjSpec.from_file(str(ASSETS / 'robotiq_2f85' / '2f85.xml'))
arm.attach(gripper, site=arm.site('attachment_site'), prefix='grip_')
# Arm that ships with its hand (Franka Panda, ...): skip the gripper; add your
# own tool site on the hand body if you need a point to control.

# Mount the robot in the scene.
mount = spec.worldbody.add_frame(pos=[0, 0, TABLE_Z])
spec.attach(arm, frame=mount, prefix='arm_')
```

Names inside an attached model get the prefix (`grip_pinch`, `arm_elbow_joint`).

## `context` output

```json
{"sim_time": 13.4,
 "qpos": {"<joint name>": [..]},   // free joints: x, y, z, then quaternion
 "qvel": {"<joint name>": [..]},
 "selected_body_name": "", "applied_wrenches": {}}
```

It has joint values only, not body positions. To check a jointless body, read
it in the headless test, or publish it from the plugin.

## Common mistakes

| Symptom | Cause and fix |
|---|---|
| Arm starts flat and hits the table | `qpos` starts at zero. In `Controller.reset()` set the home `qpos` and matching `ctrl`, then `mj_forward`. |
| A save does not restart the routine, or restarts it unexpectedly | The daemon keeps joint positions, controls and time across reloads. The template's `on_post_model` resets on every reload; remove that call to keep state instead. |
| Simulation time jumps back to 0 | `mj_resetData` resets `data.time`. Expected when looping a routine; not a stall. |
| Arm never "arrives" at a target | Position actuators sag a few millimetres under gravity. Wait for joint speeds to drop, not for position error to reach zero. |
| Grasped object slides out | Set `spec.option.cone = mjCONE_ELLIPTIC` and `impratio = 10` on the top-level spec; give the object `condim=4`. Options from attached models are dropped. |
| Tool lags the plan by centimetres | Solve inverse kinematics on a separate `MjData` copy and send joint targets to the actuators; do not chase the measured pose. |
| `Renderer` raises "framebuffer width" | Set `spec.visual.global_.offwidth` and `offheight` to at least the image size (the template does). |
| `import scene` fails under `python` | Run it from the scene folder. |
| Edits do nothing | A failed reload keeps the old code. Run `status` and read the traceback. Renaming a plugin class needs `start` again. |
| Vehicle on a circular track scrubs or slows | Wheels must point along their own circle: turn each by `atan(offset / radius)`. |

## Limits to state in the reply

- One viewer per user: `start` replaces the scene being shown.
- The viewer listens on all network interfaces with no password.
- You cannot see the browser view. Say what was verified headless and through
  `status` and `context`, and that the browser view itself was not seen.
