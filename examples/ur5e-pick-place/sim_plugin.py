"""Simulation-side Studio plugin (hot-reloaded on save).

Shows the UR5e pick-and-place scene from pick_place.py and runs its controller
before every physics step. Edit pick_place.py (cube positions, speeds, heights)
and save: the scene is rebuilt and the routine starts again.
"""

import messages as user_messages
from mujoco.studio import messages
from mujoco.studio import plugin
import pick_place

RESTART_AFTER = 3.0  # Seconds to admire the result before looping.


class SimPlugin(plugin.SimPlugin):
  """Builds the scene and drives the pick-and-place routine."""

  speed: float = 0.35
  loop: bool = True
  runs: int = 0
  controller: pick_place.PickPlaceController | None = None
  restart_requested: bool = True

  @messages.handler
  def on_load_model(self, event: messages.LoadModelEvent) -> bool:
    if event.path:
      return False  # Show a model file instead (a dropped file).
    self.handle.set_model(pick_place.build_spec())
    return True

  @messages.handler
  def on_post_model(self, event: messages.PostModelEvent) -> None:
    # A rebuilt scene gets a fresh controller and starts from the beginning.
    self.controller = pick_place.PickPlaceController(event.model)
    self.restart_requested = True

  @messages.handler
  def on_hot_reload(self, event: messages.HotReloadEvent) -> None:
    if self in event.plugins:
      self.handle.reload()

  @messages.handler
  def on_config(self, snapshot: user_messages.RoutineConfig) -> None:
    self.speed = snapshot.speed
    self.loop = snapshot.loop

  @messages.handler
  def on_restart(self, event: user_messages.RestartEvent) -> None:
    del event
    self.restart_requested = True

  @messages.handler
  def on_pre_step(self, event: messages.PreStepEvent) -> None:
    c = self.controller
    if c is None or c.model is not event.model:
      return  # A dropped model without this robot.
    data = event.data
    finished = c.done_at is not None
    if finished and self.loop and data.time > c.done_at + RESTART_AFTER:
      self.restart_requested = True
    if self.restart_requested or data.time < 1e-9:
      self.restart_requested = False
      if finished:
        self.runs += 1
      c.reset(data)
    c.speed = self.speed
    c.update(data)
    self.handle.send_to_viewer(
        user_messages.Telemetry(
            sim_time=float(data.time),
            stage=c.label,
            placed=tuple(k for k, v in c.placed(data).items() if v),
            runs=self.runs,
        )
    )
