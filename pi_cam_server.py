from picamera2 import Picamera2
import subprocess
import socket

# RUN THIS FROM THE ORANGE PI.
# This is the camera server: it captures camera frames and sends them to the client.
# Pipeline settings are kept the same to preserve transmission efficiency.

STREAM_PORT = 5000
CONTROL_PORT = 5001

print(f"Waiting for camera client registration on UDP {CONTROL_PORT}...")

control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
control_sock.bind(("", CONTROL_PORT))
_, (client_host, _) = control_sock.recvfrom(1024)
control_sock.close()

print(f"Client registered from {client_host}. Starting stream...")

pipeline = [
    "gst-launch-1.0",
    "fdsrc",
    "!",
    "h264parse",
    "config-interval=1",
    "!",
    "rtph264pay",
    "pt=96",
    "!",
    f"udpsink host={client_host} port={STREAM_PORT} sync=false"
]

gst = subprocess.Popen(pipeline, stdin=subprocess.PIPE)

picam2 = Picamera2()

config = picam2.create_video_configuration(
    main={"size": (1280, 720)},
    controls={"FrameRate": 30}
)

picam2.configure(config)
picam2.start()

picam2.start_recording("h264", gst.stdin)