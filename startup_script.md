sudo nano /etc/systemd/system/myscript.service

# Put this in the service file.
[Unit]
Description=My Startup Script Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/myscript.sh

[Install]
WantedBy=multi-user.target

# Give the files permission, reload the system daemon.
sudo chmod 644 /etc/systemd/system/myscript.service
sudo systemctl daemon-reload

# Enable and start the program.
sudo systemctl enable myscript.service
sudo systemctl start myscript.service
