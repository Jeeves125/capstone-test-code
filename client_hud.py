import math
import pygame, random
from pygame.locals import *
import moderngl
import numpy as np
import engine
from engine import InputManager as Input, Float2, Float3
from engine.rendering.model import create_model_matrix
from pyrr import Matrix44, Quaternion, Vector3

# The { Input.OPTION_CONTROLLER: 0 } option specifies that these inputs are for controller 0 (NOT required, just an example of using options for controller-specific mappings)
Input.add_mapping('move', Float2(0,0), normalized=Input.NORM_REGULAR)
Input.add_mapping_input('move', Input.J_LEFT_Y, Input.JOY_AXIS, Float2(0, -1), { Input.OPTION_CONTROLLER: 0 })
Input.add_mapping_input('move', Input.J_LEFT_X, Input.JOY_AXIS, Float2(1, 0))
Input.add_mapping_input('move', Input.J_HAT_X, Input.JOY_HAT, Float2(1, 0))
Input.add_mapping_input('move', Input.J_HAT_Y, Input.JOY_HAT, Float2(0, 1))
Input.add_mapping_input('move', pygame.K_w, Input.KEY, Float2(0, 1))
Input.add_mapping_input('move', pygame.K_s, Input.KEY, Float2(0, -1))
Input.add_mapping_input('move', pygame.K_a, Input.KEY, Float2(-1, 0))
Input.add_mapping_input('move', pygame.K_d, Input.KEY, Float2(1, 0))

Input.add_mapping('look', Float2(0,0), normalized=Input.NORM_NONE)
Input.add_mapping_input('look', Input.J_RIGHT_X, Input.JOY_AXIS, Float2(.05, 0))
Input.add_mapping_input('look', Input.J_RIGHT_Y, Input.JOY_AXIS, Float2(0, .05))
# Input.add_mapping_input('look', pygame.K_RIGHT, Input.KEY, Float2(.05, 0))
# Input.add_mapping_input('look', pygame.K_LEFT, Input.KEY, Float2(-.05, 0))
# Input.add_mapping_input('look', pygame.K_DOWN, Input.KEY, Float2(0, .05))
# Input.add_mapping_input('look', pygame.K_UP, Input.KEY, Float2(0, -.05))
Input.add_mapping_input('look', Input.M_MOTION_Y, Input.MOUSE_MOTION, Float2(0, .005))
Input.add_mapping_input('look', Input.M_MOTION_X, Input.MOUSE_MOTION, Float2(.005, 0))

Input.add_mapping('sprint', 0, normalized=Input.NORM_REGULAR)
Input.add_mapping_input('sprint', pygame.K_LCTRL, Input.KEY, 1)
Input.add_mapping_input('sprint', Input.J_LEFT_STICK, Input.JOY_BUTTON, 1, { Input.OPTION_CONTROLLER: 0 })

Input.add_mapping('jump', 0, normalized=Input.NORM_REGULAR)
Input.add_mapping_input('jump', pygame.K_SPACE, Input.KEY, 1)
Input.add_mapping_input('jump', pygame.CONTROLLER_BUTTON_A, Input.JOY_BUTTON, 1, { Input.OPTION_CONTROLLER: 0 })

Input.add_mapping('fly', 0, normalized=Input.NORM_NONE)
Input.add_mapping_input('fly', pygame.K_SPACE, Input.KEY, 1)
Input.add_mapping_input('fly', pygame.K_LSHIFT, Input.KEY, -1)

Input.add_mapping('add_remove_cubes', 0, normalized=Input.NORM_REGULAR)
Input.add_mapping_input('add_remove_cubes', pygame.K_e, Input.KEY, 1)
Input.add_mapping_input('add_remove_cubes', pygame.K_q, Input.KEY, -1)

def move_and_look():
  action_look_value = Input.get_action_held('look')
  camera_capsule.transform.rotation.y -= action_look_value.x * engine.settings.sensitivity
  camera_capsule.transform.rotation.x -= action_look_value.y * engine.settings.sensitivity
  camera_capsule.transform.rotation.x = max(-math.pi/2, min(math.pi/2, camera_capsule.transform.rotation.x))  # Clamp pitch

  right, up, forward = camera_capsule.transform.get_basis_vectors()
  move_speed = 0.1

  if Input.get_action_held('sprint') == 1:
      move_speed = 5

  action_value = Input.get_action_held('move')
  forward_value = (Float3(forward.x, 0, forward.z)).normalize() * action_value.y
  right_value = (Float3(right.x, 0, right.z)).normalize() * action_value.x
  camera_capsule.velocity.xz = (forward_value + right_value) * move_speed
  
  action_value = Input.get_action_held('fly')
  camera_capsule.velocity.y = action_value * move_speed
  camera_capsule.transform.position += camera_capsule.velocity

camera = engine.rendering.Camera()
camera.overlay = engine.rendering.Overlay()

scene = engine.rendering.Scene(0, 0, engine.WIDTH, engine.HEIGHT)

frames = 0

pygame.font.init()
FONT = pygame.font.SysFont("Arial", 24)
total_fps = 0.0
total_frames = 0

cubes: list[engine.rendering.Model] = []
mod_reg = engine.rendering.Model.load(
    "low_poly.obj",
    engine.Transform(
        Float3(10, 0, 0),
        Float3(1,1,1),
    )
)
mod_reg.set_texture(engine.rendering.Texture.load(random.choice(["cube_tex.png", "white.png", "noise.png"])))
mod_reg_2 = engine.rendering.Model.load(
    "cube.obj",
    engine.Transform(
        Float3(0, 0, 0),
        Float3(1,1,1),
    )
)
mod_reg_2.set_texture(engine.rendering.Texture.load(random.choice(["cube_tex.png", "white.png", "noise.png"])))
cubes.append(mod_reg)
cubes.append(mod_reg_2)

scene.add_objects(cubes)


camera.transform.position = engine.Float3(10, 40, 10)
camera_capsule = engine.Capsule(camera.transform, 4, 1)

engine.rendering.DebugDraw.setup()
engine.INDIRECT_PROGRAM['projection'].write(engine.rendering.create_projection_matrix().tobytes())


while True:
    dt = engine.CLOCK.tick(60) / 1000.0  # delta time
    
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
    
    ''' Handle input '''
    Input.process_events(events)
    move_and_look()

    ''' Fill overlay '''
    fps = round(engine.CLOCK.get_fps(), 3)
    total_fps += fps
    total_frames += 1
    text_surf = FONT.render(f"FPS: {fps}", True, (255, 255, 255), (0,0,0))
    text_2_surf = FONT.render(f"Avg FPS: {round(total_fps / total_frames, 3)}", True, (255, 255, 255), (0,0,0))
    text_3_surf = FONT.render(f"Time: {pygame.time.get_ticks() / 1000.0}", True, (255, 255, 255), (0,0,0))
    camera.overlay.fill((0,0,0,0))  # Clear previous overlay
    camera.overlay.blit(text_surf, (0,0))
    camera.overlay.blit(text_2_surf, (0, 24))
    camera.overlay.blit(text_3_surf, (0, 48))

    ''' Render scene '''
    
    # engine.rendering.PPR.begin_frame_post_processing()
    
    engine.CTX.clear(0.0, 0.0, 0.0, 0.0, depth=1)
    engine.INDIRECT_PROGRAM['view'].write(engine.rendering.create_view_matrix().tobytes())
    engine.INDIRECT_PROGRAM['time'].value = pygame.time.get_ticks() / 1000.0
    engine.INDIRECT_PROGRAM['tint'].value = (1.0, 1.0, 1.0, 1.0)
    
    scene.render()

    pygame.display.flip()

    engine.rendering.DebugDraw.draw_all()
    
    # engine.rendering.PPR.end_frame_post_processing()

    ''' End frame '''
    engine.CLOCK.tick()