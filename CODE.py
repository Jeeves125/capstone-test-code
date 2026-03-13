import pygame
from pygame.locals import *
import pigpio
import time
# from engine import InputManager as Input, Float2

# The { Input.OPTION_CONTROLLER: 0 } option specifies that these inputs are for controller 0 (NOT required, just an example of using options for controller-specific mappings)
# Input.add_mapping('move', Float2(0,0), normalized=Input.NORM_REGULAR)
# Input.add_mapping_input('move', Input.J_LEFT_Y, Input.JOY_AXIS, Float2(0, -1), { Input.OPTION_CONTROLLER: 0 })
# Input.add_mapping_input('move', Input.J_LEFT_X, Input.JOY_AXIS, Float2(1, 0))

pi = pigpio.pi()
pi.set_mode(14, pigpio.OUTPUT)
pi.set_servo_pulsewidth(14, 1500)  # Set initial pulse width to stop the motor
time.sleep(2)

while True:
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
    
    ''' Handle input '''
    # Input.process_events(events)

    # action_value = Input.get_action_held('move')
    forward_value = 1500 + 200 # (500 * action_value.y)
    
    pi.set_servo_pulsewidth(14, forward_value)