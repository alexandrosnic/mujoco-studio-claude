"""UR5e + Robotiq 2F-85 pick-and-place scene and controller (no Studio imports).

The arm picks three coloured cubes off a table and places each on the pad of
the same colour. Cubes are held by finger friction only: nothing is welded.

The robot models are not part of this folder; see README.md for the two
commands that fetch them into assets/.
"""

import dataclasses
import pathlib

import mujoco
import numpy as np

ASSETS = pathlib.Path(__file__).resolve().parent / 'assets'
UR5E_XML = ASSETS / 'universal_robots_ur5e' / 'ur5e.xml'
GRIPPER_XML = ASSETS / 'robotiq_2f85' / '2f85.xml'

TABLE_Z = 0.5  # Height of the table top; the robot base sits on it.
CUBE_HALF = 0.025
# Name, colour, start (x, y) and pad (x, y) on the table, in meters.
CUBES = (
    ('red', (0.85, 0.15, 0.15), (0.50, -0.15), (0.15, 0.50)),
    ('green', (0.15, 0.70, 0.25), (0.50, 0.00), (0.30, 0.50)),
    ('blue', (0.15, 0.35, 0.90), (0.50, 0.15), (0.45, 0.50)),
)
ARM_JOINTS = (
    'shoulder_pan_joint',
    'shoulder_lift_joint',
    'elbow_joint',
    'wrist_1_joint',
    'wrist_2_joint',
    'wrist_3_joint',
)
HOME = np.array([0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0])
PINCH_SITE = 'grip_pinch'
GRIPPER_ACTUATOR = 'grip_fingers_actuator'
GRIPPER_OPEN, GRIPPER_CLOSED = 0.0, 255.0
# Tool pointing straight down, fingers closing along a table axis.
TOOL_DOWN = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]])

HOVER = 0.16  # Height of the pinch point above a cube centre when hovering.
GRASP_DZ = 0.004  # Pinch point this far above the cube centre when grasping.
RELEASE_DZ = 0.006  # Cube is let go this far above its resting height.
DWELL = 0.7  # Seconds to wait for the fingers to close or open.
SETTLE_SPEED = 0.02  # The arm has arrived when every joint is slower (rad/s).
PLACE_TOL = 0.02  # A cube counts as placed within this distance of its pad.


def build_spec() -> mujoco.MjSpec:
  """Returns the full scene: table, arm with gripper, cubes and pads."""
  arm = mujoco.MjSpec.from_file(str(UR5E_XML))
  gripper = mujoco.MjSpec.from_file(str(GRIPPER_XML))
  for key in list(arm.keys):
    arm.delete(key)
  arm.attach(gripper, site=arm.site('attachment_site'), prefix='grip_')

  spec = mujoco.MjSpec()
  spec.modelname = 'ur5e_pick_place'
  spec.option.timestep = 0.002
  spec.option.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
  # Elliptic friction cones with a high impratio keep grasped objects from
  # creeping out of the fingers.
  spec.option.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
  spec.option.impratio = 10
  spec.visual.headlight.diffuse = [0.6, 0.6, 0.6]
  spec.visual.headlight.ambient = [0.35, 0.35, 0.35]
  spec.visual.headlight.specular = [0, 0, 0]
  spec.visual.rgba.haze = [0.15, 0.25, 0.35, 1]
  spec.visual.global_.azimuth = 150
  spec.visual.global_.elevation = -25
  spec.visual.global_.offwidth = 1280
  spec.visual.global_.offheight = 720
  spec.stat.center = [0.3, 0.15, TABLE_Z + 0.2]
  spec.stat.extent = 1.3

  spec.add_texture(
      type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
      builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT,
      rgb1=[0.3, 0.5, 0.7],
      rgb2=[0, 0, 0],
      width=512,
      height=3072,
  )
  spec.add_texture(
      name='groundplane',
      type=mujoco.mjtTexture.mjTEXTURE_2D,
      builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
      mark=mujoco.mjtMark.mjMARK_EDGE,
      rgb1=[0.2, 0.3, 0.4],
      rgb2=[0.1, 0.2, 0.3],
      markrgb=[0.8, 0.8, 0.8],
      width=300,
      height=300,
  )
  ground = spec.add_material(
      name='groundplane', texrepeat=[5, 5], texuniform=True, reflectance=0.2
  )
  ground.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = 'groundplane'

  world = spec.worldbody
  world.add_light(
      pos=[0.3, 0, 3],
      dir=[0, 0, -1],
      type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
  )
  world.add_geom(
      name='floor',
      type=mujoco.mjtGeom.mjGEOM_PLANE,
      size=[0, 0, 0.05],
      material='groundplane',
  )
  wood = [0.72, 0.58, 0.42, 1]
  world.add_geom(
      name='table',
      type=mujoco.mjtGeom.mjGEOM_BOX,
      pos=[0.25, 0.1, TABLE_Z - 0.02],
      size=[0.55, 0.65, 0.02],
      rgba=wood,
      friction=[1.0, 0.005, 0.0001],
  )
  for x in (-0.22, 0.72):
    for y in (-0.47, 0.67):
      world.add_geom(
          type=mujoco.mjtGeom.mjGEOM_BOX,
          pos=[x, y, (TABLE_Z - 0.04) / 2],
          size=[0.03, 0.03, (TABLE_Z - 0.04) / 2],
          rgba=wood,
      )
  world.add_camera(
      name='overview',
      pos=[1.55, -0.75, 1.35],
      xyaxes=[0.48, 0.88, 0, -0.42, 0.23, 0.88],
  )

  for name, rgb, start, pad in CUBES:
    # The pad is a visual marker only; the cube rests on the table.
    world.add_geom(
        name=f'{name}_pad',
        type=mujoco.mjtGeom.mjGEOM_BOX,
        pos=[*pad, TABLE_Z + 0.0005],
        size=[0.045, 0.045, 0.0005],
        rgba=[*rgb, 0.45],
        contype=0,
        conaffinity=0,
    )
    cube = world.add_body(
        name=f'{name}_cube', pos=[*start, TABLE_Z + CUBE_HALF]
    )
    cube.add_freejoint(name=f'{name}_free')
    cube.add_geom(
        name=f'{name}_geom',
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[CUBE_HALF] * 3,
        rgba=[*rgb, 1],
        mass=0.06,
        condim=4,
        friction=[1.0, 0.02, 0.0001],
    )

  mount = world.add_frame(pos=[0, 0, TABLE_Z])
  spec.attach(arm, frame=mount, prefix='')
  return spec


def _orientation_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
  """Returns the rotation vector taking `current` to `target` (3x3 each)."""
  quat = np.zeros(4)
  mujoco.mju_mat2Quat(quat, (target @ current.T).flatten())
  error = np.zeros(3)
  mujoco.mju_quat2Vel(error, quat, 1.0)
  return error


@dataclasses.dataclass
class Step:
  """One leg of the routine: move the pinch point to `goal`, then wait."""

  label: str
  goal: np.ndarray
  gripper: float
  dwell: float = 0.0
  speed_scale: float = 1.0


class PickPlaceController:
  """Runs the pick-and-place routine; call `update` once before every step.

  Joint targets come from damped-least-squares inverse kinematics solved on a
  private copy of the state, so the plan is not disturbed by tracking lag. The
  model's own position actuators then follow those joint targets.
  """

  def __init__(self, model: mujoco.MjModel):
    self.model = model
    self.ik_data = mujoco.MjData(model)
    self.site = model.site(PINCH_SITE).id
    self.arm_qpos = np.array(
        [model.joint(j).qposadr[0] for j in ARM_JOINTS]
    )
    self.arm_dof = np.array([model.joint(j).dofadr[0] for j in ARM_JOINTS])
    self.arm_ctrl = np.array(
        [model.actuator(j.removesuffix('_joint')).id for j in ARM_JOINTS]
    )
    self.grip_ctrl = model.actuator(GRIPPER_ACTUATOR).id
    self.speed = 0.35  # Tool speed along a leg, in m/s.
    self.reset_state()

  def reset_state(self) -> None:
    """Starts the routine again from the home pose."""
    self.q_cmd = HOME.copy()
    self.steps: list[Step] = []
    self.index = 0
    self.target: np.ndarray | None = None
    self.dwell_until: float | None = None
    self.done_at: float | None = None

  def reset(self, data: mujoco.MjData) -> None:
    """Puts cubes back, sends the arm home and restarts the routine."""
    mujoco.mj_resetData(self.model, data)
    data.qpos[self.arm_qpos] = HOME
    data.ctrl[self.arm_ctrl] = HOME
    data.ctrl[self.grip_ctrl] = GRIPPER_OPEN
    mujoco.mj_forward(self.model, data)
    self.reset_state()

  def _plan(self, data: mujoco.MjData) -> list[Step]:
    """Builds the legs from where the cubes are right now."""
    steps = []
    for name, _, _, pad in CUBES:
      cube = data.xpos[self.model.body(f'{name}_cube').id].copy()
      grasp = cube + [0, 0, GRASP_DZ]
      place = np.array([*pad, TABLE_Z + CUBE_HALF + GRASP_DZ + RELEASE_DZ])
      up = np.array([0, 0, HOVER])
      steps += [
          Step(f'{name}: move above cube', grasp + up, GRIPPER_OPEN),
          Step(f'{name}: lower', grasp, GRIPPER_OPEN, speed_scale=0.5),
          Step(f'{name}: grasp', grasp, GRIPPER_CLOSED, dwell=DWELL),
          Step(f'{name}: lift', grasp + up, GRIPPER_CLOSED, speed_scale=0.6),
          Step(f'{name}: carry to pad', place + up, GRIPPER_CLOSED),
          Step(f'{name}: lower', place, GRIPPER_CLOSED, speed_scale=0.5),
          Step(f'{name}: release', place, GRIPPER_OPEN, dwell=DWELL),
          Step(f'{name}: retreat', place + up, GRIPPER_OPEN),
      ]
    return steps

  def _solve_ik(self, target: np.ndarray) -> None:
    """Moves `q_cmd` so the pinch point reaches `target`, tool pointing down."""
    model, d = self.model, self.ik_data
    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))
    for _ in range(3):
      d.qpos[self.arm_qpos] = self.q_cmd
      mujoco.mj_kinematics(model, d)
      mujoco.mj_comPos(model, d)
      error = np.concatenate([
          target - d.site_xpos[self.site],
          _orientation_error(TOOL_DOWN, d.site_xmat[self.site].reshape(3, 3)),
      ])
      mujoco.mj_jacSite(model, d, jacp, jacr, self.site)
      jac = np.vstack([jacp, jacr])[:, self.arm_dof]
      dq = jac.T @ np.linalg.solve(jac @ jac.T + 1e-4 * np.eye(6), error)
      self.q_cmd = self.q_cmd + np.clip(dq, -0.05, 0.05)

  def update(self, data: mujoco.MjData) -> None:
    """Writes this step's controls into `data.ctrl`."""
    if not self.steps:
      self.steps = self._plan(data)
      self.ik_data.qpos[:] = data.qpos
      # Start the first leg from where the tool is when the arm is at home.
      self.ik_data.qpos[self.arm_qpos] = self.q_cmd
      mujoco.mj_kinematics(self.model, self.ik_data)
      self.target = self.ik_data.site_xpos[self.site].copy()

    if self.index < len(self.steps):
      step = self.steps[self.index]
      to_goal = step.goal - self.target
      distance = float(np.linalg.norm(to_goal))
      stride = self.speed * step.speed_scale * self.model.opt.timestep
      if distance > stride:
        self.target = self.target + to_goal / distance * stride
      else:
        self.target = step.goal.copy()
        # Wait for the real arm to catch up with the plan and come to rest.
        moving = np.abs(data.qvel[self.arm_dof]).max()
        if self.dwell_until is None and moving < SETTLE_SPEED:
          self.dwell_until = data.time + step.dwell
        if self.dwell_until is not None and data.time >= self.dwell_until:
          self.dwell_until = None
          self.index += 1
          if self.index == len(self.steps):
            self.done_at = float(data.time)
      self._solve_ik(self.target)
      data.ctrl[self.grip_ctrl] = step.gripper
    else:
      # Routine finished: ease back to the home pose.
      self.q_cmd += np.clip(HOME - self.q_cmd, -0.002, 0.002)
      data.ctrl[self.grip_ctrl] = GRIPPER_OPEN
    data.ctrl[self.arm_ctrl] = self.q_cmd

  @property
  def label(self) -> str:
    if self.index < len(self.steps):
      return self.steps[self.index].label
    return 'done' if self.steps else 'starting'

  def placed(self, data: mujoco.MjData) -> dict[str, bool]:
    """Returns, per cube, whether it rests on its own pad."""
    result = {}
    for name, _, _, pad in CUBES:
      pos = data.xpos[self.model.body(f'{name}_cube').id]
      on_pad = np.linalg.norm(pos[:2] - pad) < PLACE_TOL
      resting = abs(pos[2] - (TABLE_Z + CUBE_HALF)) < 0.005
      result[name] = bool(on_pad and resting)
    return result
