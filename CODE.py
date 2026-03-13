import pygame
from pygame.locals import *
import pigpio
import time
# from engine import InputManager as Input, Float2

pygame.init()
pygame.joystick.init()
screen = pygame.display.set_mode((640, 480))
clock = pygame.time.Clock()

joystick = pygame.joystick.Joystick(0)
joystick.init()

print(f"Joystick Name: {joystick.get_name()}")

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
    left_y = joystick.get_axis(1)  # Get the Y-axis value of the left stickq
    # action_value = Input.get_action_held('move')
    forward_value = 1500 + (500 * left_y)
    
    pi.set_servo_pulsewidth(14, forward_value)
    clock.tick(60)