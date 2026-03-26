import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('0.0.0.0', 5001))
server.listen(1)

client_socket, client_address = None, None

def client_connect():
  global client_socket, client_address
  print("Waiting for a controller to connect...")
  client_socket, client_address = server.accept()
  
def process_command(command):
  global client_socket, client_address
  
  # Placeholder for command processing logic
  print("Processing command: {}".format(command))
  
  if command == "EXIT":
    print("Received EXIT command. Closing connection.")
    client_socket.close()
    client_socket, client_address = None, None
    
print("Server is listening on port 5001...")
while True:
  if client_socket == None or client_address == None:
    client_connect()
    continue
  
  try:
    command = client_socket.recv(1024).decode()
    print("Received command from {}:{}".format(client_address[0], client_address[1]))
    process_command(command)
    
  except Exception as e:
    print("Error processing command: {}".format(e))
    client_socket.close()
    client_socket, client_address = None, None