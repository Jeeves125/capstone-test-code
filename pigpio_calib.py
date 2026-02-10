import pigpio
import time

pi = pigpio.pi()

PWM_PIN = 18

STOP = 1500
FORWARD = 1700
REVERSE = 1300

pi.set_servo_pulsewidth(PWM_PIN, STOP)
time.sleep(2)

pi.set_servo_pulsewidth(PWM_PIN, FORWARD)
time.sleep(3)

pi.set_servo_pulsewidth(PWM_PIN, STOP)
time.sleep(1)

pi.set_servo_pulsewidth(PWM_PIN, REVERSE)
time.sleep(3)

pi.set_servo_pulsewidth(PWM_PIN, STOP)
pi.stop()