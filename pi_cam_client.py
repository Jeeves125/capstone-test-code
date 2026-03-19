from picamera2 import Picamera2
import subprocess

# RUN THIS FROM THE PI.
# It should connect to the server running on the other computer connected to the PI's wifi access point.
# Then, using h264 encoding, it will stream the video feed from the camera to the server using GStreamer.

HOST = "192.168.4.2"
PORT = 5000

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
    f"udpsink host={HOST} port={PORT} sync=false"
]

gst = subprocess.Popen(pipeline, stdin=subprocess.PIPE)

picam2 = Picamera2()

config = picam2.create_video_configuration(
    main={"size": (1280,720)},
    controls={"FrameRate":30}
)

picam2.configure(config)
picam2.start()

picam2.start_recording("h264", gst.stdin)