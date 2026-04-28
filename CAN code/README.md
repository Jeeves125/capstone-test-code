CAN Command Server (Victor SPX)
================================

This folder contains a TCP server that receives command messages from a client and applies motor output to a VEX/CTRE Victor SPX over CAN.

Files
-----
- can_command_server.py
- can_command_client_example.py
- java_wpilib_example/Robot.java
- java_wpilib_example/README.md

Python Dependency
-----------------
Install RobotPy CTRE on the target robot controller environment:

pip install robotpy-ctre

This project uses the Phoenix 5 API exposed through the phoenix5 package.

If you only want to test networking and parsing without hardware:

python can_command_server.py --simulate

Run Server
----------
Default port is 5003 and default CAN ID is 1.

python can_command_server.py --can-id 1 --port 5003

Run Client Example
------------------
python can_command_client_example.py --host 127.0.0.1 --port 5003

Command Protocol
----------------
Send one UTF-8 command per line:

- PING
- STATUS
- STOP
- SET <value>   where value is -1.0 to 1.0
- FWD <value>   where value is 0.0 to 1.0
- REV <value>   where value is 0.0 to 1.0
- QUIT          close one client connection
- SHUTDOWN      stop motor and shut down server

Notes
-----
- Server includes idle safety: if no command arrives for 0.75 seconds, motor output is forced to 0.
- You can tune this with --idle-timeout.
- For safety, the server always sets motor output to 0 during shutdown.

Java WPILib Fallback Test
-------------------------
If you want to independently verify Victor SPX hardware and CAN bus health with official FRC tooling,
see java_wpilib_example/README.md and java_wpilib_example/Robot.java.
