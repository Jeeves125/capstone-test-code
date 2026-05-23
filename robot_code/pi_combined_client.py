import socket, pygame, threading, paramiko, os
import sys
import time
import struct

import cv2
import numpy as np

from calibrated_depth_mapper import CalibratedStereoDepthMapper

pygame.init()

USER = "robot"
PASSWORD = "robot"
HOST = "192.168.10.80"
MAIN_PORT = 5000
STREAM_PORT = 5001
UDP_MAGIC = b"FRM2"
UDP_HEADER = struct.Struct("!4sBIHH")
MAX_PENDING_SECONDS = 1.0

CLOCK = pygame.time.Clock()
SCREEN = pygame.display.set_mode((800, 800))
FONT = pygame.font.SysFont("Arial", 24)
JOYSTICK = pygame.joystick.Joystick(0) if pygame.joystick.get_count() > 0 else None

client: socket.socket = None
video_client: socket.socket = None

depth_mapper = CalibratedStereoDepthMapper("stereo_calibration_refined")

stop_event = threading.Event()

def full_exit():
  if stop_event.is_set():
    return
  
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
  try:
    video_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    video_client.bind(("", STREAM_PORT))
    video_client.settimeout(1.0)
  except Exception as e:
    print("Failed to open UDP video socket: {}".format(e))
    full_exit()

  pending_frames = {}

  def cleanup_pending():
    now = time.monotonic()
    expired = [seq for seq, entry in pending_frames.items() if now - entry["created_at"] > MAX_PENDING_SECONDS]
    for seq in expired:
      pending_frames.pop(seq, None)

  def decode_ready_pair():
    for frame_sequence in sorted(pending_frames):
      entry = pending_frames[frame_sequence]
      left_entry = entry.get(0)
      right_entry = entry.get(1)
      if not left_entry or not right_entry:
        continue
      if len(left_entry["chunks"]) != left_entry["chunk_count"] or len(right_entry["chunks"]) != right_entry["chunk_count"]:
        continue

      left_payload = b"".join(left_entry["chunks"][chunk_index] for chunk_index in range(left_entry["chunk_count"]))
      right_payload = b"".join(right_entry["chunks"][chunk_index] for chunk_index in range(right_entry["chunk_count"]))
      pending_frames.pop(frame_sequence, None)
      return left_payload, right_payload

    return None

  try:
    while not stop_event.is_set():
      try:
        packet, _ = video_client.recvfrom(2048)
      except socket.timeout:
        cleanup_pending()
        continue
      except Exception as e:
        print("Error reading video frame: {}".format(e))
        full_exit()

      if len(packet) < UDP_HEADER.size:
        continue

      magic, stream_id, frame_sequence, chunk_index, chunk_count = UDP_HEADER.unpack(packet[:UDP_HEADER.size])
      if magic != UDP_MAGIC or stream_id not in (0, 1) or chunk_count == 0 or chunk_index >= chunk_count:
        continue

      entry = pending_frames.setdefault(frame_sequence, {
        "created_at": time.monotonic(),
        0: None,
        1: None,
      })

      stream_entry = entry.get(stream_id)
      if stream_entry is None:
        entry[stream_id] = {
          "chunk_count": chunk_count,
          "chunks": {},
        }
      elif stream_entry["chunk_count"] != chunk_count:
        pending_frames.pop(frame_sequence, None)
        continue

      entry[stream_id]["chunks"][chunk_index] = packet[UDP_HEADER.size:]

      ready_pair = decode_ready_pair()
      if ready_pair is None:
        continue

      left_payload, right_payload = ready_pair
      left_frame_array = np.frombuffer(left_payload, dtype=np.uint8)
      right_frame_array = np.frombuffer(right_payload, dtype=np.uint8)
      left_frame = cv2.imdecode(left_frame_array, cv2.IMREAD_COLOR)
      right_frame = cv2.imdecode(right_frame_array, cv2.IMREAD_COLOR)
      if left_frame is None or right_frame is None:
        continue

      depth_surface, data = depth_mapper.run(left_frame, right_frame, 1)
      SCREEN.fill((50, 200, 50))
      if depth_surface is not None:
        SCREEN.blit(depth_surface, (0, 0))
        pygame.display.update()
      # print("Recieved following frames from robot: {}".format("Frames received" if all(f is not None for f in frames) else "Missing frames"))

      combined = np.hstack((left_frame, right_frame))
      cv2.imshow("video", combined)

      if cv2.waitKey(1) == 27:
        break
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
        if event.key == pygame.K_t:
            print("Running auto-tune on current frame...")
            ok = depth_mapper.auto_tune_on_frame()
            if ok:
                print("Auto-tune applied — new matcher active.")
        if event.key == pygame.K_u:
            print("Running FULL auto-tune (expanded grid) on current frame... this may take a while")
            ok = depth_mapper.auto_tune_full()
            if ok:
                print("Full auto-tune applied — new matcher active.")
        if event.key == pygame.K_r:
            print("Running ROI-focused auto-tune on current frame...")
            ok = depth_mapper.auto_tune_roi(size_frac=0.5)
            if ok:
                print("ROI auto-tune applied — new matcher active.")
        if event.key == pygame.K_e:
            depth_mapper.ensemble_enabled = not depth_mapper.ensemble_enabled
            print(f"Ensemble matching {'enabled' if depth_mapper.ensemble_enabled else 'disabled'}")
        if event.key == pygame.K_m:
            depth_mapper.temporal_median_enabled = not depth_mapper.temporal_median_enabled
            print(f"Temporal median {'enabled' if depth_mapper.temporal_median_enabled else 'disabled'} (size={depth_mapper.temporal_median_size})")

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

        # SCREEN.fill((200, 50, 50))
        # SCREEN.blit(pulse_width_text, (20, 20))

      pygame.display.update()

retrys = 0
while not main_client(retrys):
  retrys += 1