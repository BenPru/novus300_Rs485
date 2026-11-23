"""Serial coordinator for the Paul Novus 300 bus."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import serial
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HARDWARE_PROFILE,
    DEFAULT_HARDWARE_PROFILE,
    HARDWARE_PROFILES,
    PROFILE_XOR,
    CONF_AWAY_DURATION_MINUTES,
    CONF_BAUDRATE,
    CONF_BOOST_DURATION_MINUTES,
    CONF_DYNAMIC_BUS_ADDRESSES,
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
    DEFAULT_AWAY_DURATION_MINUTES,
    DEFAULT_BOOST_DURATION_MINUTES,
    DEFAULT_DYNAMIC_BUS_ADDRESSES,
    DEFAULT_FILTER_INTERVAL_DAYS,
    CONF_DAILY_TIME_SYNC,
    CONF_SHOW_FAN_LEVELS,
    DEFAULT_SHOW_FAN_LEVELS,
    DAILY_TIME_SYNC_HOUR,
    DEFAULT_DAILY_TIME_SYNC,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    DEFAULT_FAN_LEVEL_1_PERCENTAGE,
    DEFAULT_FAN_LEVEL_2_PERCENTAGE,
    DEFAULT_FAN_LEVEL_3_PERCENTAGE,
    DEFAULT_FAN_STAGES,
    DOMAIN,
    FAN_STAGE_KEYS,
    FAN_IMBALANCE_KEYS,
)
from .capture import PassiveRecording
from .xor_protocol import NovusXorParser
from .protocol import (
    MODE_REQUEST_VALUES,
    NovusFrameParser,
    SETTING_REGISTERS,
    NovusValue,
    VENTILATION_MODES,
    FILTER_INTERVAL_DAYS,
    build_date_frame,
    build_filter_interval_frame,
    build_filter_reset_frame,
    build_memory_dump_request,
    build_mode_request,
    build_power_frame,
    PARAMETER_LIMITS,
    build_parameter_frame,
    build_select_frame,
    build_setting_frame,
    build_time_frame,
    bypass_is_present,
)

LOGGER = logging.getLogger(__name__)

COUNTER_ENTITY_IDS = {
    "operating_time": "sensor.novus300_operating_time",
    "fan_operating_time": "sensor.novus300_fan_operating_time",
    "filter_time_remaining": "sensor.novus300_filter_time_remaining",
    "filter_interval": "sensor.novus300_filter_interval",
}

# Identifiers shown in the panel's software-version menu.
KNOWN_IDENTITIES = {
    "serial_panel": "ETA0036E29A",
    "serial_fan_slave": "SWZ0025B26A",
    "serial_defroster": "ST00064E24A",
}

PERSISTED_KEYS = {
    "defroster_status_raw",
    "message_log_0",
    "message_log_1",
    "message_log_2",
    "message_history",
    "status_events",
    "message",
    "message_code",
    *KNOWN_IDENTITIES,
    *COUNTER_ENTITY_IDS,
    "ventilation_mode",
    "ventilation_mode_raw",
    *SETTING_REGISTERS.values(),
}

SETTING_DEFAULTS = {
    CONF_FAN_LEVEL_1_PERCENTAGE: DEFAULT_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE: DEFAULT_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE: DEFAULT_FAN_LEVEL_3_PERCENTAGE,
    CONF_BOOST_DURATION_MINUTES: DEFAULT_BOOST_DURATION_MINUTES,
    CONF_AWAY_DURATION_MINUTES: DEFAULT_AWAY_DURATION_MINUTES,
    **dict(zip(FAN_STAGE_KEYS, DEFAULT_FAN_STAGES)),
    **dict.fromkeys(FAN_IMBALANCE_KEYS, 0),
}


ORIGINAL_PREFIX = "orig_"


class NovusCoordinator(DataUpdateCoordinator[dict[str, NovusValue]]):
    """Read bus frames continuously in a dedicated serial thread."""

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], entry_id: str
    ) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN)
        self._config = config
        if self.hardware_profile not in HARDWARE_PROFILES:
            raise HomeAssistantError(f"Unknown Novus hardware profile: {self.hardware_profile}")
        self._parser = NovusXorParser() if self.read_only else NovusFrameParser(
            dynamic_bus_addresses=config.get(
                CONF_DYNAMIC_BUS_ADDRESSES, DEFAULT_DYNAMIC_BUS_ADDRESSES
            )
        )
        self._serial: serial.Serial | None = None
        self._serial_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._values: dict[str, NovusValue] = {} if self.read_only else dict(KNOWN_IDENTITIES)
        store_suffix = ".xor" if self.read_only else ""
        self._counter_store = Store[dict[str, NovusValue]](
            hass, 1, f"{DOMAIN}.{entry_id}.counters{store_suffix}"
        )
        self._cancel_time_sync = None
        self._last_clock_at = 0.0
        self._parameter_write_lock = asyncio.Lock()
        self._plant_word_received = asyncio.Event()
        self.raw_log: deque[tuple[str, str]] = deque(maxlen=3000)
        self.passive_recording = PassiveRecording()
        self.data = {}

    @property
    def hardware_profile(self) -> str:
        """Return the explicitly selected protocol, defaulting existing entries to CRC16."""
        return self._config.get(CONF_HARDWARE_PROFILE, DEFAULT_HARDWARE_PROFILE)

    @property
    def read_only(self) -> bool:
        """Return whether all device writes must be blocked."""
        return self.hardware_profile == PROFILE_XOR

    @property
    def device_info(self) -> dict:
        """Do not present reference firmware metadata as detected XOR hardware."""
        return {
            "identifiers": {(DOMAIN, "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300 (XOR, experimental)" if self.read_only else "Novus 300 (FOCUS250)",
            "sw_version": None if self.read_only else "BUS 1.7.1",
        }

    def ensure_writable(self) -> None:
        """Fail before any transmission or optimistic local mutation."""
        if self.read_only:
            raise HomeAssistantError("The XOR hardware/firmware profile is read-only")

    def start_passive_recording(self) -> None:
        """Record received bytes only, using the existing reader connection."""
        try:
            self.passive_recording.start()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    def protocol_diagnostics(self) -> dict:
        """Return experimental decoder details where available."""
        if isinstance(self._parser, NovusXorParser):
            return self._parser.diagnostics()
        return {"framing": "CRC16", "read_only": False}

    async def async_start(self) -> None:
        """Start the serial reader thread."""
        if not self.read_only:
            await self._async_restore_counters()
        self._thread = threading.Thread(
            target=self._read_serial,
            name="novus300bus-reader",
            daemon=True,
        )
        self._thread.start()
        if not self.read_only and self._config.get(CONF_DAILY_TIME_SYNC, DEFAULT_DAILY_TIME_SYNC) and str(
            self._config[CONF_SERIAL_PORT]
        ).startswith("socket://"):
            self._cancel_time_sync = async_track_time_change(
                self.hass,
                self._async_daily_time_sync,
                hour=DAILY_TIME_SYNC_HOUR,
                minute=0,
                second=0,
            )

    async def _async_restore_counters(self) -> None:
        """Restore persisted counters, importing prior entity values once."""
        counters = await self._counter_store.async_load()
        if counters is None:
            counters = await self.hass.async_add_executor_job(
                self._load_counters_from_history
            )
            if counters:
                await self._counter_store.async_save(counters)

        if counters:
            raw_mode = counters.get("ventilation_mode_raw")
            if isinstance(raw_mode, int):
                counters["ventilation_mode"] = VENTILATION_MODES.get(
                    raw_mode, "unknown"
                )
            self._values.update(counters)
            self.async_set_updated_data(dict(self._values))

    def _load_counters_from_history(self) -> dict[str, float]:
        """Return the most recent numeric counter values from the recorder."""
        states = get_significant_states(
            self.hass,
            dt_util.utcnow() - timedelta(days=14),
            entity_ids=list(COUNTER_ENTITY_IDS.values()),
            significant_changes_only=False,
        )
        counters: dict[str, float] = {}
        for key, entity_id in COUNTER_ENTITY_IDS.items():
            for state in reversed(states.get(entity_id, [])):
                try:
                    counters[key] = float(state.state)
                except ValueError:
                    continue
                break
        return counters

    def _persisted_values(self) -> dict[str, NovusValue]:
        """Return readings suitable for persistent storage."""
        return {
            key: value
            for key, value in self._values.items()
            if (key in PERSISTED_KEYS or key.startswith((ORIGINAL_PREFIX, "param_")))
            and isinstance(value, float | int | str)
        }

    async def async_stop(self) -> None:
        """Stop the serial reader thread."""
        self._stop_event.set()
        if self._cancel_time_sync is not None:
            self._cancel_time_sync()
            self._cancel_time_sync = None
        if self._thread is not None:
            await self.hass.async_add_executor_job(self._thread.join, 5)
            if self._thread.is_alive():
                raise HomeAssistantError("The Novus serial reader did not stop")
        await self._counter_store.async_save(self._persisted_values())

    def _read_serial(self) -> None:
        """Read and decode the serial byte stream until stopped."""
        parity = (
            serial.PARITY_MARK
            if self._config[CONF_PARITY] == "mark"
            else serial.PARITY_NONE
        )
        while not self._stop_event.is_set():
            try:
                port = self._config[CONF_SERIAL_PORT]
                if port.startswith("socket://"):
                    serial_port = serial.serial_for_url(port, timeout=1)
                else:
                    serial_port = serial.Serial(
                        port,
                        baudrate=self._config[CONF_BAUDRATE],
                        bytesize=serial.EIGHTBITS,
                        parity=parity,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=1,
                        rtscts=False,
                        dsrdtr=False,
                        exclusive=True,
                    )
                with serial_port:
                    if not port.startswith("socket://"):
                        serial_port.dtr = False
                        serial_port.rts = False
                    with self._serial_lock:
                        self._serial = serial_port
                    LOGGER.info("Connected to Novus bus at %s", serial_port.port)
                    while not self._stop_event.is_set():
                        data = serial_port.read(serial_port.in_waiting or 1)
                        if not data:
                            continue
                        timestamp = dt_util.utcnow().isoformat()
                        self.raw_log.append((timestamp, data.hex()))
                        self.passive_recording.feed(data, timestamp)
                        for readings in self._parser.feed(data):
                            self.hass.loop.call_soon_threadsafe(
                                self._async_publish, dict(readings)
                            )
            except (OSError, serial.SerialException) as err:
                if not self._stop_event.is_set():
                    LOGGER.warning("Novus serial reader disconnected: %s", err)
                    self._stop_event.wait(5)
            finally:
                with self._serial_lock:
                    self._serial = None

    def _send_frame(self, frame: bytes) -> None:
        """Write one frame to the bridge connection."""
        self.ensure_writable()
        with self._serial_lock:
            serial_port = self._serial
            if serial_port is None or not serial_port.port.startswith("socket://"):
                raise HomeAssistantError(
                    "Writing to the Novus bus requires the socket:// bridge connection"
                )
            serial_port.write(frame)

    async def async_set_ventilation_mode(self, mode: str) -> None:
        """Request a ventilation mode and wait until the unit reports it."""
        self.ensure_writable()
        if mode not in MODE_REQUEST_VALUES:
            raise HomeAssistantError(f"Unsupported ventilation mode: {mode}")
        frame = build_mode_request(mode)
        for _ in range(3):
            try:
                await self.hass.async_add_executor_job(self._send_frame, frame)
            except OSError as err:
                raise HomeAssistantError(f"Unable to write to the Novus bus: {err}") from err
            for _ in range(10):
                await asyncio.sleep(0.5)
                if self._values.get("ventilation_mode") == mode:
                    return
        raise HomeAssistantError(f"Novus did not confirm ventilation mode {mode}")

    async def async_set_power(self, on: bool) -> None:
        """Switch the unit on or off and wait until it reports the new state."""
        self.ensure_writable()
        wanted = ("running", "starting") if on else ("stopped",)
        for _ in range(3):
            await self._async_send(build_power_frame(on))
            for _ in range(10):
                await asyncio.sleep(0.5)
                if self._values.get("run_state") in wanted:
                    return
        raise HomeAssistantError(
            f"Novus did not confirm switching {'on' if on else 'off'}"
        )

    @callback
    def _async_daily_time_sync(self, now: datetime) -> None:
        """Start the scheduled clock synchronization."""
        self.hass.async_create_task(self._async_sync_clock_logged())

    async def _async_sync_clock_logged(self) -> None:
        try:
            await self.async_sync_clock()
        except HomeAssistantError as err:
            LOGGER.warning("Novus clock synchronization failed: %s", err)

    async def _async_send(self, frame: bytes) -> None:
        self.ensure_writable()
        try:
            await self.hass.async_add_executor_job(self._send_frame, frame)
        except OSError as err:
            raise HomeAssistantError(f"Unable to write to the Novus bus: {err}") from err

    def setting_value(self, key: str, actual: bool = False) -> int | float:
        """Return a menu setting last seen on the bus, else the configured one.

        While a setting is temporarily overridden, the original value is
        returned unless `actual` asks for what the unit currently runs.
        """
        original = self._values.get(f"{ORIGINAL_PREFIX}{key}")
        if not actual and isinstance(original, int) and not isinstance(original, bool):
            return original
        value = self._values.get(key)
        if (
            isinstance(value, int | float if key in FAN_IMBALANCE_KEYS else int)
            and not isinstance(value, bool)
        ):
            return value
        configured = self._config.get(key, SETTING_DEFAULTS[key])
        return float(configured) if key in FAN_IMBALANCE_KEYS else int(configured)

    def settings_from_bus(self) -> dict[str, int | float]:
        """Return the menu settings the unit itself has sent."""
        return {
            key: value
            for key in SETTING_DEFAULTS
            if isinstance(
                value := self._values.get(key),
                int | float if key in FAN_IMBALANCE_KEYS else int,
            )
            and not isinstance(value, bool)
            and f"{ORIGINAL_PREFIX}{key}" not in self._values
        }

    def temporary_settings(self) -> dict[str, int]:
        """Return settings temporarily overridden, with their original value."""
        return {
            key[len(ORIGINAL_PREFIX) :]: int(value)
            for key, value in self._values.items()
            if key.startswith(ORIGINAL_PREFIX) and isinstance(value, int)
        }

    def clear_temporary_settings(self) -> None:
        """Forget temporary overrides (their values were just written on purpose)."""
        for key in list(self.temporary_settings()):
            self._values.pop(f"{ORIGINAL_PREFIX}{key}", None)

    @property
    def show_fan_levels(self) -> bool:
        """Return whether regulated levels are shown instead of automatic."""
        return bool(self._config.get(CONF_SHOW_FAN_LEVELS, DEFAULT_SHOW_FAN_LEVELS))

    async def async_set_temporary_setting(self, key: str, value: int) -> None:
        """Write a setting, remembering its original value for later restore."""
        self.ensure_writable()
        marker = f"{ORIGINAL_PREFIX}{key}"
        new_override = marker not in self._values
        if new_override:
            self._values[marker] = self.setting_value(key)
        try:
            await self.async_write_settings({key: value})
        except HomeAssistantError:
            if new_override:
                self._values.pop(marker, None)
            raise

    async def async_restore_settings(self, keep: str | None = None) -> None:
        """Write back the original values of all temporary settings but `keep`."""
        self.ensure_writable()
        for key, original in self.temporary_settings().items():
            if key == keep:
                continue
            await self.async_write_settings({key: original})
            self._values.pop(f"{ORIGINAL_PREFIX}{key}", None)
        self._counter_store.async_delay_save(self._persisted_values, 5)

    def message_log(self) -> list[dict[str, str | int]]:
        """Return the last messages stored in the unit (newest first)."""
        entries = []
        for slot in range(3):
            value = self._values.get(f"message_log_{slot}")
            if isinstance(value, str) and value.count("|") >= 2:
                time, code, detail = value.split("|", 2)
                entries.append({"time": time, "code": int(code), "detail": detail})
        return entries

    def message_time(self) -> datetime | None:
        """Return when the latest message occurred."""
        message = self._values.get("message")
        if message not in (None, "none"):
            for entry in self.message_history():
                if entry["message"] == message:
                    return datetime.fromisoformat(entry["time"])
        log = self.message_log()
        if log:
            return datetime.fromisoformat(str(log[0]["time"])).replace(
                tzinfo=dt_util.DEFAULT_TIME_ZONE
            )
        return None

    def message_history(self) -> list[dict[str, str]]:
        """Return the last unit messages seen on the bus (newest first)."""
        try:
            return json.loads(str(self._values.get("message_history", "[]")))
        except ValueError:
            return []

    def status_events(self) -> list[dict[str, str]]:
        """Return the last run state and air path changes (newest first)."""
        try:
            return json.loads(str(self._values.get("status_events", "[]")))
        except ValueError:
            return []

    def transient_event(self) -> dict[str, str] | None:
        """Return the newest status event of a state that is still a transition."""
        data = self._values
        run_state = data.get("run_state")
        events = self.status_events()
        if run_state == "stopped":
            # The unit reports no shutdown phase; show it briefly after the change.
            for event in events:
                if event["kind"] == "run_state":
                    age = dt_util.now() - datetime.fromisoformat(event["time"])
                    return event if event["state"] == "stopped" and age < timedelta(seconds=45) else None
            return None
        for event in events:
            if event["kind"] == "run_state" and run_state not in (None, "running"):
                return event
            if (
                event["kind"] == "air_path"
                and run_state == "running"
                and data.get("air_path") not in (None, "heat_recovery", "bypass")
            ):
                run_event = next((e for e in events if e["kind"] == "run_state"), None)
                if (
                    event["state"] == "unknown"
                    and run_event
                    and dt_util.now() - datetime.fromisoformat(run_event["time"])
                    < timedelta(minutes=2)
                ):
                    # Air path is unknown while the unit ramps up after switching on.
                    return {**run_event, "state": "starting"}
                return event
        return None

    def _record_status_events(self, readings: dict[str, NovusValue]) -> None:
        """Log every change of the run state or the air path."""
        history = self.status_events()
        for kind in ("run_state", "air_path"):
            new = readings.get(kind)
            old = self._values.get(kind)
            if new is None or old is None or new == old:
                continue
            raw = readings.get("run_state_raw") if kind == "run_state" else None
            history.insert(
                0,
                {
                    "time": dt_util.now().isoformat(timespec="seconds"),
                    "kind": kind,
                    "state": str(new),
                    "raw": "" if raw is None else str(raw),
                },
            )
        if history != self.status_events():
            self._values["status_events"] = json.dumps(history[:10])

    def _record_message(self, message: str) -> None:
        """Remember when a message appeared or was cleared."""
        if self._values.get("message") is None and message == "none":
            return
        history = self.message_history()
        history.insert(0, {"time": dt_util.now().isoformat(timespec="seconds"), "message": message})
        self._values["message_history"] = json.dumps(history[:10])

    def settings_not_read(self) -> list[str]:
        """Return menu settings never seen on the bus (fallback values apply)."""
        return [
            key
            for key in SETTING_DEFAULTS
            if not isinstance(
                self._values.get(key), int | float if key in FAN_IMBALANCE_KEYS else int
            )
        ]

    async def async_write_settings(self, settings: dict[str, int | float]) -> None:
        """Store menu settings in the unit, as the panel does when saving."""
        self.ensure_writable()
        for key in FAN_IMBALANCE_KEYS:
            if key in settings and (
                isinstance(settings[key], bool)
                or not isinstance(settings[key], int | float)
                or settings[key] * 2 not in range(-100, 101)
            ):
                raise HomeAssistantError("Fan imbalance must be -50 to 50 in steps of 0.5")
        for key, value in settings.items():
            if key not in SETTING_DEFAULTS:
                continue
            value = value if key in FAN_IMBALANCE_KEYS else int(value)
            await self._async_send(build_setting_frame(key, value))
            self._values[key] = value
            await asyncio.sleep(1)
        self._counter_store.async_delay_save(self._persisted_values, 5)
        self.async_set_updated_data(dict(self._values))

    def unit_values(self) -> dict[str, NovusValue]:
        """Return all known values, including restored ones."""
        return dict(self._values)

    async def async_write_parameters(self, parameters: dict[int, int]) -> None:
        """Store changed unit parameters and selections (register -> raw value)."""
        self.ensure_writable()
        async with self._parameter_write_lock:
            await self._async_write_parameters(parameters)

    async def _async_write_parameters(self, parameters: dict[int, int]) -> None:
        """Serialize parameter writes with summer ventilation changes."""
        self.ensure_writable()
        for register, value in parameters.items():
            if register == 0x1B:
                word = self._values.get("param_1b")
                if not isinstance(word, int):
                    raise HomeAssistantError("The unit configuration has not been received")
                # This options field changes installation only, not summer mode.
                value = (word & ~0x04) | (value & 0x04)
            frame = (
                build_parameter_frame(register, int(value))
                if register in PARAMETER_LIMITS
                else build_select_frame(register, int(value))
            )
            await self._async_send(frame)
            self._values[f"param_{register:02x}"] = int(value)
            await asyncio.sleep(1)
        self._counter_store.async_delay_save(self._persisted_values, 5)
        self.async_set_updated_data(dict(self._values))

    async def async_set_summer_ventilation(self, on: bool) -> None:
        """Change only the summer flag and wait for its bus feedback."""
        self.ensure_writable()
        async with self._parameter_write_lock:
            if self.bypass_present is not False:
                raise HomeAssistantError(
                    "Summer ventilation requires a unit configured without a bypass"
                )
            word = self._values["param_1b"]
            if bool(word & 0x80) == on:
                return
            value = (word | 0x80) if on else (word & ~0x80)
            self._plant_word_received.clear()
            await self._async_send(build_select_frame(0x1B, value))
            try:
                async with asyncio.timeout(15):
                    while True:
                        await self._plant_word_received.wait()
                        self._plant_word_received.clear()
                        if self.bypass_present is not False:
                            raise HomeAssistantError(
                                "The unit no longer reports a configuration without a bypass"
                            )
                        if bool(self._values["param_1b"] & 0x80) == on:
                            return
            except TimeoutError as err:
                raise HomeAssistantError(
                    "Novus did not confirm the summer ventilation setting"
                ) from err

    def filter_interval_days(self) -> int:
        """Return the filter interval last seen on the bus, in days."""
        seconds = self._values.get("filter_interval")
        if isinstance(seconds, float | int) and not isinstance(seconds, bool):
            return round(seconds / 86400)
        return DEFAULT_FILTER_INTERVAL_DAYS

    async def async_set_filter_interval(self, days: int) -> None:
        """Store the filter interval in the unit, as the panel does."""
        self.ensure_writable()
        if days not in FILTER_INTERVAL_DAYS:
            raise HomeAssistantError("Filter interval must be 30 to 180 days in steps of 10")
        await self._async_send(build_filter_interval_frame(days))
        self._values["filter_interval"] = days * 86400
        self.async_set_updated_data(dict(self._values))

    async def async_reset_filter(self) -> None:
        """Restart the filter run time at the configured interval."""
        self.ensure_writable()
        days = self.filter_interval_days()
        if days not in FILTER_INTERVAL_DAYS:
            raise HomeAssistantError(f"Unexpected filter interval of {days} days")
        await self._async_send(build_filter_reset_frame(days))
        self._values["filter_time_remaining"] = days * 86400
        self.async_set_updated_data(dict(self._values))

    @property
    def bypass_present(self) -> bool | None:
        """Return installation bit 0x04, independently of activation bit 0x08."""
        return bypass_is_present(self._values.get("param_1b"))

    def _plant_value(self, register: int) -> int | None:
        value = self._values.get(f"param_{register:02x}")
        return value if isinstance(value, int) else None

    @property
    def installed_parts(self) -> dict[str, bool | None]:
        """Return which optional parts the plant has (None while unknown)."""
        reheater, ewt, defroster = (self._plant_value(r) for r in (0x21, 0x24, 0x1E))
        installed = {0x08: False, 0x0C: True, 0x1C: True}.get(
            self._values.get("defroster_status_raw")
        )
        known_type = defroster in (1, 2, 3)
        if installed is None and known_type:
            installed = True
        return {
            "bypass_present": self.bypass_present,
            "reheater_present": None if reheater is None else reheater != 0,
            "ewt_present": None if ewt is None else ewt != 0,
            "defroster_installed": installed,
            "defroster_present": (
                False if installed is False else defroster in (1, 2) if known_type else None
            ),
            "brine_defroster_present": (
                False if installed is False else defroster == 3 if known_type else None
            ),
        }

    async def async_request_dump(self) -> None:
        """Ask the unit to resend all registers (briefly disturbs the panel)."""
        self.ensure_writable()
        await self._async_send(build_memory_dump_request())

    async def async_sync_clock(self) -> None:
        """Set the unit's date and time to Home Assistant's local time."""
        self.ensure_writable()
        for _ in range(3):
            moment = dt_util.now()
            plant = self._values.get("clock")
            if not isinstance(plant, str) or plant[:10] != moment.date().isoformat():
                await self._async_send(build_date_frame(moment))
                await asyncio.sleep(1.5)
            await asyncio.sleep(1 - dt_util.now().microsecond / 1_000_000)
            await self._async_send(build_time_frame(dt_util.now()))
            for _ in range(30):
                await asyncio.sleep(0.5)
                drift = self._values.get("clock_drift")
                if self._clock_seen_after_sync() and isinstance(drift, float) and abs(drift) <= 3:
                    return
        raise HomeAssistantError("Novus did not confirm the new time")

    def _clock_seen_after_sync(self) -> bool:
        """Return whether a clock broadcast arrived within the last 6 seconds."""
        return (
            dt_util.utcnow().timestamp() - self._last_clock_at < 6
        )

    def _async_publish(self, readings: dict[str, NovusValue]) -> None:
        """Publish decoded readings on Home Assistant's event loop."""
        if self._stop_event.is_set():
            return
        clock = readings.get("clock")
        if isinstance(clock, str):
            now = dt_util.now().replace(tzinfo=None)
            readings["clock_drift"] = round(
                (datetime.fromisoformat(clock) - now).total_seconds(), 1
            )
            self._last_clock_at = dt_util.utcnow().timestamp()
        if "message" in readings and readings["message"] != self._values.get("message"):
            self._record_message(str(readings["message"]))
        self._record_status_events(readings)
        self._values.update(readings)
        if "param_1b" in readings:
            self._plant_word_received.set()
        if any(key in PERSISTED_KEYS or key.startswith("param_") for key in readings) or (
            "status_events" in self._values and ("run_state" in readings or "air_path" in readings)
        ):
            self._counter_store.async_delay_save(self._persisted_values, 5)
        self.async_set_updated_data(dict(self._values))

    @property
    def is_stopped(self) -> bool:
        """Return whether the unit reports that it is switched off."""
        return self._values.get("run_state") == "stopped"

    def fan_level_percentage(self, mode: str) -> int | None:
        """Return the percentage of the level a mode runs at (boost: 3, away: 1)."""
        key = {
            "level_1": CONF_FAN_LEVEL_1_PERCENTAGE,
            "level_2": CONF_FAN_LEVEL_2_PERCENTAGE,
            "level_3": CONF_FAN_LEVEL_3_PERCENTAGE,
            "boost": CONF_FAN_LEVEL_3_PERCENTAGE,
            "away": CONF_FAN_LEVEL_1_PERCENTAGE,
        }.get(mode)
        return None if key is None else self.setting_value(key, actual=True)
