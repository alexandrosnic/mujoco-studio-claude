"""Viewer-side Studio plugin (hot-reloaded on save). No panel yet.

Add a BuildGuiEvent handler with Dear ImGui widgets when the user should be
able to tweak parameters live; see MuJoCo's `gui` skill.
"""

from mujoco.studio import plugin


class ViewerPlugin(plugin.ViewerPlugin):
  """Empty panel."""
