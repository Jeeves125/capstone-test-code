from periphery import GPIO
from datetime import datetime
import socket, threading, sys, os, time

class Pin:
  def __init__(self, pin_number, direction, inverse=False, offset=0):
    self.gpio = GPIO(pin_number, direction)
    self.gpio.write(False)  # Ensure pin starts LOW

    self.inverse = inverse
    self.deadband = 50
    self.offset = offset

  def write(self, value):
    self.gpio.write(value)

  def close(self):
    self.gpio.close()
    
def try_save_pin_states():
  pickle_path = os.path.join(BASE_DIR, "pin_states.pkl")
  try:
    import pickle
    with open(pickle_path, 'wb') as f:
      pickle.dump({
        "PIN": {
          "inverse": PIN.inverse,
          "offset": PIN.offset,
        },
        "PIN2": {
          "inverse": PIN2.inverse,
          "offset": PIN2.offset,
        }
      }, f)
    print_info("Pin states saved to {}".format(pickle_path))
  except Exception as e:
    print_error("Failed to save pin states: {}".format(e))
    
def try_load_pin_states():
  pickle_path = os.path.join(BASE_DIR, "pin_states.pkl")
  if not os.path.exists(pickle_path):
    print_info("No saved pin states found at {}, starting with defaults.".format(pickle_path))
    return

  try:
    import pickle
    with open(pickle_path, 'rb') as f:
      data = pickle.load(f)
      PIN.inverse = data.get("PIN", {}).get("inverse", False)
      PIN.offset = data.get("PIN", {}).get("offset", 0)
      PIN2.inverse = data.get("PIN2", {}).get("inverse", False)
      PIN2.offset = data.get("PIN2", {}).get("offset", 0)
    print_info("Pin states loaded from {}".format(pickle_path))
  except Exception as e:
    print_error("Failed to load pin states: {}".format(e))
    
stop_event = threading.Event()
pwm_lock = threading.Lock()
pwm_thread = None
client_socket, client_address = None, None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "server.log")

original_stdout = sys.stdout
log_file = open(LOG_PATH, 'a', buffering=1)
sys.stdout = log_file
sys.stderr = log_file
print(flush=True)
print(f" PI SERVER LOG {datetime.now()} ".center(70, "="), flush=True)
print(flush=True)


def print_info(log):
  print("[INFO] {}".format(log), flush=True)


def print_warn(warn):
  print("[WARN] {}".format(warn), flush=True)


def print_error(error):
  print("[*ERROR*] {}".format(error), flush=True)


def get_logs():
  log_file.flush()
  with open(LOG_PATH, 'r') as f:
    return f.read()


def full_exit():
  if client_socket != None:
    client_socket.close()
  if not log_file.closed:
    log_file.close()
  stop_event.set()
  stop_gpio_pwm()
  try_save_pin_states()
  sys.exit(0)


""" PWM using GPIO toggling (50 hz, 1000-2000 microsecond pulse width) """
PIN = Pin(54, "out")
PIN2 = Pin(35, "out")
try_load_pin_states()
PWM_FREQ = 50
PWM_PERIOD_US = 20_000
PWM_PERIOD_S = 1.0 / PWM_FREQ
# neutral and deadband settings
NEUTRAL_PULSE_WIDTH = 1500
# stored pulse_width is the raw commanded value;
pulse_width = NEUTRAL_PULSE_WIDTH
duration_start_time_ns = 0


def configure_pulse_width(value, pin: Pin):
  # First normalize around the deadband
  deadband = getattr(pin, "deadband", 50)
  if abs(value - NEUTRAL_PULSE_WIDTH) <= deadband:
    value = NEUTRAL_PULSE_WIDTH

  # Then apply inversion if needed
  if getattr(pin, "inverse", False):
    pw_magnitude = value - NEUTRAL_PULSE_WIDTH
    value = NEUTRAL_PULSE_WIDTH - pw_magnitude
    
  # Finally, apply the offset
  value += getattr(pin, "offset", 0)

  return value

def start_pwm_loop(pin, stop_event, get_pulse_width, frequency=50):
  try:
    period_ns = int(1e9 / frequency)
    next_cycle_ns = time.perf_counter_ns()

    while not stop_event.is_set():
      pulse_width = get_pulse_width()
      high_time_ns = max(900_000, min(2_100_000, pulse_width * 1_000))

      now_ns = time.perf_counter_ns()
      time_to_cycle_ns = next_cycle_ns - now_ns
      if time_to_cycle_ns > 2_000_000:
        time.sleep((time_to_cycle_ns - 1_000_000) / 1_000_000_000)

      while not stop_event.is_set() and time.perf_counter_ns() < next_cycle_ns:
        pass

      if stop_event.is_set():
        break

      pin.write(True)
      pulse_start_ns = time.perf_counter_ns()
      while not stop_event.is_set() and (time.perf_counter_ns() - pulse_start_ns) < high_time_ns:
        pass
      pin.write(False)

      next_cycle_ns += period_ns
  
  except Exception as e:
    print_error(f"Error in PWM thread: {e}")
    full_exit()

def stop_gpio_pwm():
  stop_event.set()
  try:
    PIN.write(False)
    PIN2.write(False)
  except Exception:
    pass

  try:
    PIN.close()
  except Exception:
    pass

  try:
    PIN2.close()
  except Exception:
    pass


def main_server():
  global client_socket, client_address, pulse_width, duration_start_time_ns, pwm_thread
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  print_info("Starting server...")
  server.bind(('0.0.0.0', 5000))
  server.listen(1)

  def client_connect():
    global client_socket, client_address, pwm_thread
    stop_event.clear()
    print_info("Waiting for a controller to connect...")
    client_socket, client_address = server.accept()

    if pwm_thread is None or not pwm_thread.is_alive():
      # ensure the PWM state begins neutral when a client connects

      pwm_threads = [
        threading.Thread(target=start_pwm_loop, args=(PIN, stop_event, lambda: configure_pulse_width(pulse_width, PIN), PWM_FREQ)),
        threading.Thread(target=start_pwm_loop, args=(PIN2, stop_event, lambda: configure_pulse_width(pulse_width, PIN2), PWM_FREQ)),
      ]
      for thread in pwm_threads:
        thread.start()
      pwm_thread = pwm_threads[0]

  def process_command(command):
    global client_socket, client_address, pulse_width, log_file, duration_start_time_ns

    if command == "":
      print_warn("Received empty command, ignoring.")
      return

    if command == "STOP":
      duration_start_time_ns = time.perf_counter_ns()

    if command.startswith("PWM"):
      command_value = command.replace("PWM", "")
      try:
        pwm_command_value = int(command_value)

        if pwm_command_value < 1000 or pwm_command_value > 2000:
          print_error("PWM value out of range (1000-2000), ignoring command.")
          return

        with pwm_lock:
          if pwm_command_value != pulse_width:
            duration_start_time_ns = time.perf_counter_ns()
          pulse_width = pwm_command_value
      except ValueError:
        print_error("Invalid PWM value.")

    if command == "CALIBRATE_UP_PIN1":
      PIN.offset += 10
      duration_start_time_ns = time.perf_counter_ns()

    if command == "CALIBRATE_DOWN_PIN1":
      PIN.offset -= 10
      duration_start_time_ns = time.perf_counter_ns()

    if command == "CALIBRATE_UP_PIN2":
      PIN2.offset += 10
      duration_start_time_ns = time.perf_counter_ns()

    if command == "CALIBRATE_DOWN_PIN2":
      PIN2.offset -= 10
      duration_start_time_ns = time.perf_counter_ns()

    if command == "LOGS":
      logs = get_logs()
      log_bytes = logs.encode()
      client_socket.send(str(len(log_bytes)).encode())
      client_socket.send(logs.encode())

    if command == "CLEAR_LOGS":
      log_file.close()
      os.remove(LOG_PATH)
      log_file = open(LOG_PATH, 'a', buffering=1)
      sys.stdout = log_file
      sys.stderr = log_file
      print_info("Logs cleared by command.")

  rx_buffer = ""

  print_info("Server is listening on port 5000...")
  while True:
    if client_socket == None or client_address == None:
      client_connect()
      rx_buffer = ""
      continue

    try:
      data = client_socket.recv(1024)
      if not data:
        print_warn("Client disconnected.")
        log_file.flush()
        client_socket.close()
        client_socket, client_address = None, None
        try_save_pin_states()
        continue

      rx_buffer += data.decode(errors="ignore")
      while "\n" in rx_buffer:
        command, rx_buffer = rx_buffer.split("\n", 1)
        command = command.strip()
        if not command:
          continue

        # print_info("Received command from {}:{}".format(client_address[0], client_address[1]))
        process_command(command)

    except Exception as e:
      print_error("Error processing command: {}".format(e))
      client_socket.close()
      client_socket, client_address = None, None


if __name__ == "__main__":
  try:
    main_server()
  except KeyboardInterrupt:
    print_info("Interrupted by user")
    full_exit()
  except Exception as e:
    print_error("Error: {}".format(e))
    full_exit()