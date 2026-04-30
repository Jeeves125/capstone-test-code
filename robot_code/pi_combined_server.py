from periphery import GPIO
from datetime import datetime
import socket, threading, sys, os, time

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
  sys.exit(0)


""" PWM using GPIO toggling (50 hz, 1000-2000 microsecond pulse width) """
PIN = GPIO(54, "out")
PIN2 = GPIO(35, "out")
PWM_FREQ = 50
PWM_PERIOD_NS = 20_000_000
pulse_width = 1500
duration_start_time_ns = 0
NEUTRAL_PULSE_WIDTH = 1500
NEUTRAL_DEADBAND_US = 15


def normalize_pulse_width(value):
  if abs(value - NEUTRAL_PULSE_WIDTH) <= NEUTRAL_DEADBAND_US:
    return NEUTRAL_PULSE_WIDTH
  return value


def start_gpio_pwm(duration=5):
  """Software PWM loop using perf_counter_ns for the highest practical timer resolution."""
  global duration_start_time_ns, pulse_width
  try:
    duration_start_time_ns = time.perf_counter_ns()
    next_cycle_ns = time.perf_counter_ns()

    while not stop_event.is_set():
      with pwm_lock:
        current_pw = normalize_pulse_width(pulse_width)

      high_time_ns = max(900_000, min(2_100_000, current_pw * 1_000))

      now_ns = time.perf_counter_ns()
      time_to_cycle_ns = next_cycle_ns - now_ns
      if time_to_cycle_ns > 2_000_000:
        time.sleep((time_to_cycle_ns - 1_000_000) / 1_000_000_000)

      while not stop_event.is_set() and time.perf_counter_ns() < next_cycle_ns:
        pass

      if stop_event.is_set():
        break

      PIN.write(True)
      PIN2.write(True)
      pulse_start_ns = time.perf_counter_ns()
      while not stop_event.is_set() and (time.perf_counter_ns() - pulse_start_ns) < high_time_ns:
        pass
      PIN.write(False)
      PIN2.write(False)

      next_cycle_ns += PWM_PERIOD_NS

      if current_pw != NEUTRAL_PULSE_WIDTH and duration and (time.perf_counter_ns() - duration_start_time_ns) >= (duration * 1_000_000_000):
        print_warn("Stopped motor due to inactivity")
        with pwm_lock:
          pulse_width = NEUTRAL_PULSE_WIDTH
        duration_start_time_ns = time.perf_counter_ns()
  except Exception as e:
    print_error(f"Error in PWM thread: {e}")
    full_exit()


def stop_gpio_pwm():
  global pulse_width, pwm_thread
  with pwm_lock:
    pulse_width = NEUTRAL_PULSE_WIDTH

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

  pwm_thread = None


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
      pwm_thread = threading.Thread(target=start_gpio_pwm, daemon=True)
      pwm_thread.start()

  def process_command(command):
    global client_socket, client_address, pulse_width, log_file, duration_start_time_ns

    if command == "":
      print_warn("Received empty command, ignoring.")
      return

    if command == "STOP":
      with pwm_lock:
        pulse_width = NEUTRAL_PULSE_WIDTH
      duration_start_time_ns = time.perf_counter_ns()

    if command.startswith("PWM"):
      command_value = command.replace("PWM", "")
      try:
        pwm_command_value = int(command_value)

        if pwm_command_value < 1000 or pwm_command_value > 2000:
          print_error("PWM value out of range (1000-2000), ignoring command.")
          return

        pwm_command_value = normalize_pulse_width(pwm_command_value)

        with pwm_lock:
          if pwm_command_value != pulse_width:
            duration_start_time_ns = time.perf_counter_ns()
          pulse_width = pwm_command_value
      except ValueError:
        print_error("Invalid PWM value.")

    if command == "LOW_FWD":
      with pwm_lock:
        pulse_width = 1700
      duration_start_time_ns = time.perf_counter_ns()

    if command == "HIGH_FWD":
      with pwm_lock:
        pulse_width = 1900
      duration_start_time_ns = time.perf_counter_ns()

    if command == "LOW_BWD":
      with pwm_lock:
        pulse_width = 1300
      duration_start_time_ns = time.perf_counter_ns()

    if command == "HIGH_BWD":
      with pwm_lock:
        pulse_width = 1100
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
        continue

      rx_buffer += data.decode(errors="ignore")
      while "\n" in rx_buffer:
        command, rx_buffer = rx_buffer.split("\n", 1)
        command = command.strip()
        if not command:
          continue

        print_info("Received command from {}:{}".format(client_address[0], client_address[1]))
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