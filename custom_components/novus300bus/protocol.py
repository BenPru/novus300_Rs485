"""Frame parser for the Paul Novus 300 RS-485 bus."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime

NovusValue = float | int | bool | str

# Panel menu settings: registers the panel writes when a menu page is saved.
SETTING_REGISTERS = {
    0x2E: "fan_level_1_percentage",
    0x2F: "fan_level_2_percentage",
    0x30: "fan_level_3_percentage",
    0x3B: "boost_duration_minutes",
    0x3C: "away_duration_minutes",
}

REGISTER_WIDTHS = {
    0x2E: 1,
    0x2F: 1,
    0x30: 1,
    0x31: 1,
    0x32: 1,
    0x33: 1,
    0x3B: 1,
    0x3C: 1,
    0x62: 1,
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

UNKNOWN_REGISTERS = {
    0x44: "register_44",
    0x62: "register_62",
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
    0: "standby",
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


MODE_REQUEST_REGISTER = 0x28
MODE_REQUEST_VALUES = {name: value for value, name in VENTILATION_MODES.items() if value}


def build_mode_request(mode: str) -> bytes:
    """Return the panel frame that requests a ventilation mode."""
    header = bytes((0x01, 0x00, 0x85, 0x03))
    payload = bytes((MODE_REQUEST_REGISTER, 0x00, MODE_REQUEST_VALUES[mode]))
    crc = crc16_ccitt(header + payload)
    return header + bytes((crc & 0xFF, crc >> 8)) + payload


def _build_register_write(payload: bytes) -> bytes:
    header = bytes((0x01, 0x00, 0x85, len(payload)))
    crc = crc16_ccitt(header + payload)
    return header + bytes((crc & 0xFF, crc >> 8)) + payload


def build_time_frame(moment: datetime) -> bytes:
    """Return the panel frame that sets the unit's time of day."""
    return _build_register_write(
        bytes((0x02, 0x00, moment.second, moment.minute, moment.hour))
    )


def build_date_frame(moment: datetime) -> bytes:
    """Return the panel frame that sets the unit's date and weekday."""
    return _build_register_write(
        bytes(
            (0x01, 0x00, moment.weekday(), moment.day, moment.month, moment.year % 100)
        )
    )


FILTER_INTERVAL_REGISTER = 0x3D
FILTER_REMAINING_REGISTER = 0x3E
FILTER_INTERVAL_DAYS = range(30, 181, 10)


def _filter_days_value(register: int, days: int) -> bytes:
    return bytes((register, 0x00, 0, 0, days & 0xFF, days >> 8, 0))


def build_filter_interval_frame(days: int) -> bytes:
    """Return the panel frame that stores the filter interval in days."""
    return _build_register_write(_filter_days_value(FILTER_INTERVAL_REGISTER, days))


def build_filter_reset_frame(days: int) -> bytes:
    """Return the panel frame that restarts the filter run time at `days`."""
    return _build_register_write(
        _filter_days_value(FILTER_INTERVAL_REGISTER, days)
        + _filter_days_value(FILTER_REMAINING_REGISTER, days)
    )


def build_setting_frame(key: str, value: int) -> bytes:
    """Return the panel frame that stores one menu setting in the unit."""
    register = next(reg for reg, name in SETTING_REGISTERS.items() if name == key)
    return _build_register_write(bytes((register, 0x00, value)))


def _decode_clock(frame: bytes) -> dict[str, NovusValue] | None:
    """Decode the unit's clock broadcast (command 0x00)."""
    payload = frame[6:]
    if len(payload) != 14 or payload[0:2] != b"\x01\x00" or payload[6:8] != b"\x02\x00":
        return None
    _, _, weekday, day, month, year, _, _, second, minute, hour = payload[:11]
    try:
        moment = datetime(2000 + year, month, day, hour, minute, second)
    except ValueError:
        return None
    return {"clock": moment.isoformat()}


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
        elif register in UNKNOWN_REGISTERS:
            readings[UNKNOWN_REGISTERS[register]] = raw[0]
        elif register in SETTING_REGISTERS:
            readings[SETTING_REGISTERS[register]] = raw[0]
        elif register in COUNTER_REGISTERS:
            readings[COUNTER_REGISTERS[register]] = _duration_seconds(raw)
    return readings


IDENTITY_PATTERN = re.compile(rb"(ETA|SWZ|ST)[0-9A-Z]{8,9}")
IDENTITY_KEYS = {
    b"ETA": "serial_panel",
    b"SWZ": "serial_fan_slave",
    b"ST": "serial_defroster",
}


def _decode_identity(payload: bytes) -> dict[str, NovusValue]:
    """Decode the component identifiers the unit announces at start-up."""
    return {
        IDENTITY_KEYS[match.group(1)]: match.group(0).decode()
        for match in IDENTITY_PATTERN.finditer(payload)
    }


class NovusFrameParser:
    """Incrementally parse Novus RS-485 frames."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Mapping[str, NovusValue]]:
        """Return readings from every valid register-data frame in `data`."""
        self._buffer.extend(data)
        readings: list[Mapping[str, float | int | bool]] = []

        while len(self._buffer) >= 6:
            is_clock = bytes(self._buffer[:4]) == b"\x00\x00\x00\x0e"
            if not is_clock and (
                self._buffer[0] not in (0x00, 0x01) or not 0x80 <= self._buffer[2] <= 0x87
            ):
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
            if is_clock:
                if _frame_is_valid(frame):
                    del self._buffer[:frame_length]
                    decoded = _decode_clock(frame)
                    if decoded:
                        readings.append(decoded)
                else:
                    del self._buffer[0]
                continue
            if candidate[0] == 0x00:
                candidate = bytes((0x01,)) + candidate[1:]
            if not _frame_is_valid(candidate):
                del self._buffer[0]
                continue

            del self._buffer[:frame_length]
            if candidate[2] in (0x81, 0x85):
                identity = _decode_identity(candidate[6:])
                if identity:
                    readings.append(identity)
            if candidate[2] == 0x85:
                decoded = _decode_registers(candidate[6:])
                if decoded:
                    readings.append(decoded)

        return readings
