# from picamera2 import Picamera2
from periphery import GPIO, PWM
from datetime import datetime
import socket, threading, sys, os, time

stop_event = threading.Event()
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
  logs = ""
  with open(LOG_PATH, 'r') as f:
    logs = f.read()
  return logs

def full_exit():
  if client_socket != None:
    client_socket.close()
  if not log_file.closed:
    log_file.close()
  stop_event.set()
  stop_gpio_pwm()
  sys.exit(0)

""" PWM using GPIO toggling (50 hz, 1000-2000 microsecond pulse width) """
PIN = GPIO(54, "out")  # GPIO number for PWM15
PIN2 = GPIO(35, "out")  # GPIO number for PWM15
PWM_FREQ = 50  # 50 Hz
PWM_PERIOD = 1.0 / PWM_FREQ
pulse_width = 1500  # Neutral pulse width in microseconds
duration_start_time = 0

def start_gpio_pwm(duration=5):
  global duration_start_time, pulse_width
  try:
    duration_start_time = time.monotonic()
    start_time = time.monotonic()
    next_pulse = start_time
    while True:
      duty = pulse_width / 1_000_000  # Convert microseconds to seconds
      
      now = time.monotonic()
      if now < next_pulse:
        time.sleep(next_pulse - now)

      PIN.write(True)
      PIN2.write(True)
      pulse_start = time.monotonic()
      while time.monotonic() - pulse_start < duty:
        pass  # busy wait for more precise high pulse
      PIN.write(False)
      PIN2.write(False)

      next_pulse += PWM_PERIOD
      
      # If I want to only have it last a certain amount of time.
      if pulse_width != 1500 and duration and (now - duration_start_time) >= duration:
        print_warn("Stopped motor due to inactivity")
        pulse_width = 1500
  except Exception as e:
    print_error(f"Error in PWM thread: {e}")
    full_exit()

def stop_gpio_pwm():
  global pulse_width
  pulse_width = 1500  # Reset to neutral
  PIN.write(False)
  PIN2.write(False)
  PIN.close()
  PIN2.close()
  
# print_info("Server starting up...")
# print_warn("This is a test warning message.")
# print_error("This is a test error message.")
# full_exit()

def main_server():
  global client_socket, client_address, pulse_width, duration_start_time
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  print_info("Starting server...")
  server.bind(('0.0.0.0', 5000))
  server.listen(1)

  def client_connect():
    global client_socket, client_address
    stop_event.clear()
    print_info("Waiting for a controller to connect...")
    client_socket, client_address = server.accept()
    
    
    threading.Thread(target=start_gpio_pwm).start()
    # threading.Thread(target=run_camera_server, args=(client_socket, client_address, stop_event)).start()
    
  def process_command(command):
    global client_socket, client_address, pulse_width, log_file, duration_start_time
    
    if command == "":
      print_warn("Received empty command, ignoring.")
      return
    
    if command == "STOP":
      pulse_width = 1500  # Neutral pulse width to stop the motor
    
    if command.startswith("PWM"):
      command = command.replace("PWM", "")
      try:
        pwm_command_value = int(command)
        
        if pwm_command_value < 1000 or pwm_command_value > 2000:
          print_error("PWM value out of range (1000-2000), ignoring command.")
          return
        
        if pwm_command_value != pulse_width:
          duration_start_time = time.monotonic()  # Reset duration timer on new command
        
        pulse_width = pwm_command_value
      except ValueError:
        print_error("Invalid PWM value.")
    
    if command == "LOW_FWD":
      pulse_width = 1700
      duration_start_time = time.monotonic()  # Reset duration timer on stop command
    
    if command == "HIGH_FWD":
      pulse_width = 1900
      duration_start_time = time.monotonic()  # Reset duration timer on stop command
      
    if command == "LOW_BWD":
      pulse_width = 1300
      duration_start_time = time.monotonic()  # Reset duration timer on stop command
      
    if command == "HIGH_BWD":
      pulse_width = 1100
      duration_start_time = time.monotonic()  # Reset duration timer on stop command
    
    if command == "LOGS":
      logs = get_logs()
      log_bytes = logs.encode()
      client_socket.send(str(len(log_bytes)).encode())  # Send the length of the log data first
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
      
# def run_camera_server(client_socket, client_address, stop_event):
#   STREAM_PORT = 5001
#   client_host = client_address[0]

#   if stop_event.is_set() or client_host == None:
#     print_error("Camera server stopping before stream start.")
#     return

#   print_info(f"Client registered from {client_host}. Starting stream...")

#   pipeline = [
#       "gst-launch-1.0",
#       "fdsrc",
#       "!",
#       "h264parse",
#       "config-interval=1",
#       "!",
#       "rtph264pay",
#       "pt=96",
#       "!",
#       f"udpsink host={client_host} port={STREAM_PORT} sync=false"
#   ]

#   gst = subprocess.Popen(pipeline, stdin=subprocess.PIPE)

#   picam2 = Picamera2()

#   config = picam2.create_video_configuration(
#       main={"size": (1280, 720)},
#       controls={"FrameRate": 30}
#   )

#   picam2.configure(config)
#   picam2.start()

#   try:
#     picam2.start_recording("h264", gst.stdin)
#     stop_event.wait()
#   finally:
#     try:
#       picam2.stop_recording()
#     except Exception:
#       pass
#     try:
#       picam2.stop()
#     except Exception:
#       pass
#     try:
#       picam2.close()
#     except Exception:
#       pass

#     if gst.stdin:
#       try:
#         gst.stdin.close()
#       except Exception:
#         pass

#     try:
#       gst.terminate()
#       gst.wait(timeout=3)
#     except Exception:
#       try:
#         gst.kill()
#       except Exception:
#         pass


  
if __name__ == "__main__":
  try:
    main_server()
  except KeyboardInterrupt:
    print_info("Interrupted by user")
    full_exit()
  except Exception as e:
    print_error("Error: {}".format(e))
    full_exit()