import socket
import time
import glob
import math
import struct

import cv2

# RUN THIS FROM THE ORANGE PI.
# This is the camera server: it captures frames from the connected USB webcam and sends them to the client.
# The client receives chunked JPEG frames over UDP.

STREAM_PORT = 5000
CONTROL_PORT = 5001
WEBCAM_DEVICE = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 360
CAMERA_FPS = 20
JPEG_QUALITY = 60
UDP_MAGIC = b"FRM2"
UDP_HEADER = struct.Struct("!4sBIHH")
MAX_UDP_CHUNK_BYTES = 1200


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

client_address = (client_host, STREAM_PORT)

print(f"Client registered from {client_host}. Waiting for video connection on UDP {STREAM_PORT}...")

camera = open_webcam_capture()

camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
frame_sequence = 0

print(f"Starting UDP video stream to {client_address[0]}:{client_address[1]}...")

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
        if not payload:
            continue

        chunk_count = max(1, math.ceil(len(payload) / MAX_UDP_CHUNK_BYTES))
        send_failed = False
        for chunk_index in range(chunk_count):
            start = chunk_index * MAX_UDP_CHUNK_BYTES
            chunk = payload[start:start + MAX_UDP_CHUNK_BYTES]
            packet = UDP_HEADER.pack(UDP_MAGIC, 0, frame_sequence, chunk_index, chunk_count) + chunk

            try:
                video_sock.sendto(packet, client_address)
            except Exception:
                send_failed = True
                break

        frame_sequence = (frame_sequence + 1) % 0xFFFFFFFF
        if send_failed:
            continue
except KeyboardInterrupt:
    pass
finally:
    try:
        camera.release()
    except Exception:
        pass
    try:
        video_sock.close()
    except Exception:
        pass