import cv2
import sys
import socket
import time
import struct

# RUN THIS FROM THE COMPUTER.
# This is the camera client: it receives the Orange Pi camera stream over UDP.
# Pipeline settings are kept the same to preserve transmission efficiency.

SERVER_HOST = "192.168.4.1"
STREAM_PORT = 5000
CONTROL_PORT = 5001
UDP_MAGIC = b"FRM2"
UDP_HEADER = struct.Struct("!4sBIHH")
MAX_PENDING_SECONDS = 1.0

control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
stream_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
stream_sock.bind(("", STREAM_PORT))
stream_sock.settimeout(1.0)

for _ in range(3):
    control_sock.sendto(b"camera_client_ready", (SERVER_HOST, CONTROL_PORT))
control_sock.close()

pending_frames = {}

def cleanup_pending():
    now = time.monotonic()
    expired = [seq for seq, entry in pending_frames.items() if now - entry["created_at"] > MAX_PENDING_SECONDS]
    for seq in expired:
        pending_frames.pop(seq, None)

def get_completed_frame():
    for frame_sequence in sorted(pending_frames):
        entry = pending_frames[frame_sequence]
        if len(entry["chunks"]) == entry["chunk_count"]:
            payload = b"".join(entry["chunks"][chunk_index] for chunk_index in range(entry["chunk_count"]))
            pending_frames.pop(frame_sequence, None)
            return payload
    return None

try:
    while True:
        try:
            packet, _ = stream_sock.recvfrom(2048)
        except socket.timeout:
            cleanup_pending()
            continue

        if len(packet) < UDP_HEADER.size:
            continue

        magic, stream_id, frame_sequence, chunk_index, chunk_count = UDP_HEADER.unpack(packet[:UDP_HEADER.size])
        if magic != UDP_MAGIC or stream_id != 0 or chunk_count == 0 or chunk_index >= chunk_count:
            continue

        entry = pending_frames.setdefault(frame_sequence, {
            "created_at": time.monotonic(),
            "chunk_count": chunk_count,
            "chunks": {},
        })
        if entry["chunk_count"] != chunk_count:
            pending_frames.pop(frame_sequence, None)
            continue

        entry["chunks"][chunk_index] = packet[UDP_HEADER.size:]
        frame_bytes = get_completed_frame()
        if frame_bytes is None:
            continue

        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        cv2.imshow("video", frame)

        if cv2.waitKey(1) == 27:
            break
finally:
    try:
        stream_sock.close()
    except Exception:
        pass
    cv2.destroyAllWindows()