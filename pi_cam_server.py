import socket
import time
import glob

import cv2

# RUN THIS FROM THE ORANGE PI.
# This is the camera server: it captures frames from the connected USB webcam and sends them to the client.
# The client receives an MPEG-TS over UDP stream.

STREAM_PORT = 5000
CONTROL_PORT = 5001
WEBCAM_DEVICE = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360
CAMERA_FPS = 20
JPEG_QUALITY = 60
VIDEO_FRAME_SIZE_BYTES = 4


def open_webcam_capture():
    candidate_devices = [0, 1, 2, 3, 4, 5]
    candidate_devices.extend(sorted(glob.glob("/dev/video*")))

    seen_candidates = []
    for candidate in candidate_devices:
        if candidate in seen_candidates:
            continue
        seen_candidates.append(candidate)

        print(f"Trying webcam device: {candidate}")

        if isinstance(candidate, int):
            capture = cv2.VideoCapture(candidate, cv2.CAP_V4L2)
        else:
            capture = cv2.VideoCapture(candidate, cv2.CAP_V4L2)
        
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if capture.isOpened():
            print(f"Using webcam device: {candidate}")
            return capture

        capture.release()

    raise RuntimeError("Failed to open any webcam device")

print(f"Waiting for camera client registration on UDP {CONTROL_PORT}...")

control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
control_sock.bind(("", CONTROL_PORT))
_, (client_host, _) = control_sock.recvfrom(1024)
control_sock.close()

print(f"Client registered from {client_host}. Waiting for video connection on TCP {STREAM_PORT}...")

camera = open_webcam_capture()

camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

video_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
video_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
video_server.bind(("0.0.0.0", STREAM_PORT))
video_server.listen(1)
video_server.settimeout(1.0)

video_client = None

while video_client is None:
    try:
        video_client, video_address = video_server.accept()
        print(f"Video client connected from {video_address[0]}. Starting stream...")
    except socket.timeout:
        continue

try:
    while True:
        ok, frame = camera.read()
        if not ok:
            time.sleep(0.01)
            continue

        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
        if not ok:
            continue

        payload = encoded.tobytes()
        video_client.sendall(len(payload).to_bytes(VIDEO_FRAME_SIZE_BYTES, byteorder="big"))
        video_client.sendall(payload)
except KeyboardInterrupt:
    pass
finally:
    try:
        camera.release()
    except Exception:
        pass
    try:
        if video_client is not None:
            video_client.close()
    except Exception:
        pass
    try:
        video_server.close()
    except Exception:
        pass