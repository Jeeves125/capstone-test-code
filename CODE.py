import pygame
from pygame.locals import *
import engine
from engine import InputManager as Input, Float2

# The { Input.OPTION_CONTROLLER: 0 } option specifies that these inputs are for controller 0 (NOT required, just an example of using options for controller-specific mappings)
Input.add_mapping('move', Float2(0,0), normalized=Input.NORM_REGULAR)
Input.add_mapping_input('move', Input.J_LEFT_Y, Input.JOY_AXIS, Float2(0, -1), { Input.OPTION_CONTROLLER: 0 })
Input.add_mapping_input('move', Input.J_LEFT_X, Input.JOY_AXIS, Float2(1, 0))

while True:
    dt = engine.CLOCK.tick(60) / 1000.0  # delta time
    
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
    
    ''' Handle input '''
    Input.process_events(events)

    action_value = Input.get_action_held('move')
    forward_value = 1500 + (500 * action_value.y)
    

    ''' End frame '''
    engine.CLOCK.tick()