"""Messages shared by sim_plugin.py and viewer_plugin.py (none yet).

Add frozen dataclasses deriving from mujoco.studio.messages.Snapshot (latest
value wins) or Event (every one delivered) when the panel needs to talk to the
simulation; see MuJoCo's `studio` skill.
"""
