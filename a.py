import sys

original_stdout = sys.stdout

with open("requirements.txt", 'w') as f:
  sys.stdout = f
  print("paramiko")
  print("pygame")
  print("opencv-python")

sys.stdout = original_stdout