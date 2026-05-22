from periphery import GPIO
from datetime import datetime
import glob
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
camera_thread = None
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
PIN2 = Pin(35, "out", inverse=True)
try_load_pin_states()
PWM_FREQ = 50
PWM_PERIOD_US = 20_000
PWM_PERIOD_S = 1.0 / PWM_FREQ
# neutral and deadband settings
NEUTRAL_PULSE_WIDTH = 1500
# stored pulse_width is the raw commanded value;
pulse_width_1 = NEUTRAL_PULSE_WIDTH
pulse_width_2 = NEUTRAL_PULSE_WIDTH
duration_start_time_ns = 0

COMMAND_PORT = 5000
CAMERA_STREAM_PORT = 5001
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360
CAMERA_FPS = 20
JPEG_QUALITY = 60
VIDEO_FRAME_SIZE_BYTES = 4


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


def open_webcam_capture(to_open="/dev/video0"):
  try:
    import cv2
  except Exception as e:
    raise RuntimeError("OpenCV is required for camera streaming: {}".format(e))

  print_info("Trying webcam device: {}".format(to_open))

  capture = cv2.VideoCapture(to_open, cv2.CAP_V4L2)
  capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
  capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
  capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

  if capture.isOpened():
    print_info("Using webcam device: {}".format(to_open))
    return capture

  capture.release()

  raise RuntimeError("Failed to open any webcam device")


def configure_camera_capture(capture):
  try:
    import cv2
  except Exception as e:
    raise RuntimeError("OpenCV is required for camera streaming: {}".format(e))

  capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
  capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
  capture.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
  capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
  return capture


def get_camera_candidates():
  candidates = ["/dev/video0", "/dev/video4"]
  candidates.extend(sorted(glob.glob("/dev/video*")))

  seen = []
  unique_candidates = []
  for candidate in candidates:
    if candidate in seen:
      continue
    seen.append(candidate)
    unique_candidates.append(candidate)

  return unique_candidates


def run_camera_server(stop_event):
  try:
    import cv2
  except Exception as e:
    print_error("Camera stream disabled because OpenCV could not be imported: {}".format(e))
    return

  while not stop_event.is_set():
    video_server = None
    video_client = None
    cameras = []
    try:
      for candidate in get_camera_candidates():
        if len(cameras) >= 2:
          break

        try:
          camera = configure_camera_capture(open_webcam_capture(candidate))
          cameras.append(camera)
        except Exception as e:
          print_warn("Skipping camera device {}: {}".format(candidate, e))

      if not cameras:
        raise RuntimeError("No usable camera devices were found")

      if len(cameras) == 1:
        print_warn("Only one camera was found; duplicating its frames for the stereo client.")

      video_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      video_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      video_server.bind(("0.0.0.0", CAMERA_STREAM_PORT))
      video_server.listen(1)
      video_server.settimeout(1.0)
      
      print_info("Waiting for video connection on TCP {}...".format(CAMERA_STREAM_PORT))
      

      while not stop_event.is_set() and video_client is None:
        try:
          video_client, video_address = video_server.accept()
          print_info("Video client connected from {}. Starting stream...".format(video_address[0]))
        except socket.timeout:
          continue

      while not stop_event.is_set() and video_client is not None:
        frames = []

        if len(cameras) == 1:
          ok, frame = cameras[0].read()
          if not ok:
            time.sleep(0.01)
            continue
          frames = [frame, frame]
        else:
          ok1, frame1 = cameras[0].read()
          ok2, frame2 = cameras[1].read()
          if not ok1 or not ok2:
            time.sleep(0.01)
            continue
          frames = [frame1, frame2]

        encoded_frames = []
        for frame in frames:
          ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
          )
          if not ok:
            encoded_frames = []
            break
          encoded_frames.append(encoded.tobytes())

        if len(encoded_frames) != 2:
          continue

        try:
          for payload in encoded_frames:
            video_client.sendall(len(payload).to_bytes(VIDEO_FRAME_SIZE_BYTES, byteorder="big"))
            video_client.sendall(payload)
        except Exception as e:
          print_warn("Video client disconnected or stream failed: {}".format(e))
          break

    except Exception as e:
      print_error("Camera server error: {}".format(e))
      time.sleep(1.0)
    finally:
      try:
        for camera in cameras:
          try:
            camera.release()
          except Exception:
            pass
      except Exception:
        pass

      try:
        if video_client is not None:
          video_client.close()
      except Exception:
        pass

      try:
        if video_server is not None:
          video_server.close()
      except Exception:
        pass


def start_camera_server():
  global camera_thread
  if camera_thread is None or not camera_thread.is_alive():
    print_info("Starting camera stream service...")
    camera_thread = threading.Thread(target=run_camera_server, args=(stop_event,), daemon=True)
    camera_thread.start()


def main_server():
  global client_socket, client_address, pulse_width, duration_start_time_ns, pwm_thread
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  print_info("Starting server...")
  server.bind(('0.0.0.0', COMMAND_PORT))
  server.listen(1)
  start_camera_server()

  def client_connect():
    global client_socket, client_address, pwm_thread
    stop_event.clear()
    print_info("Waiting for a controller to connect...")
    client_socket, client_address = server.accept()

    if pwm_thread is None or not pwm_thread.is_alive():
      # ensure the PWM state begins neutral when a client connects

      pwm_threads = [
        threading.Thread(target=start_pwm_loop, args=(PIN, stop_event, lambda: configure_pulse_width(pulse_width_1, PIN), PWM_FREQ)),
        threading.Thread(target=start_pwm_loop, args=(PIN2, stop_event, lambda: configure_pulse_width(pulse_width_2, PIN2), PWM_FREQ)),
      ]
      for thread in pwm_threads:
        thread.start()
      pwm_thread = pwm_threads[0]

  def process_command(command):
    global client_socket, client_address, pulse_width_1, pulse_width_2, log_file, duration_start_time_ns

    if command == "":
      print_warn("Received empty command, ignoring.")
      return

    if command == "STOP":
      duration_start_time_ns = time.perf_counter_ns()

    if command.startswith("PWMONE"):
      command_value = command.replace("PWMONE", "")
      try:
        pwm_command_value = int(command_value)

        if pwm_command_value < 1000 or pwm_command_value > 2000:
          print_error("PWM value out of range (1000-2000), ignoring command.")
          return

        with pwm_lock:
          if pwm_command_value != pulse_width_1:
            duration_start_time_ns = time.perf_counter_ns()
          pulse_width_1 = pwm_command_value
      except ValueError:
        print_error("Invalid PWM value.")
        
    if command.startswith("PWMTWO"):
      command_value = command.replace("PWMTWO", "")
      try:
        pwm_command_value = int(command_value)

        if pwm_command_value < 1000 or pwm_command_value > 2000:
          print_error("PWM value out of range (1000-2000), ignoring command.")
          return

        with pwm_lock:
          if pwm_command_value != pulse_width_2:
            duration_start_time_ns = time.perf_counter_ns()
          pulse_width_2 = pwm_command_value
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

  print_info("Server is listening on port {}...".format(COMMAND_PORT))
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