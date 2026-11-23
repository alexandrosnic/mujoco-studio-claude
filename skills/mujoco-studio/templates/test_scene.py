"""Headless check. Run from the scene folder: studio.sh python test_scene.py"""

import mujoco
from PIL import Image
import scene

model = scene.build_spec().compile()
data = mujoco.MjData(model)
controller = scene.Controller(model)
controller.reset(data)
while data.time < 2.0:
  controller.step(data)
  mujoco.mj_step(model, data)

# Assert the outcome the user asked for, in numbers.
box_z = data.xpos[model.body('box').id][2]
assert abs(box_z - 0.05) < 0.005, f'box should rest on the floor, z={box_z:.3f}'

renderer = mujoco.Renderer(model, 720, 1280)
renderer.update_scene(data)
Image.fromarray(renderer.render()).save('frame.png')
print('PASS; wrote frame.png')
