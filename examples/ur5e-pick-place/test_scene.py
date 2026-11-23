"""Headless check. Run from this folder: studio.sh python test_scene.py"""

import mujoco
from PIL import Image
import pick_place

model = pick_place.build_spec().compile()
data = mujoco.MjData(model)
controller = pick_place.PickPlaceController(model)
controller.reset(data)
while controller.done_at is None and data.time < 90:
  controller.update(data)
  mujoco.mj_step(model, data)
while data.time < (controller.done_at or 0) + 2.0:
  controller.update(data)
  mujoco.mj_step(model, data)

placed = controller.placed(data)
assert controller.done_at is not None, 'routine did not finish in 90 s'
assert all(placed.values()), f'cubes not on their pads: {placed}'

renderer = mujoco.Renderer(model, 720, 1280)
renderer.update_scene(data, 'overview')
Image.fromarray(renderer.render()).save('frame.png')
print(f'PASS: all three cubes placed in {controller.done_at:.1f} s; wrote frame.png')
