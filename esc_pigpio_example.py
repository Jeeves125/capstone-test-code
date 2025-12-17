import os
import time
import pigpio

# Define the GPIO pin connected to the ESC signal wire (using Broadcom numbering)
ESC_GPIO = 13 

# Optional: Start the pigpiod daemon from the script if not running
# os.system("sudo pigpiod")
# time.sleep(1) # Give the daemon time to start

# Connect to the local pigpio daemon
pi = pigpio.pi()

def calibrate_or_arm():
    """Arms or calibrates the ESC. 
    Follow your ESC's specific instructions for calibration if this generic method fails.
    Generally involves setting max throttle, connecting power, waiting for beeps, then min throttle.
    """
    print(f"Set max throttle ({2000} us)... Disconnect ESC battery now, then press Enter.")
    input()
    pi.set_servo_pulsewidth(ESC_GPIO, 2000) # Maximum throttle
    print("Connect the ESC battery NOW. You should hear beeps. Wait for a few seconds, then press Enter.")
    input()
    pi.set_servo_pulsewidth(ESC_GPIO, 1000) # Minimum throttle
    print("Waiting for the arming/calibration tone sequence to finish (usually 2 beeps). Press Enter when done.")
    input()
    print("ESC armed and ready!")

def control():
    """Allows manual control input to set motor speed."""
    print("Enter a pulse width value between 1000 (stop/min) and 2000 (max) or 'quit' to exit.")
    while True:
        try:
            inp = input("Pulse width (us): ")
            if inp.lower() == 'quit':
                break
            pulse_width = int(inp)
            if 1000 <= pulse_width <= 2000:
                pi.set_servo_pulsewidth(ESC_GPIO, pulse_width)
            else:
                print("Value out of range.")
        except ValueError:
            print("Invalid input.")

def stop():
    """Stops the PWM pulses and disconnects from pigpio."""
    pi.set_servo_pulsewidth(ESC_GPIO, 0) # Stops the pulses
    pi.stop() # Disconnects the pigpio connection
    print("Motor stopped and pigpio disconnected.")

# Main script logic
if __name__ == "__main__":
    try:
        # Run calibration once when you first set up the ESC
        # calibrate_or_arm() 
        # Once calibrated, you might just arm with min throttle on future runs
        
        print("Arming with minimum throttle for a moment...")
        pi.set_servo_pulsewidth(ESC_GPIO, 1000)
        time.sleep(2)
        print("Armed. Starting manual control.")
        
        control()
    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        stop()

