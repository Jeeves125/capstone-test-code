import pygame
from pygame.locals import *
# import pigpio
import time
# from engine import InputManager as Input, Float2

pygame.init()
pygame.joystick.init()
screen = pygame.display.set_mode((640, 480))
clock = pygame.time.Clock()

# joystick = pygame.joystick.Joystick(0)
# joystick.init()

def lerp(a, b, t): 
    return a + (b - a) * t

pwm_pin = 14
wanted_pulse_width = 1500  # Neutral pulse width for ESC (Electronic Speed Controller)
pulse_width = 1500  # Neutral pulse width for ESC (Electronic Speed Controller)

_pulse_width = 1500  # Actual pulse width variable that will be updated smoothly and safely
_max_delta = 50  # Maximum change in pulse width per frame to ensure smooth acceleration/deceleration
def safe_set_motor_speed(pw):
    global _pulse_width
    delta = pw - _pulse_width
    
    if (delta > 0 and _pulse_width < 1500) or (delta < 0 and _pulse_width > 1500):
        _pulse_width = 1500  # Snap to the neutral point if crossing it
        return  # Do not update pulse width if it's already at the boundary
    if (delta > 0 and _pulse_width >= 1500) or (delta < 0 and _pulse_width <= 1500):
        sign_delta = 1 if delta > 0 else -1
        delta = min(abs(delta), _max_delta) * sign_delta  # Limit the delta to max_delta while preserving the sign
        _pulse_width += delta
        
    print(f"Pulse Width: {_pulse_width:.2f}")
    
    # pi.set_servo_pulsewidth(pwm_pin, pulse_width)

# print(f"Joystick Name: {joystick.get_name()}")

# The { Input.OPTION_CONTROLLER: 0 } option specifies that these inputs are for controller 0 (NOT required, just an example of using options for controller-specific mappings)
# Input.add_mapping('move', Float2(0,0), normalized=Input.NORM_REGULAR)
# Input.add_mapping_input('move', Input.J_LEFT_Y, Input.JOY_AXIS, Float2(0, -1), { Input.OPTION_CONTROLLER: 0 })
# Input.add_mapping_input('move', Input.J_LEFT_X, Input.JOY_AXIS, Float2(1, 0))

# pi = pigpio.pi()
# pi.set_mode(pwm_pin, pigpio.OUTPUT)
# pi.set_servo_pulsewidth(pwm_pin, 1500)  # Set initial pulse width to stop the motor
# time.sleep(2)

while True:
    events = pygame.event.get()
    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()
              
    
    ''' Handle input '''
    # Input.process_events(events)
    # left_y = joystick.get_axis(1)  # Get the Y-axis value of the left stickq
    # print(f"Left Stick Y: {left_y:.2f} : Pulse Width: {1500 + (500 * left_y):.2f}")
    
    keys = pygame.key.get_pressed()
    a = int(keys[pygame.K_a])
    d = int(keys[pygame.K_d])
    left_y = -a + d
    
    # action_value = Input.get_action_held('move')
    
    wanted_pulse_width = 1500 + (-500 * left_y)
    pulse_width = lerp(pulse_width, wanted_pulse_width, 0.1)  # Smoothly interpolate towards the target pulse width
    
    safe_set_motor_speed(pulse_width)
    
    clock.tick(60)