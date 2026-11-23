"""Scene and controller, with no Studio imports so it can be tested headless.

Replace the contents of build_spec() and Controller with the real scene. Keep
the three entry points: build_spec(), Controller.reset() and Controller.step().
"""

import mujoco

WATCH = ()  # Asset files (robot XMLs) whose edits should rebuild the scene.


def build_spec() -> mujoco.MjSpec:
  """Returns the whole scene."""
  spec = mujoco.MjSpec()
  spec.option.timestep = 0.002
  spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
  # Offscreen pictures up to this size (the default is 640x480).
  spec.visual.global_.offwidth = 1280
  spec.visual.global_.offheight = 720
  world = spec.worldbody
  world.add_light(pos=[0, 0, 3], dir=[0, 0, -1])
  world.add_geom(type=mujoco.mjtGeom.mjGEOM_PLANE, size=[0, 0, 0.05])
  box = world.add_body(name='box', pos=[0, 0, 0.5])
  box.add_freejoint(name='box_free')
  box.add_geom(
      type=mujoco.mjtGeom.mjGEOM_BOX, size=[0.05] * 3, rgba=[0.9, 0.3, 0.2, 1]
  )
  return spec


class Controller:
  """Writes controls before every physics step."""

  def __init__(self, model: mujoco.MjModel):
    self.model = model

  def reset(self, data: mujoco.MjData) -> None:
    """Puts the simulation in its start state (home pose, matching ctrl)."""
    mujoco.mj_resetData(self.model, data)  # Also sets data.time back to 0.
    mujoco.mj_forward(self.model, data)

  def step(self, data: mujoco.MjData) -> None:
    """Sets data.ctrl for this step."""
