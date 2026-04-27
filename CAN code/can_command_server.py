#!/usr/bin/env python3
"""
TCP command server for controlling a Victor SPX motor controller over CAN.

Protocol:
  - One UTF-8 command per line
  - One response per line

Commands:
  PING
  STATUS
  STOP
  SET <value>       # value in range -1.0 .. 1.0
  FWD <value>       # value in range 0.0 .. 1.0
  REV <value>       # value in range 0.0 .. 1.0
  QUIT              # close only this client connection
  SHUTDOWN          # stop motor and shut down server
"""

from __future__ import annotations

import argparse
import importlib
import logging
import socketserver
import threading
import time
from dataclasses import dataclass
from typing import Optional


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class MotorDriver:
    def set_percent_output(self, value: float) -> None:
        raise NotImplementedError

    def stop_motor(self) -> None:
        self.set_percent_output(0.0)


class SimulatedMotorDriver(MotorDriver):
    def __init__(self, can_id: int) -> None:
        self.can_id = can_id
        self.last_value = 0.0

    def set_percent_output(self, value: float) -> None:
        value = clamp(value, -1.0, 1.0)
        self.last_value = value
        logging.info("[SIM] CAN ID %s output set to %.3f", self.can_id, value)


class VictorSPXDriver(MotorDriver):
    """RobotPy CTRE (Phoenix 5) driver for Victor SPX."""

    def __init__(self, can_id: int) -> None:
        self.can_id = can_id
        self._motor = None
        self._control_mode = None
        self._initialize_driver()

    def _initialize_driver(self) -> None:
        try:
            ctre = importlib.import_module("ctre")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'ctre'. Install RobotPy CTRE (pip install robotpy-ctre)."
            ) from exc

        motor_class = getattr(ctre, "WPI_VictorSPX", None) or getattr(ctre, "VictorSPX", None)
        if motor_class is None:
            raise RuntimeError("ctre module found, but VictorSPX class is unavailable.")

        control_mode = getattr(ctre, "ControlMode", None)
        if control_mode is None:
            try:
                ctre_internal = importlib.import_module("ctre._ctre")
                control_mode = getattr(ctre_internal, "ControlMode", None)
            except ModuleNotFoundError:
                control_mode = None

        self._motor = motor_class(self.can_id)
        self._control_mode = control_mode
        logging.info("Victor SPX initialized on CAN ID %s", self.can_id)

    def set_percent_output(self, value: float) -> None:
        value = clamp(value, -1.0, 1.0)

        if self._control_mode is not None:
            percent_output = getattr(self._control_mode, "PercentOutput", None)
            if percent_output is not None:
                self._motor.set(percent_output, value)
                return

        # Fallback for wrappers exposing SpeedController-style set(value)
        self._motor.set(value)


@dataclass
class CommandResult:
    response: str
    close_client: bool = False


@dataclass
class ParsedCommand:
    name: str
    value: Optional[float] = None


def parse_command(raw_command: str) -> ParsedCommand:
    parts = raw_command.strip().split()
    if not parts:
        raise ValueError("empty command")

    name = parts[0].upper()

    if name in {"PING", "STATUS", "STOP", "QUIT", "SHUTDOWN"}:
        if len(parts) != 1:
            raise ValueError(f"{name} does not take arguments")
        return ParsedCommand(name=name)

    if name in {"SET", "FWD", "REV"}:
        if len(parts) != 2:
            raise ValueError(f"{name} requires exactly one numeric argument")
        try:
            value = float(parts[1])
        except ValueError as exc:
            raise ValueError(f"invalid numeric value: {parts[1]}") from exc
        return ParsedCommand(name=name, value=value)

    raise ValueError(f"unknown command: {name}")


class CommandProcessor:
    def __init__(self, driver: MotorDriver, idle_timeout_s: float, max_output: float) -> None:
        self._driver = driver
        self._idle_timeout_s = max(0.0, idle_timeout_s)
        self._max_output = clamp(abs(max_output), 0.0, 1.0)
        self._lock = threading.Lock()
        self._current_output = 0.0
        self._last_command_at = time.monotonic()
        self.shutdown_event = threading.Event()

    def _apply_output(self, requested_output: float) -> float:
        safe_output = clamp(requested_output, -self._max_output, self._max_output)
        self._driver.set_percent_output(safe_output)
        self._current_output = safe_output
        self._last_command_at = time.monotonic()
        return safe_output

    def process(self, raw_command: str) -> CommandResult:
        parsed = parse_command(raw_command)

        with self._lock:
            if parsed.name == "PING":
                return CommandResult("OK PONG")

            if parsed.name == "STATUS":
                return CommandResult(f"OK OUTPUT {self._current_output:.3f}")

            if parsed.name == "STOP":
                self._apply_output(0.0)
                return CommandResult("OK STOPPED")

            if parsed.name == "SET":
                value = clamp(parsed.value if parsed.value is not None else 0.0, -1.0, 1.0)
                applied = self._apply_output(value)
                return CommandResult(f"OK OUTPUT {applied:.3f}")

            if parsed.name == "FWD":
                value = abs(parsed.value if parsed.value is not None else 0.0)
                applied = self._apply_output(clamp(value, 0.0, 1.0))
                return CommandResult(f"OK OUTPUT {applied:.3f}")

            if parsed.name == "REV":
                value = abs(parsed.value if parsed.value is not None else 0.0)
                applied = self._apply_output(-clamp(value, 0.0, 1.0))
                return CommandResult(f"OK OUTPUT {applied:.3f}")

            if parsed.name == "QUIT":
                return CommandResult("OK BYE", close_client=True)

            if parsed.name == "SHUTDOWN":
                self._apply_output(0.0)
                self.shutdown_event.set()
                return CommandResult("OK SHUTTING_DOWN", close_client=True)

        raise ValueError("command dispatch failure")

    def enforce_idle_timeout(self) -> None:
        if self._idle_timeout_s <= 0:
            return

        with self._lock:
            elapsed = time.monotonic() - self._last_command_at
            if self._current_output != 0.0 and elapsed >= self._idle_timeout_s:
                self._driver.stop_motor()
                self._current_output = 0.0
                logging.warning("Idle timeout reached (%.2fs). Motor output set to 0.", elapsed)

    def shutdown(self) -> None:
        with self._lock:
            self._driver.stop_motor()
            self._current_output = 0.0
        self.shutdown_event.set()


class CANCommandServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, request_handler_class, processor: CommandProcessor):
        super().__init__(server_address, request_handler_class)
        self.processor = processor


class CANCommandRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        client = f"{self.client_address[0]}:{self.client_address[1]}"
        logging.info("Client connected: %s", client)

        self.wfile.write(b"READY CAN_COMMAND_SERVER\n")

        while True:
            line = self.rfile.readline()
            if not line:
                logging.info("Client disconnected: %s", client)
                break

            command = line.decode("utf-8", errors="replace").strip()
            if not command:
                self.wfile.write(b"ERR empty command\n")
                continue

            logging.info("Command from %s: %s", client, command)

            try:
                result = self.server.processor.process(command)
                self.wfile.write((result.response + "\n").encode("utf-8"))
            except ValueError as exc:
                self.wfile.write((f"ERR {exc}\n").encode("utf-8"))
                continue
            except Exception as exc:
                logging.exception("Unhandled error while processing command")
                self.wfile.write((f"ERR internal error: {exc}\n").encode("utf-8"))
                continue

            if self.server.processor.shutdown_event.is_set():
                # shutdown() must execute in a different thread to avoid deadlock.
                threading.Thread(target=self.server.shutdown, daemon=True).start()

            if result.close_client:
                break


def watchdog_loop(processor: CommandProcessor, period_s: float = 0.05) -> None:
    while not processor.shutdown_event.is_set():
        processor.enforce_idle_timeout()
        time.sleep(period_s)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CAN command server for Victor SPX")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5003, help="Bind port (default: 5003)")
    parser.add_argument("--can-id", type=int, default=1, help="Victor SPX CAN ID (default: 1)")
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=0.75,
        help="Seconds without command before auto-stop (default: 0.75)",
    )
    parser.add_argument(
        "--max-output",
        type=float,
        default=1.0,
        help="Max absolute percent output clamp in range 0.0..1.0 (default: 1.0)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run without hardware using a simulated motor driver",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def build_driver(can_id: int, simulate: bool) -> MotorDriver:
    if simulate:
        logging.warning("Simulation mode enabled. No real CAN frames will be sent.")
        return SimulatedMotorDriver(can_id)
    return VictorSPXDriver(can_id)


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    driver = build_driver(args.can_id, args.simulate)
    processor = CommandProcessor(
        driver=driver,
        idle_timeout_s=args.idle_timeout,
        max_output=args.max_output,
    )

    watchdog = threading.Thread(target=watchdog_loop, args=(processor,), daemon=True)
    watchdog.start()

    with CANCommandServer((args.host, args.port), CANCommandRequestHandler, processor) as server:
        logging.info(
            "CAN command server listening on %s:%s (CAN ID: %s)",
            args.host,
            args.port,
            args.can_id,
        )
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Stopping server.")
        finally:
            processor.shutdown()
            server.shutdown()
            server.server_close()
            logging.info("Server stopped and motor output set to zero.")


if __name__ == "__main__":
    main()
