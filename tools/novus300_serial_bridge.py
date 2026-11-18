#!/usr/bin/env python3
"""Expose the Novus serial bus as a TCP byte stream.

The bridge is read-only unless --allow-command-frames is given. In that mode only
the exact panel command frames in ALLOWED_COMMAND_FRAMES are accepted from the
client; everything else is discarded. An accepted frame is written once, right
after the panel's next reply frame (cmd 0x87), so it does not overlap another
transmission.
"""

import argparse
import logging
import select
import socket

import serial

LOGGER = logging.getLogger(__name__)

def _mode_request(mode: int) -> bytes:
    """Return the panel frame requesting ventilation mode 1-6."""
    header = bytes((0x01, 0x00, 0x85, 0x03))
    payload = bytes((0x28, 0x00, mode))
    msb = lsb = 0
    for byte in header + payload:
        value = byte ^ msb
        value ^= value >> 4
        msb = (lsb ^ (value >> 3) ^ (value << 4)) & 0xFF
        lsb = (value ^ (value << 5)) & 0xFF
    return header + bytes((lsb, msb)) + payload


MODE_NAMES = {1: "level_1", 2: "level_2", 3: "level_3", 4: "boost", 5: "away", 6: "automatic"}
ALLOWED_COMMAND_FRAMES = {_mode_request(m): "slot05_" + n for m, n in MODE_NAMES.items()}
# Panel power frames: register 0x07 = 0 (off) and register 0x07 = 1 plus 0x90 = 0 (on).
ALLOWED_COMMAND_FRAMES[bytes.fromhex("01008503aaa7070000")] = "slot05_power_off"
ALLOWED_COMMAND_FRAMES[bytes.fromhex("0100850693bd070001900000")] = "slot05_power_on"


def parse_args() -> argparse.Namespace:
    """Parse bridge configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serial-port",
        default="/dev/serial/by-id/usb-1a86_USB2.0-Serial-if00-port0",
    )
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--listen-port", type=int, default=9700)
    parser.add_argument("--allowed-client", required=True)
    parser.add_argument("--allow-command-frames", action="store_true")
    return parser.parse_args()


ALIVE_05 = bytes.fromhex("01058400184a")
SLOT_FRAMES = set(ALLOWED_COMMAND_FRAMES)


def _crc(data: bytes) -> bytes:
    msb = lsb = 0
    for byte in data:
        value = byte ^ msb
        value ^= value >> 4
        msb = (lsb ^ (value >> 3) ^ (value << 4)) & 0xFF
        lsb = (value ^ (value << 5)) & 0xFF
    return bytes((lsb, msb))


def clock_frame_kind(frame: bytes):
    """Classify a valid panel clock or menu-setting frame, else None."""
    if len(frame) < 6 or frame[:3] != bytes((0x01, 0x00, 0x85)):
        return None
    if frame[4:6] != _crc(frame[:4] + frame[6:]):
        return None
    payload = frame[6:]
    if frame[3] == 5 and len(payload) == 5 and payload[:2] == b"\x02\x00":
        second, minute, hour = payload[2:]
        return "time" if second < 60 and minute < 60 and hour < 24 else None
    if frame[3] == 6 and len(payload) == 6 and payload[:2] == b"\x01\x00":
        weekday, day, month, year = payload[2:]
        valid = weekday < 7 and 1 <= day <= 31 and 1 <= month <= 12 and year < 100
        return "date" if valid else None
    if frame[3] in (7, 14) and len(payload) == frame[3]:
        entries = [payload[i : i + 7] for i in range(0, len(payload), 7)]
        registers = (0x3D, 0x3E)[: len(entries)]
        if frame[3] == 7 and payload[0] == 0x3E:
            minute, hour, days = payload[2], payload[3], payload[4] | payload[5] << 8
            if payload[1] or payload[6] or minute >= 60 or hour >= 24 or days > 180:
                return None
            return "filter_remaining"
        values = set()
        for entry, register in zip(entries, registers):
            minute, hour, days = entry[2], entry[3], entry[4] | entry[5] << 8
            if entry[:2] != bytes((register, 0)) or minute or hour or entry[6]:
                return None
            if not 30 <= days <= 180 or days % 10:
                return None
            values.add(days)
        if len(values) == 1:
            return "filter_interval" if frame[3] == 7 else "filter_reset"
        return None
    if frame[3] == 3 and len(frame) == 9 and frame[7] == 0:
        limits = {0x2E: (0, 100), 0x2F: (0, 100), 0x30: (0, 100), 0x3B: (1, 240), 0x3C: (1, 240)}
        low, high = limits.get(frame[6], (1, 0))
        if low <= frame[8] <= high:
            return "setting"
    return None


def is_allowed_frame(frame: bytes) -> bool:
    """Return whether a client frame may be sent to the bus."""
    return frame in ALLOWED_COMMAND_FRAMES or clock_frame_kind(frame) is not None


def reply_frame_completed(rx: bytearray) -> bool:
    """Consume complete frames from rx; return True if a cmd 0x87 frame ended."""
    seen_reply = False
    while len(rx) >= 6:
        if rx[0] not in (0x00, 0x01) or not 0x80 <= rx[2] <= 0x87:
            del rx[0]
            continue
        frame_length = (rx[3] & 0x7F) + 6
        if frame_length > 70:
            del rx[0]
            continue
        if len(rx) < frame_length:
            break
        if rx[2] == 0x87:
            seen_reply = True
        if bytes(rx[:frame_length]) == ALIVE_05:
            seen_reply = "alive05"
        del rx[:frame_length]
    return seen_reply


def serve(args: argparse.Namespace) -> None:
    """Forward serial bytes to one allowed TCP client."""
    with serial.Serial(
        port=args.serial_port,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_MARK,
        stopbits=serial.STOPBITS_ONE,
        timeout=0,
        rtscts=False,
        dsrdtr=False,
        exclusive=True,
    ) as serial_port, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        serial_port.dtr = False
        serial_port.rts = False
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((args.listen_host, args.listen_port))
        listener.listen(1)
        listener.setblocking(False)

        LOGGER.info(
            "Forwarding %s to %s:%s for %s only (command frames %s)",
            args.serial_port,
            args.listen_host,
            args.listen_port,
            args.allowed_client,
            "ALLOWED" if args.allow_command_frames else "blocked",
        )
        client = None
        rx = bytearray()
        pending: bytes | None = None

        while True:
            readers = [listener, serial_port]
            if client is not None:
                readers.append(client)
            readable, _, _ = select.select(readers, [], [])

            if listener in readable:
                candidate, address = listener.accept()
                if address[0] != args.allowed_client:
                    LOGGER.warning("Rejected client %s", address[0])
                    candidate.close()
                else:
                    if client is not None:
                        client.close()
                    client = candidate
                    client.setblocking(False)
                    LOGGER.info("Accepted client %s", address[0])

            if serial_port in readable:
                data = serial_port.read(serial_port.in_waiting or 1)
                if data and client is not None:
                    try:
                        client.sendall(data)
                    except (BrokenPipeError, ConnectionResetError):
                        client.close()
                        client = None
                if data and args.allow_command_frames:
                    rx.extend(data)
                    trigger = reply_frame_completed(rx)
                    if pending is not None and (
                        trigger == "alive05" if pending in SLOT_FRAMES or clock_frame_kind(pending) else trigger
                    ):
                        serial_port.write(pending)
                        serial_port.flush()
                        LOGGER.warning(
                            "Sent command frame %s (%s)",
                            pending.hex(),
                            ALLOWED_COMMAND_FRAMES.get(pending, "clock"),
                        )
                        pending = None
                    del rx[:-70]

            if client is not None and client in readable:
                try:
                    data = client.recv(4096)
                except ConnectionResetError:
                    client.close()
                    client = None
                    continue
                if not data:
                    client.close()
                    client = None
                elif args.allow_command_frames and is_allowed_frame(data):
                    pending = data
                    LOGGER.warning(
                        "Queued command frame %s", ALLOWED_COMMAND_FRAMES.get(data, "clock")
                    )
                else:
                    LOGGER.warning(
                        "Discarded %d client bytes; not an allowed command frame",
                        len(data),
                    )


def main() -> None:
    """Run the bridge."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    serve(parse_args())


if __name__ == "__main__":
    main()
