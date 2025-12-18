import pigpio
import time

ESC = 17
pi = pigpio.pi()

# Neutral (arming)
pi.set_servo_pulsewidth(ESC, 1500)
time.sleep(3)

# Small forward
pi.set_servo_pulsewidth(ESC, 1600)
time.sleep(2)

# Back to neutral
pi.set_servo_pulsewidth(ESC, 1500)
