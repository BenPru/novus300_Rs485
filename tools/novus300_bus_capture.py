#!/usr/bin/env python3
"""Passively record raw bytes observed on a Paul Novus 300 RS-485 bus."""

from __future__ import annotations

import argparse
import json
import signal
from datetime import datetime
from pathlib import Path
from threading import Event
from time import monotonic_ns

import serial

STOP = Event()


def parse_args() -> argparse.Namespace:
    """Parse passive capture options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serial-port",
        default="/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0",
    )
    parser.add_argument(
        "--output-dir",
        default="/home/pi/novus300-captures",
        help="Directory for raw binary and JSONL capture files",
    )
    return parser.parse_args()


def stop_capture(signum: int, frame: object) -> None:
    """Stop recording after SIGINT or SIGTERM."""
    STOP.set()


def main() -> None:
    """Record every received byte without ever sending serial data."""
    args = parse_args()
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"novus300-{timestamp}.raw"
    events_path = output_dir / f"novus300-{timestamp}.jsonl"

    signal.signal(signal.SIGINT, stop_capture)
    signal.signal(signal.SIGTERM, stop_capture)

    with (
        raw_path.open("xb") as raw_file,
        events_path.open("x", encoding="utf-8") as events_file,
        serial.Serial(
            port=args.serial_port,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_MARK,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.25,
            rtscts=False,
            dsrdtr=False,
            exclusive=True,
        ) as serial_port,
    ):
        serial_port.dtr = False
        serial_port.rts = False
        metadata = {
            "event": "capture_started",
            "serial_port": args.serial_port,
            "baudrate": 9600,
            "parity": "mark",
            "raw_file": raw_path.name,
            "note": "Receive-only capture; this program never calls write().",
        }
        events_file.write(json.dumps(metadata) + "\n")
        events_file.flush()

        while not STOP.is_set():
            data = serial_port.read(serial_port.in_waiting or 1)
            if not data:
                continue
            raw_file.write(data)
            raw_file.flush()
            events_file.write(
                json.dumps(
                    {
                        "monotonic_ns": monotonic_ns(),
                        "received_at": datetime.now().astimezone().isoformat(),
                        "length": len(data),
                        "hex": data.hex(),
                    }
                )
                + "\n"
            )
            events_file.flush()

        events_file.write(json.dumps({"event": "capture_stopped"}) + "\n")


if __name__ == "__main__":
    main()
