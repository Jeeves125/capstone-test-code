Do not use an Ad Hoc connection, make the PI a Wi-Fi access point instead.

## Camera scripts by machine

- `pi_cam_client.py` runs on the Raspberry Pi (Linux only) and sends camera frames over UDP.
- `pi_cam_server.py` runs on your Windows/Linux computer and receives/displays UDP camera frames.

## Install commands

Raspberry Pi (sender):

```bash
python -m pip install --upgrade pip
python -m pip install picamera2
```

Windows laptop/desktop (receiver):

```powershell
python -m pip install --upgrade pip
python -m pip install opencv-python
```

Do not install `picamera2` on Windows; one of its dependencies (`python-prctl`) is Linux-only.