"""Simulation-side Studio plugin (hot-reloaded on save). Keep it thin."""

import mujoco
from mujoco.studio import messages
from mujoco.studio import plugin
import scene


class SimPlugin(plugin.SimPlugin):
  """Shows scene.build_spec() and runs scene.Controller before every step."""

  controller: scene.Controller | None = None

  @messages.handler
  def on_load_model(self, event: messages.LoadModelEvent) -> bool:
    if event.path:
      return False  # A model file was dropped on the viewer: show that.
    self.handle.set_model(scene.build_spec(), watch=list(scene.WATCH))
    return True

  @messages.handler
  def on_post_model(self, event: messages.PostModelEvent) -> None:
    # The daemon keeps joint positions, controls and time across a reload.
    # Resetting here makes every save restart the routine from the beginning.
    self.controller = scene.Controller(event.model)
    self.controller.reset(event.data)

  @messages.handler
  def on_hot_reload(self, event: messages.HotReloadEvent) -> None:
    if self in event.plugins:
      self.handle.reload()

  @messages.handler
  def on_pre_step(self, event: messages.PreStepEvent) -> None:
    if self.controller is not None and self.controller.model is event.model:
      self.controller.step(event.data)
