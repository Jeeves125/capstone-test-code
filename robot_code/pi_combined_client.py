import socket, pygame, threading, paramiko, os
import sys

import cv2

USER = "robot"
PASSWORD = "robot"
HOST = "192.168.10.76"
MAIN_PORT = 5000
STREAM_PORT = 5001
client: socket.socket = None

stop_event = threading.Event()

def full_exit():
  if client != None:
    client.close()
  stop_event.set()
  sys.exit(0)

def main_client(retry_count=0):
  global client
  """ 
  Connecting to the robot and making sure that the command server is running. 
  """
  
  if retry_count > 0:
    print("Retrying connection to robot, attempt #{}".format(retry_count))
  else:
    os.system('cls')
  
  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(HOST, username=USER, password=PASSWORD)
  
  # Open the secure file transfer.
  sftp = ssh.open_sftp()
  sftp.put(os.path.join(os.getcwd(), "robot_code", "pi_combined_server.py"), 'pi_combined_server.py')
  sftp.close()

  # Find and KILLL the existing server process, then start a new one.
  stdin, stdout, stderr = ssh.exec_command("lsof -ti :5000")
  pids = stdout.read().decode().strip().splitlines()

  for pid in pids:
    print(f"Killed server running at :5000, PID: {pid}")
    ssh.exec_command(f"kill -9 {pid}")
  
  # ONLY USE FOR DEBUGGING
  stdin, stdout, stderr = ssh.exec_command("python3 pi_combined_server.py")
  print(stdout.read().decode())
  print(stderr.read().decode())
  
  # Start the new server in the BACKGROUND, redirecting output to a log file.
  # stdin, stdout, stderr = ssh.exec_command("nohup python3 pi_combined_server.py > server.log 2>&1 &")
  # print("Server started in the background.")
  ssh.close()

  """ 
  Connecting to the command server and sending commands. 
  """
  client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  def connect_to_server():
    try:
      client.connect((HOST, MAIN_PORT))
      # cam_client_thread = threading.Thread(target=run_camera_client, args=(stop_event,))
      # cam_client_thread.start()
      start_hud()
      
      print("Connected to robot.")
    except Exception as e:
      print("Failed to connect to robot: {}".format(e))
      return False
    return True
  
  return connect_to_server()  
    
def run_camera_client(stop_event):
  pipeline = (
    f"udpsrc port={STREAM_PORT} buffer-size=65536 ! "
    "application/x-rtp, encoding-name=H264, payload=96 ! "
    "rtph264depay ! "
    "avdec_h264 ! "  # Replace with nvh264dec for Linux NVIDIA GPU decoding, or vaapih264dec for Linux Intel GPU decoding
    "videoconvert ! "
    "appsink sync=false max-buffers=1 drop=true"
  )

  cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

  if not cap.isOpened():
      print("Failed to open GStreamer UDP pipeline on this machine.")
      print("Install OpenCV with GStreamer support and verify GStreamer is installed.")
      full_exit()

  while not stop_event.is_set():
    try:
      ret, frame = cap.read()
      if not ret:
          continue

      # result = my_algorithm(frame)

      cv2.imshow("video", frame)

      if cv2.waitKey(1) == 27:
          break
    except Exception as e:
      print("Error reading video frame: {}".format(e))
      full_exit()

def start_hud():
  pygame.init()
  
  def lerp(a, b, t): 
      return a + (b - a) * t

  PWM_PIN = 14
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
    
    # pi.set_servo_pulsewidth(PWM_PIN, pulse_width)
  
  CLOCK = pygame.time.Clock()
  SCREEN = pygame.display.set_mode((800, 800))
  
  while True:
    for event in pygame.event.get():
      delta = CLOCK.tick(60)
      if event.type == pygame.QUIT:
        pygame.quit()
        full_exit()
        
      ''' Handle input '''
      keys = pygame.key.get_pressed()
      a = int(keys[pygame.K_a])
      d = int(keys[pygame.K_d])
      left_y = -a + d
      
      # action_value = Input.get_action_held('move')
      
      wanted_pulse_width = 1500 + (-500 * left_y)
      pulse_width = lerp(pulse_width, wanted_pulse_width, 0.1)  # Smoothly interpolate towards the target pulse width
      
      safe_set_motor_speed(pulse_width)
        
      SCREEN.fill((200, 50, 50))
      pygame.display.update()

retrys = 0
while not main_client(retrys):
  retrys += 1