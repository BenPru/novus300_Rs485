"""Frame parser for the Paul Novus 300 RS-485 bus."""

from __future__ import annotations

from collections.abc import Mapping

NovusValue = float | int | bool | str

REGISTER_WIDTHS = {
    0x08: 1,
    0x09: 16,
    0x0E: 1,
    0x1A: 1,
    0x1D: 1,
    0x25: 1,
    0x26: 5,
    0x27: 1,
    0x28: 1,
    0x29: 1,
    0x3D: 5,
    0x3E: 5,
    0x44: 1,
    0x55: 2,
    0x81: 2,
    0x82: 2,
    0x83: 2,
    0x84: 2,
    0x85: 5,
}

TEMPERATURE_REGISTERS = {
    0x81: "supply_air_temperature",
    0x82: "outdoor_air_temperature",
    0x83: "extract_air_temperature",
    0x84: "exhaust_air_temperature",
}

COUNTER_REGISTERS = {
    0x26: "operating_time",
    0x3D: "filter_interval",
    0x3E: "filter_time_remaining",
    0x85: "fan_operating_time",
}

RUN_STATES = {
    0: "stopped",
    1: "running",
    3: "starting",
}

VENTILATION_MODES = {
    1: "level_1",
    2: "level_2",
    3: "level_3",
    4: "boost",
    5: "away",
    6: "automatic",
}


def crc16_ccitt(data: bytes) -> int:
    """Return the protocol's CRC-16/CCITT value."""
    msb = 0
    lsb = 0
    for byte in data:
        value = byte ^ msb
        value ^= value >> 4
        msb = (lsb ^ (value >> 3) ^ (value << 4)) & 0xFF
        lsb = (value ^ (value << 5)) & 0xFF
    return (msb << 8) | lsb


def _frame_is_valid(frame: bytes) -> bool:
    crc = crc16_ccitt(frame[:4] + frame[6:])
    return frame[4:6] == bytes((crc & 0xFF, crc >> 8))


def _duration_seconds(raw: bytes) -> int:
    minute, hour, days_low, days_high, years = raw
    days = int.from_bytes((days_low, days_high), "little")
    return (((years * 365 + days) * 24 + hour) * 60 + minute) * 60


def _decode_registers(payload: bytes) -> dict[str, NovusValue]:
    readings: dict[str, NovusValue] = {}
    offset = 0
    while offset + 2 <= len(payload):
        register = int.from_bytes(payload[offset : offset + 2], "little")
        width = REGISTER_WIDTHS.get(register)
        if width is None or offset + 2 + width > len(payload):
            break
        raw = payload[offset + 2 : offset + 2 + width]
        offset += 2 + width

        if register in TEMPERATURE_REGISTERS:
            readings[TEMPERATURE_REGISTERS[register]] = (
                int.from_bytes(raw, "little", signed=True) / 10
            )
        elif register == 0x55:
            readings["fan_setpoint"] = int.from_bytes(raw, "little") / 10
        elif register == 0x1A:
            status_word = raw[0]
            heat_recovery = bool(status_word & 0x08)
            bypass = bool(status_word & 0x20)
            if heat_recovery and bypass:
                air_path = "transition"
            elif bypass:
                air_path = "bypass"
            elif heat_recovery:
                air_path = "heat_recovery"
            else:
                air_path = "unknown"
            readings["air_path"] = air_path
            readings["bypass_open"] = air_path in ("bypass", "transition")
            readings["status_word"] = status_word
        elif register == 0x1D:
            readings["run_state"] = RUN_STATES.get(raw[0], "unknown")
            readings["run_state_raw"] = raw[0]
        elif register == 0x27:
            readings["ventilation_mode"] = VENTILATION_MODES.get(raw[0], "unknown")
            readings["ventilation_mode_raw"] = raw[0]
        elif register in COUNTER_REGISTERS:
            readings[COUNTER_REGISTERS[register]] = _duration_seconds(raw)
    return readings


class NovusFrameParser:
    """Incrementally parse Novus RS-485 frames."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Mapping[str, NovusValue]]:
        """Return readings from every valid register-data frame in `data`."""
        self._buffer.extend(data)
        readings: list[Mapping[str, float | int | bool]] = []

        while len(self._buffer) >= 6:
            if self._buffer[0] not in (0x00, 0x01) or not 0x80 <= self._buffer[2] <= 0x87:
                del self._buffer[0]
                continue

            length = self._buffer[3] & 0x7F
            frame_length = length + 6
            if frame_length > 70:
                del self._buffer[0]
                continue
            if len(self._buffer) < frame_length:
                break

            frame = bytes(self._buffer[:frame_length])
            candidate = frame
            if candidate[0] == 0x00:
                candidate = bytes((0x01,)) + candidate[1:]
            if not _frame_is_valid(candidate):
                del self._buffer[0]
                continue

            del self._buffer[:frame_length]
            if candidate[2] == 0x85:
                decoded = _decode_registers(candidate[6:])
                if decoded:
                    readings.append(decoded)

        return readings
