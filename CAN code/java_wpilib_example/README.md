Java WPILib Victor SPX Smoke Test
=================================

Goal
----
Use this Java/WPILib test to verify CAN wiring, CAN ID, and Victor SPX hardware independent of the Python server.

What this test does
-------------------
- Uses a Victor SPX on CAN.
- Runs a repeating output pattern whenever the robot is enabled:
  - 2 seconds forward at +0.25
  - 1 second stop
  - 2 seconds reverse at -0.25
  - 1 second stop

Files
-----
- Robot.java (drop-in replacement for src/main/java/frc/robot/Robot.java)

Setup steps (WPILib)
--------------------
1. Create a new WPILib Java project (TimedRobot template).
2. Install the CTRE Phoenix 5 vendor library in that project.
   - Victor SPX uses Phoenix 5 APIs.
3. Replace the generated Robot.java with the Robot.java in this folder.
4. Set VICTOR_CAN_ID in Robot.java to match your controller's CAN ID.
5. Deploy code to the roboRIO.
6. Enable the robot in Teleop or Autonomous.

Expected behavior
-----------------
- Motor repeatedly moves forward, stops, reverses, then stops.
- SmartDashboard entries under VictorSmokeTest show output and phase updates.

How to use for troubleshooting
------------------------------
- If this Java test works but Python does not:
  - CAN bus, motor controller, and basic motor configuration are likely good.
  - Focus next on Python dependencies, Python runtime on target, and socket command path.
- If this Java test also fails:
  - Check power wiring, CAN wiring order/termination, CAN ID conflicts, and Phoenix installation.

Safety
------
- Keep wheels/chains off the ground while testing.
- Use low output values first.
- Disable robot immediately if direction/output is unexpected.
