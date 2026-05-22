import socket, pygame, threading, paramiko, os
import sys
import time

import cv2
import numpy as np

from calibrated_depth_mapper import CalibratedStereoDepthMapper

USER = "robot"
PASSWORD = "robot"
HOST = "192.168.10.80"
MAIN_PORT = 5000
STREAM_PORT = 5001
client: socket.socket = None
video_client: socket.socket = None

depth_mapper = CalibratedStereoDepthMapper()

stop_event = threading.Event()

def full_exit():
  if client != None:
    client.close()
  if video_client != None:
    video_client.close()
  stop_event.set()
  # Grab the logs for the current session before exiting.
  print("Trying to fetch logs from robot before exiting...")
  try: 
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD)
    
    # Open the secure file transfer.
    sftp = ssh.open_sftp()
    # sftp.put(os.path.join(os.getcwd(), "robot_code", "test_code.py"), 'test_code.py')
    sftp.get('server.log', os.path.join(os.getcwd(), "robot_code", "server.log"))
    # print("Fetched server logs from robot")
    sftp.close()
    ssh.close()
    print("Fetched server logs from robot, exiting now.")
  except Exception as e:
    print("Failed to fetch logs from robot: {}".format(e))
  
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
  sftp.put(os.path.join(os.getcwd(), "pi_cam_server.py"), "pi_cam_server.py")
  # sftp.put(os.path.join(os.getcwd(), "robot_code", "test_code.py"), 'test_code.py')
  sftp.get('server.log', os.path.join(os.getcwd(), "robot_code", "server.log"))
  # print("Fetched server logs from robot")
  sftp.close()

  # Find and KILLL the existing server process, then start a new one.
  stdin, stdout, stderr = ssh.exec_command("sudo lsof -ti :5000")
  pids = stdout.read().decode().strip().splitlines()

  for pid in pids:
    print(f"Killed server running at :5000, PID: {pid}")
    ssh.exec_command(f"sudo kill -9 {pid}")
    
  stdin, stdout, stderr = ssh.exec_command("sudo lsof -ti :5001")
  pids = stdout.read().decode().strip().splitlines()

  for pid in pids:
    print(f"Killed server running at :5001, PID: {pid}")
    ssh.exec_command(f"sudo kill -9 {pid}")
  
  # ONLY USE FOR DEBUGGING
  # stdin, stdout, stderr = ssh.exec_command("python3 pi_combined_server.py")
  # print(stdout.read().decode())
  # print(stderr.read().decode())
  
  # Start the new server in the BACKGROUND, redirecting output to a log file.
  stdin, stdout, stderr = ssh.exec_command("nohup sudo python3 pi_combined_server.py")
  print("Server started in the background.")
  ssh.close()

  """ 
  Connecting to the command server and sending commands. 
  """
  client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  def connect_to_server():
    try:
      client.connect((HOST, MAIN_PORT))
      print("Connected to robot.")
      cam_client_thread = threading.Thread(target=run_camera_client, args=(stop_event,))
      cam_client_thread.start()
      start_hud()
      
    except Exception as e:
      print("Failed to connect to robot: {}".format(e))
      return False
    return True
  
  return connect_to_server()  
    
def run_camera_client(stop_event):
  global video_client
  connect_error = None
  for attempt in range(50):
    try:
      video_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      video_client.settimeout(1.0)
      video_client.connect((HOST, STREAM_PORT))
      break
    except Exception as e:
      connect_error = e
      try:
        video_client.close()
      except Exception:
        pass
      video_client = None
      time.sleep(0.1)
  else:
    print("Failed to connect to video stream: {}".format(connect_error))
    full_exit()

  def recv_exact(sock, size):
    chunks = []
    received = 0
    while received < size:
      chunk = sock.recv(size - received)
      if not chunk:
        return None
      chunks.append(chunk)
      received += len(chunk)
    return b"".join(chunks)

  try:
    while not stop_event.is_set():
      try:
        frames = [None, None]
        for i in range(2):
          header = recv_exact(video_client, 4)
          if header is None:
            break
          frame_size = int.from_bytes(header, byteorder="big")
          packet = recv_exact(video_client, frame_size)
          if packet is None:
            break

          frame_array = np.frombuffer(packet, dtype=np.uint8)
          frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
          if frame is None:
              continue
          frames[i] = frame

        # depth_map = depth_mapper.run(frames[0], frames[1], 1) if all(f is not None for f in frames) else None
    
        print("Recieved following frames from robot: {}".format("Frames received" if all(f is not None for f in frames) else "Missing frames"))

        if frames[0] is not None and frames[1] is not None:
          combined = np.hstack((frames[0], frames[1]))
          cv2.imshow("video", combined)

        if cv2.waitKey(1) == 27:
            break
      except Exception as e:
        if isinstance(e, socket.timeout):
          continue
        print("Error reading video frame: {}".format(e))
        full_exit()
  finally:
    try:
      video_client.close()
    except Exception:
      pass
    cv2.destroyAllWindows()

PWM_PIN = 14
wanted_pulse_width = 1500  # Neutral pulse width for ESC (Electronic Speed Controller)
pulse_width = 1500  # Neutral pulse width for ESC (Electronic Speed Controller)

_pulse_width = 1500  # Actual pulse width variable that will be updated smoothly and safely
_max_delta = 50  # Maximum change in pulse width per frame to ensure smooth acceleration/deceleration

def start_hud():
  global _pulse_width, _max_delta, pulse_width, wanted_pulse_width
  pygame.init()
  
  def lerp(a, b, t): 
      return a + (b - a) * t

  def get_safe_motor_speed(pw):
    global _pulse_width
    delta = pw - _pulse_width
    
    if (delta > 0 and _pulse_width < 1500) or (delta < 0 and _pulse_width > 1500):
        _pulse_width = 1500  # Snap to the neutral point if crossing it
        return 1500
    if (delta > 0 and _pulse_width >= 1500) or (delta < 0 and _pulse_width <= 1500):
        sign_delta = 1 if delta > 0 else -1
        delta = min(abs(delta), _max_delta) * sign_delta  # Limit the delta to max_delta while preserving the sign
        _pulse_width += delta
        
    # print(f"Pulse Width: {_pulse_width:.2f}")
    return _pulse_width
    
    # pi.set_servo_pulsewidth(PWM_PIN, pulse_width)
  
  CLOCK = pygame.time.Clock()
  SCREEN = pygame.display.set_mode((800, 800))
  FONT = pygame.font.SysFont("Arial", 24)
  
  JOYSTICK = pygame.joystick.Joystick(0) if pygame.joystick.get_count() > 0 else None
  
  while True:
    delta = CLOCK.tick(10)
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        pygame.quit()
        full_exit()
      
      if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_SEMICOLON:
          client.send("LOGS\n".encode())
          log_bytes = int(client.recv(1024).decode())  # Wait for acknowledgment
          log_data = client.recv(log_bytes).decode()  # Receive the actual log data
          with open(os.path.join(os.getcwd(), "robot_code", "server.log"), "w") as f:
            f.write(log_data)
            
        if event.key == pygame.K_l:
          client.send("CLEAR_LOGS\n".encode())
          
        if event.key == pygame.K_0:
          client.send("STOP\n".encode())
        if event.key == pygame.K_1:
          client.send("CALIBRATE_UP_PIN1\n".encode())
        if event.key == pygame.K_2:
          client.send("CALIBRATE_DOWN_PIN1\n".encode())
        if event.key == pygame.K_3:
          client.send("CALIBRATE_UP_PIN2\n".encode())
        if event.key == pygame.K_4:
          client.send("CALIBRATE_DOWN_PIN2\n".encode())

      # Handle continuous key state every frame so neutral is always transmitted.
      if (JOYSTICK != None):
        left_y = round(-JOYSTICK.get_axis(1) * 4)  # Invert Y-axis for typical joystick behavior
        right_y = round(-JOYSTICK.get_axis(4) * 4)  # Invert Y-axis for typical joystick behavior
        # print(left_y)
        pulse_width_1 = 1500 + (-50 * left_y)
        pulse_width_2 = 1500 + (-50 * right_y)
        pulse_width_text = FONT.render(f"USING JOYSTICK: Pulse Width 1: {pulse_width_1:.2f}, Pulse Width 2: {pulse_width_2:.2f}", True, (255, 255, 255))
        client.send(("PWMONE" + str(int(pulse_width_1)) + "\n").encode())
        client.send(("PWMTWO" + str(int(pulse_width_2)) + "\n").encode())
        SCREEN.fill((200, 50, 50))
        SCREEN.blit(pulse_width_text, (20, 20))
      else:
        keys = pygame.key.get_pressed()
        a = int(keys[pygame.K_a])
        d = int(keys[pygame.K_d])
        left_y = -a + d

        wanted_pulse_width = 1500 + (-300 * left_y)
        pulse_width = lerp(pulse_width, wanted_pulse_width, 1)  # Smoothly interpolate towards the target pulse width

        pulse_width_text = FONT.render(f"USING KEYS: Pulse Width: {pulse_width:.2f}", True, (255, 255, 255))
        client.send(("PWMONE" + str(int(pulse_width)) + "\n").encode())

        SCREEN.fill((200, 50, 50))
        SCREEN.blit(pulse_width_text, (20, 20))

      pygame.display.update()

retrys = 0
while not main_client(retrys):
  retrys += 1