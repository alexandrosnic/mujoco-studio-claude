"""Viewer-side Dear ImGui Studio plugin (hot-reloaded on save)."""

import messages as user_messages
from mujoco.studio import messages
from mujoco.studio import plugin
from mujoco.studio.app import plugins as app_plugins

imgui = app_plugins.imgui


class ViewerPlugin(plugin.ViewerPlugin):
  """Pick-and-place panel: stage, placed cubes, speed, restart."""

  speed: float = 0.35
  loop: bool = True
  telemetry: user_messages.Telemetry = user_messages.Telemetry()
  window_open: bool = True

  @messages.handler
  def on_telemetry(self, snapshot: user_messages.Telemetry) -> None:
    self.telemetry = snapshot

  @messages.handler
  def on_build_gui(self, event: messages.BuildGuiEvent) -> None:
    del event
    if not self.window_open:
      return
    expanded, self.window_open = imgui.Begin(
        'UR5e Pick and Place###PickPlaceWindow', self.window_open
    )
    try:
      if not expanded:
        return
      t = self.telemetry
      imgui.TextUnformatted(f'Stage: {t.stage}')
      imgui.TextUnformatted(f'On their pads: {", ".join(t.placed) or "none"}')
      imgui.TextUnformatted(f't = {t.sim_time:.1f} s   completed runs: {t.runs}')
      imgui.Separator()
      speed_changed, self.speed = imgui.SliderFloat(
          'Tool speed (m/s)', self.speed, 0.1, 0.8
      )
      loop_changed, self.loop = imgui.Checkbox('Loop', self.loop)
      if speed_changed or loop_changed:
        self.viewer.send_to_sim(
            user_messages.RoutineConfig(speed=self.speed, loop=self.loop)
        )
      if imgui.Button('Restart'):
        self.viewer.send_to_sim(user_messages.RestartEvent())
    finally:
      imgui.End()
