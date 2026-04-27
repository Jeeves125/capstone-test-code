#!/usr/bin/env python3
"""Simple interactive client for can_command_server.py."""

from __future__ import annotations

import argparse
import socket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive client for CAN command server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5003, help="Server port (default: 5003)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with socket.create_connection((args.host, args.port), timeout=5.0) as sock:
        with sock.makefile("rw", encoding="utf-8", newline="\n") as conn:
            greeting = conn.readline().strip()
            print(f"Server: {greeting}")
            print("Type commands (PING, STATUS, SET 0.3, FWD 0.2, REV 0.2, STOP, QUIT)")

            while True:
                command = input("cmd> ").strip()
                if not command:
                    continue

                conn.write(command + "\n")
                conn.flush()

                response = conn.readline()
                if not response:
                    print("Server closed connection.")
                    break

                print(f"Server: {response.strip()}")

                if command.upper() in {"QUIT", "SHUTDOWN"}:
                    break


if __name__ == "__main__":
    main()
