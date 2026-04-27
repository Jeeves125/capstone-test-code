package frc.robot;

import com.ctre.phoenix.motorcontrol.ControlMode;
import com.ctre.phoenix.motorcontrol.NeutralMode;
import com.ctre.phoenix.motorcontrol.can.VictorSPX;
import edu.wpi.first.wpilibj.TimedRobot;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;

/**
 * Victor SPX CAN smoke test.
 *
 * Copy this file into a standard WPILib Java TimedRobot project at src/main/java/frc/robot/Robot.java.
 */
public class Robot extends TimedRobot {
  private static final int VICTOR_CAN_ID = 1;
  private static final double FORWARD_OUTPUT = 0.25;
  private static final double REVERSE_OUTPUT = -0.25;

  private static final double CYCLE_SECONDS = 6.0;
  private static final double FORWARD_END_SECONDS = 2.0;
  private static final double REVERSE_START_SECONDS = 3.0;
  private static final double REVERSE_END_SECONDS = 5.0;

  private final VictorSPX motor = new VictorSPX(VICTOR_CAN_ID);
  private final Timer testTimer = new Timer();

  @Override
  public void robotInit() {
    motor.configFactoryDefault();
    motor.setNeutralMode(NeutralMode.Brake);
    motor.setInverted(false);
    motor.set(ControlMode.PercentOutput, 0.0);

    SmartDashboard.putString("VictorSmokeTest/Status", "Initialized");
    SmartDashboard.putNumber("VictorSmokeTest/CAN_ID", VICTOR_CAN_ID);
    SmartDashboard.putNumber("VictorSmokeTest/Output", 0.0);
    SmartDashboard.putString("VictorSmokeTest/Phase", "Idle");
  }

  @Override
  public void autonomousInit() {
    startSmokeTest("Autonomous");
  }

  @Override
  public void teleopInit() {
    startSmokeTest("Teleop");
  }

  @Override
  public void disabledInit() {
    stopMotor("Disabled");
    testTimer.stop();
  }

  @Override
  public void autonomousPeriodic() {
    runSmokeTestPattern();
  }

  @Override
  public void teleopPeriodic() {
    runSmokeTestPattern();
  }

  private void startSmokeTest(String mode) {
    testTimer.reset();
    testTimer.start();
    SmartDashboard.putString("VictorSmokeTest/Status", "Running");
    SmartDashboard.putString("VictorSmokeTest/Mode", mode);
  }

  private void runSmokeTestPattern() {
    double t = testTimer.get() % CYCLE_SECONDS;
    double output = 0.0;
    String phase = "Neutral";

    // Pattern: 2s forward, 1s stop, 2s reverse, 1s stop.
    if (t < FORWARD_END_SECONDS) {
      output = FORWARD_OUTPUT;
      phase = "Forward";
    } else if (t >= REVERSE_START_SECONDS && t < REVERSE_END_SECONDS) {
      output = REVERSE_OUTPUT;
      phase = "Reverse";
    }

    motor.set(ControlMode.PercentOutput, output);

    SmartDashboard.putNumber("VictorSmokeTest/Output", output);
    SmartDashboard.putNumber("VictorSmokeTest/CycleTimeSec", t);
    SmartDashboard.putString("VictorSmokeTest/Phase", phase);
  }

  private void stopMotor(String status) {
    motor.set(ControlMode.PercentOutput, 0.0);
    SmartDashboard.putString("VictorSmokeTest/Status", status);
    SmartDashboard.putNumber("VictorSmokeTest/Output", 0.0);
    SmartDashboard.putString("VictorSmokeTest/Phase", "Idle");
  }
}
