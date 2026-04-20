from periphery import GPIO, PWM
from time import monotonic, sleep

""" PWM using GPIO toggling (50 hz, 1000-2000 microsecond pulse width) """
PIN = GPIO(54, "out")  # GPIO number for PWM15
PWM_FREQ = 50  # 50 Hz
PWM_PERIOD = 1.0 / PWM_FREQ
pulse_width = 1500  # Neutral pulse width in microseconds
duty = pulse_width / 1_000_000  # Convert microseconds to seconds

def start_gpio_pwm(duration=None):
    start_time = monotonic()
    next_pulse = start_time
    while True:
        now = monotonic()
        if now < next_pulse:
            sleep(next_pulse - now)

        PIN.write(True)
        pulse_start = monotonic()
        while monotonic() - pulse_start < duty:
            pass  # busy wait for more precise high pulse
        PIN.write(False)

        next_pulse += PWM_PERIOD
        
        # If I want to only have it last a certain amount of time.
        # if duration and (now - start_time) >= duration:
        #     break  
        
def stop_gpio_pwm():
    PIN.write(False)
    PIN.close()
    
    
    
""" PWM using actual PWM (50 hz, 1000-2000 microsecond pulse width) """

PWM_PIN = PWM(0, 0)
PWM_PIN.frequency = 50  # 50 Hz
PWM_PIN.duty_cycle = (pulse_width / 1_000) / 20.0

def start_pwm():
    PWM_PIN.enable()
    while True:
        PWM_PIN.duty_cycle = (pulse_width / 1_000) / 20.0
        sleep(0.1)  # Adjust duty cycle every 100ms for testing

def stop_pwm():
    global pulse_width
    pulse_width = 1500  # Reset to neutral
    PWM_PIN.duty_cycle = (pulse_width / 1_000) / 20.0
    PWM_PIN.disable()
    PWM_PIN.close()