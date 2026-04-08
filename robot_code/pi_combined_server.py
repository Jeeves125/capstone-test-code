# from picamera2 import Picamera2
from datetime import datetime
import socket, threading, sys, os, time

"""
git clone https://github.com/orangepi-xunlong/wiringOP.git
cd wiringOP
chmod +x build
sudo ./build

gpio readall
"""
PWM_PIN = 14
os.system(f"gpio mode {PWM_PIN} pwm")

stop_event = threading.Event()
client_socket, client_address = None, None
original_stdout = sys.stdout
log_file = open("server.log", 'a')
sys.stdout = log_file
sys.stderr = log_file
print(f" PI SERVER LOG {datetime.now()} ".center(70, "="))

def print_info(log):
  print("[INFO] {}".format(log))
  
def print_warn(warn):
  print("[WARN] {}".format(warn))
  
def print_error(error):
  print("[*ERROR*] {}".format(error))
  
def get_logs():
  log_file.flush()
  logs = ""
  with open("server.log", 'r') as f:
    logs = f.read()
  return logs

def full_exit():
  if client_socket != None:
    client_socket.close()
  if not log_file.closed:
    log_file.close()
  stop_event.set()
  sys.exit(0)
  
# print_info("Server starting up...")
# print_warn("This is a test warning message.")
# print_error("This is a test error message.")
# full_exit()

def main_server():
  global client_socket, client_address
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  print_info("Starting server...")
  server.bind(('0.0.0.0', 5000))
  server.listen(1)

  def client_connect():
    global client_socket, client_address
    stop_event.clear()
    print_info("Waiting for a controller to connect...")
    client_socket, client_address = server.accept()
    # threading.Thread(target=run_camera_server, args=(client_socket, client_address, stop_event)).start()
    
  def process_command(command):
    global client_socket, client_address
    
    # Placeholder for command processing logic
    print_info("Processing command: {}".format(command))
    
    if command == "LOW_FWD":
      #os.system(f"gpio pwm {PWM_PIN} {pulse_width_microseconds}")
      os.system(f"gpio pwm {PWM_PIN} {17}")
      time.sleep(1)
      os.system(f"gpio pwm {PWM_PIN} {15}")
    
    if command == "HIGH_FWD":
      os.system(f"gpio pwm {PWM_PIN} {19}")
      time.sleep(1)
      os.system(f"gpio pwm {PWM_PIN} {15}")
      
    if command == "LOW_BWD":
      os.system(f"gpio pwm {PWM_PIN} {13}")
      time.sleep(1)
      os.system(f"gpio pwm {PWM_PIN} {15}")
      
    if command == "HIGH_BWD":
      os.system(f"gpio pwm {PWM_PIN} {11}")
      time.sleep(1)
      os.system(f"gpio pwm {PWM_PIN} {15}")
    
    if command == "LOGS":
      logs = get_logs()
      log_bytes = logs.encode()
      client_socket.send(str(len(log_bytes)).encode())  # Send the length of the log data first
      client_socket.send(logs.encode())
    
    if command == "CLEAR_LOGS":
      log_file.close()
      os.remove("server.log")
      log_file = open("server.log", 'a')
      sys.stdout = log_file
      sys.stderr = log_file
      print_info("Logs cleared by command.")
    

  print_info("Server is listening on port 5000...")
  while True:
    if client_socket == None or client_address == None:
      client_connect()
      continue
    
    try:
      command = client_socket.recv(1024).decode()      
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