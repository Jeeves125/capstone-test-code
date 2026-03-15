import cv2
import sys

# RUN THIS FROM THE COMPUTER
# This runs a server listening for the PI's video stream.
# Uses h264 encoding and GStreamer to receive the video feed from the PI and display it using OpenCV.

pipeline = (
"udpsrc port=5000 buffer-size=65536 ! "
"application/x-rtp, encoding-name=H264, payload=96 ! "
"rtph264depay ! "
"avdec_h264 ! " # Replace with nvh264dec for Linux NVIDIA GPU decoding, or vaapih264dec for Linux Intel GPU decoding
"videoconvert ! "
"appsink sync=false max-buffers=1 drop=true"
)

cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("Failed to open GStreamer UDP pipeline on this machine.")
    print("Install OpenCV with GStreamer support and verify GStreamer is installed.")
    sys.exit(1)

while True:

    ret, frame = cap.read()
    if not ret:
        continue

    # result = my_algorithm(frame)

    cv2.imshow("video", frame)

    if cv2.waitKey(1) == 27:
        break