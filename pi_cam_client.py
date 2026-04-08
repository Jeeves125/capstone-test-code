import cv2
import sys
import socket

# RUN THIS FROM THE COMPUTER.
# This is the camera client: it receives the Orange Pi camera stream over UDP.
# Pipeline settings are kept the same to preserve transmission efficiency.

SERVER_HOST = "192.168.4.1"
STREAM_PORT = 5000
CONTROL_PORT = 5001

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
    sys.exit(1)

# Lightweight registration so the server learns where to send the stream.
control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(3):
    control_sock.sendto(b"camera_client_ready", (SERVER_HOST, CONTROL_PORT))
control_sock.close()

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    # result = my_algorithm(frame)

    cv2.imshow("video", frame)

    if cv2.waitKey(1) == 27:
        break