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
    0x31: "fan_level_1_imbalance",
    0x32: "fan_level_2_imbalance",
    0x33: "fan_level_3_imbalance",
    0x3B: "boost_duration_minutes",
    0x3C: "away_duration_minutes",
}
IMBALANCE_REGISTERS = (0x31, 0x32, 0x33)

# Seven additional fan stages (%), announced in the unit's start-up dump.
FAN_STAGE_REGISTERS = {
    0x34 + index: f"fan_stage_{index + 1}_percentage" for index in range(7)
}
SETTING_REGISTERS.update(FAN_STAGE_REGISTERS)

# Start-up parameter block (read only, meaning not verified): register -> width.
PARAMETER_REGISTER_WIDTHS = {
    **dict.fromkeys(range(0x41, 0x64), 1),
    **dict.fromkeys((0x41, 0x42, 0x47, 0x49, 0x4A, 0x4B, 0x4C, 0x55, 0x56, 0x5A, 0x5B, 0x5F, 0x60, 0x63), 2),
}
for _register in (0x44, 0x55, 0x62):
    PARAMETER_REGISTER_WIDTHS.pop(_register)

# Installation selections, stored as param_XX (0x1E/0x21: last byte only).
SELECT_REGISTER_WIDTHS = {0x1B: 2, 0x1E: 4, 0x21: 4, 0x24: 1, 0x7B: 1}

REGISTER_WIDTHS = {
    **PARAMETER_REGISTER_WIDTHS,
    **SELECT_REGISTER_WIDTHS,
    0x3F: 5,
    0x40: 1,
    **dict.fromkeys(FAN_STAGE_REGISTERS, 1),
    0x2E: 1,
    0x2F: 1,
    0x30: 1,
    0x31: 1,
    0x32: 1,
    0x33: 1,
    0x3B: 1,
    0x3C: 1,
    0x62: 1,
    **dict.fromkeys(range(0x64, 0x79), 8),
    0x79: 1,
    0x7A: 1,
    0x7C: 1,
    0x08: 1,
    0x09: 16,
    0x0E: 1,
    0x0F: 1,
    0x12: 1,
    0x15: 1,
    0x18: 1,
    0x19: 11,
    0x1A: 1,
    0x1C: 11,
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
    0x86: 1,
    0x87: 1,
    0x0A: 16,
    0x0B: 4,
    0x0C: 3,
    0x88: 16,
    0x89: 4,
    0x8A: 3,
    0x8B: 16,
    0x8C: 4,
    0x8D: 3,
}

# Last three unit messages: text (code byte + 15 characters), date
# (weekday, day, month, year), time (second, minute, hour).
MESSAGE_LOG_REGISTERS = {
    0x0A: (0, "text"), 0x0B: (0, "date"), 0x0C: (0, "time"),
    0x88: (1, "text"), 0x89: (1, "date"), 0x8A: (1, "time"),
    0x8B: (2, "text"), 0x8C: (2, "date"), 0x8D: (2, "time"),
}

TEMPERATURE_REGISTERS = {
    0x81: "supply_air_temperature",
    0x82: "outdoor_air_temperature",
    0x83: "extract_air_temperature",
    0x84: "exhaust_air_temperature",
}

# Alarm codes sent in the first byte of register 0x09 (ASCII letter).
MESSAGES = {
    0x00: "none",
    0x41: "filter_change",
    0x81: "sensor_1_error",
    0x82: "sensor_2_error",
    0x83: "input_error",
    0x84: "sensor_4_error",
    0x85: "supply_air_too_low",
    0x86: "intake_air_too_low",
    0x87: "fan_1_hall_error",
    0x88: "fan_2_hall_error",
    0x89: "bypass_error",
    0xC0: "bus_version_incompatible",
    0xC1: "too_many_devices",
    0xC2: "fan_slave_missing",
    0xC3: "fan_slave_comm_error",
    0xC4: "comm_error_general",
    0xC5: "heater_comm_error",
    0xC6: "ghe_flap_comm_error",
    0xC7: "defroster_comm_error",
    0xC8: "heating_not_switching_off",
    0xC9: "control_unit_error",
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


def build_memory_dump_request() -> bytes:
    """Return the frame that asks the unit to resend all registers (command 0x83)."""
    header = bytes((0x01, 0x01, 0x83, 0x00))
    crc = crc16_ccitt(header)
    return header + bytes((crc & 0xFF, crc >> 8))


def build_time_frame(moment: datetime) -> bytes:
    """Return the panel frame that sets the unit's time of day."""
    return _build_register_write(
        bytes((0x02, 0x00, moment.second, moment.minute, moment.hour))
    )


def build_power_frame(on: bool) -> bytes:
    """Return the panel frame that switches the unit on or off (register 0x07)."""
    return _build_register_write(
        bytes((0x07, 0x00, 0x01, 0x90, 0x00, 0x00)) if on else bytes((0x07, 0x00, 0x00))
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
    if register in IMBALANCE_REGISTERS and (
        isinstance(value, bool) or not isinstance(value, int) or not -50 <= value <= 50
    ):
        raise ValueError(f"Invalid fan imbalance: {value}")
    return _build_register_write(
        bytes((register, 0x00))
        + value.to_bytes(1, "little", signed=register in IMBALANCE_REGISTERS)
    )


# Writable unit parameters, raw limits in 0.1 degC (verified against the panel menus).
PARAMETER_LIMITS = {
    0x41: (150, 350),
    0x42: (100, 300),
    0x43: (1, 50),
    0x47: (0, 150),
    0x49: (100, 300),
    0x4A: (-100, 100),
    0x4B: (-150, 50),
    0x4C: (-200, 0),
    0x5A: (200, 700),
    0x48: (5, 50),
    0x56: (150, 300),
    0x5C: (5, 50),
    0x5F: (-100, 145),
    0x60: (150, 300),
    0x61: (5, 50),
}


def build_parameter_frame(register: int, value: int) -> bytes:
    """Return the panel frame that stores one unit parameter (raw 0.1 degC)."""
    low, high = PARAMETER_LIMITS[register]
    if not low <= value <= high:
        raise ValueError(f"Parameter 0x{register:02X} out of range: {value}")
    width = PARAMETER_REGISTER_WIDTHS[register]
    return _build_register_write(
        bytes((register, 0x00)) + value.to_bytes(width, "little", signed=width == 2)
    )


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
    log: dict[int, dict[str, bytes]] = {}
    offset = 0
    while offset + 2 <= len(payload):
        register = int.from_bytes(payload[offset : offset + 2], "little")
        width = REGISTER_WIDTHS.get(register)
        boot_form = False
        if register in (0x1E, 0x21):
            # Panel writes carry 4 bytes (0c 7f/80 00 xx); the start-up dump only the first.
            tail = payload[offset + 3 : offset + 4]
            boot_form = not (tail and tail[0] in (0x7F, 0x80))
            width = 1 if boot_form else 4
        if width is None or offset + 2 + width > len(payload):
            break
        raw = payload[offset + 2 : offset + 2 + width]
        offset += 2 + width
        if boot_form:
            # Start-up dump: only "no reheater" (0) is conclusive, the type is not in it.
            if register == 0x21 and raw[0] == 0:
                readings["param_21"] = 0
            continue

        if register in MESSAGE_LOG_REGISTERS:
            slot, part = MESSAGE_LOG_REGISTERS[register]
            log.setdefault(slot, {})[part] = raw
        elif register in TEMPERATURE_REGISTERS:
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
        elif register == 0x09:
            readings["message_code"] = raw[0]
            readings["message"] = MESSAGES.get(
                raw[0],
                "none" if raw[0] == 0 else f"code_{chr(raw[0]) if 32 < raw[0] < 127 else raw[0]}",
            )
        elif register in UNKNOWN_REGISTERS:
            readings[UNKNOWN_REGISTERS[register]] = raw[0]
        elif register in SELECT_REGISTER_WIDTHS:
            readings[f"param_{register:02x}"] = (
                raw[3] if len(raw) == 4 else int.from_bytes(raw, "little")
            )
        elif register in PARAMETER_REGISTER_WIDTHS or register in (0x79, 0x7A, 0x7C):
            readings[f"param_{register:02x}"] = int.from_bytes(
                raw, "little", signed=len(raw) == 2
            )
        elif register in SETTING_REGISTERS:
            readings[SETTING_REGISTERS[register]] = int.from_bytes(
                raw, "little", signed=register in IMBALANCE_REGISTERS
            )
        elif register in COUNTER_REGISTERS:
            readings[COUNTER_REGISTERS[register]] = _duration_seconds(raw)
    for slot, parts in log.items():
        if len(parts) == 3:
            entry = _decode_message_log(parts)
            if entry:
                readings[f"message_log_{slot}"] = entry
    return readings


def _decode_message_log(parts: dict[str, bytes]) -> str | None:
    """Return 'ISO time|code|detail' for one stored unit message."""
    _, day, month, year = parts["date"]
    second, minute, hour = parts["time"]
    try:
        moment = datetime(2000 + year, month, day, hour, minute, second)
    except ValueError:
        return None
    text = parts["text"]
    detail = text[1:].decode("ascii", "replace").strip()
    return f"{moment.isoformat()}|{text[0]}|{detail}"


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


SELECT_VALUES = {
    0x1E: (1, 2, 3),
    0x21: (0, 1, 3),
    0x24: (0, 4),
    0x7B: (0, 1, 2),
}


def build_select_frame(register: int, value: int) -> bytes:
    """Return the panel frame that stores an installation selection."""
    head = bytes((register, 0x00))
    if register == 0x1B:
        if value & ~0xFF != 0 or value & 0x7B != 0x7B:
            raise ValueError(f"Invalid value for 0x1B: {value}")
        return _build_register_write(head + value.to_bytes(2, "little"))
    if register == 0x63:
        if value not in (0x1F0, 0x1F8):
            raise ValueError(f"Invalid value for 0x63: {value}")
        return _build_register_write(head + value.to_bytes(2, "little"))
    if value not in SELECT_VALUES.get(register, ()):
        raise ValueError(f"Invalid value for 0x{register:02X}: {value}")
    if register == 0x1E:
        return _build_register_write(head + bytes((0x0C, 0x7F, 0x00, value)))
    if register == 0x21:
        extra = bytes((0x0C, 0x80, 0x00, value)) if value else bytes((0x00, 0x80, 0x00, 0x00))
        return _build_register_write(head + extra)
    return _build_register_write(head + bytes((value,)))
