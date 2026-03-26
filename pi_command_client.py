import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
def connect_to_server():
  try:
    client.connect(('localhost', 5001))
    print("Connected to server.")
  except Exception as e:
    print("Failed to connect to server: {}".format(e))