import socket, subprocess, os

user = "jeeves"
address = "192.168.4.1"

""" 
Connecting to the robot and making sure that the command server is running. 
"""
# Or use -r for recursive copy
os.system(f"scp /robot_code/pi_command_server.py {user}@{address}:/robot_code/")
os.system(f"scp /robot_code/pi_cam_server.py {user}@{address}:/robot_code/")

command_server_ssh = subprocess.Popen(["ssh", "-tt", f"{user}@{address}"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

command_server_ssh.stdin.write("cd /robot_code")
command_server_ssh.stdin.write("python3 pi_command_server.py\n")
command_server_ssh.stdin.close()

command_server_ssh_output = command_server_ssh.stdout.read()


""" 
Connecting to the command server and sending commands. 
"""
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
def connect_to_server():
  try:
    client.connect(('localhost', 5000))
    print("Connected to robot.")
  except Exception as e:
    print("Failed to connect to robot: {}".format(e))