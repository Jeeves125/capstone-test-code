"""Capture synchronized calibration image pairs from two cameras.

Usage:
    python capture_calibration_pairs.py --left 0 --right 1 --out calibration_pairs --count 20

Press SPACE to capture a pair, 'q' to quit.
"""
import cv2
import os
import argparse
import platform
from datetime import datetime


def backend_from_name(name):
    backend_name = (name or "auto").lower()
    if backend_name == "auto":
        system = platform.system().lower()
        if system.startswith("win"):
            return cv2.CAP_DSHOW
        if system.startswith("linux"):
            return cv2.CAP_V4L2
        return None
    if backend_name == "any":
        return None
    if backend_name == "dshow":
        return cv2.CAP_DSHOW
    if backend_name == "msmf":
        return cv2.CAP_MSMF
    if backend_name == "v4l2":
        return cv2.CAP_V4L2
    if backend_name == "gstreamer":
        return cv2.CAP_GSTREAMER
    if backend_name == "ffmpeg":
        return cv2.CAP_FFMPEG
    raise ValueError(f"Unsupported backend '{name}'")


def parse_camera_source(raw):
    text = str(raw).strip()
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return text


def source_for_backend(source, backend):
    if backend == cv2.CAP_FFMPEG:
        if isinstance(source, int):
            return f"v4l2:/dev/video{source}"
        source_text = str(source)
        if source_text.startswith("/dev/video"):
            return f"v4l2:{source_text}"
    return source

parser = argparse.ArgumentParser()
parser.add_argument('--left', type=str, default='0')
parser.add_argument('--right', type=str, default='1')
parser.add_argument('--out', type=str, default='calibration_pairs')
parser.add_argument('--format', type=str, default='none', choices=['none', 'mjpg'])
parser.add_argument('--count', type=int, default=20)
parser.add_argument('--width', type=int, default=640)
parser.add_argument('--height', type=int, default=480)
parser.add_argument('--backend', type=str, default='auto', choices=['auto', 'any', 'dshow', 'msmf', 'v4l2', 'gstreamer', 'ffmpeg'])
args = parser.parse_args()

backend = backend_from_name(args.backend)
left_src = parse_camera_source(args.left)
right_src = parse_camera_source(args.right)
left_src = source_for_backend(left_src, backend)
right_src = source_for_backend(right_src, backend)
format = args.format.lower()

os.makedirs(args.out, exist_ok=True)

if backend is None:
    capL = cv2.VideoCapture(left_src)
    capR = cv2.VideoCapture(right_src)
else:
    capL = cv2.VideoCapture(left_src, backend)
    capR = cv2.VideoCapture(right_src, backend)
for cap in (capL, capR):
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if format == 'mjpg':
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

count = 0
print('Press SPACE to capture synchronized pair. Press q to quit.')
while True:
    retL, frameL = capL.read()
    retR, frameR = capR.read()
    if not (retL and retR):
        print('Error reading from cameras')
        break

    # Side-by-side preview
    vis = cv2.hconcat([cv2.resize(frameL, (320,240)), cv2.resize(frameR, (320,240))])
    cv2.putText(vis, f'Pairs: {count}/{args.count}', (10,20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255),2)
    cv2.imshow('Stereo Capture (SPACE to save pair)', vis)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    # if key == ord(' '):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    left_name = os.path.join(args.out, f'left_{ts}.png')
    right_name = os.path.join(args.out, f'right_{ts}.png')
    cv2.imwrite(left_name, frameL)
    cv2.imwrite(right_name, frameR)
    count += 1
    print(f'Saved pair {count}:', left_name, right_name)
    if count >= args.count:
        print('Captured requested number of pairs.')
        break

capL.release()
capR.release()
cv2.destroyAllWindows()
