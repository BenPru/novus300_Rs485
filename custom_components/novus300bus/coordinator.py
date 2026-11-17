"""Serial coordinator for the Paul Novus 300 bus."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
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
    CONF_AWAY_DURATION_MINUTES,
    CONF_BAUDRATE,
    CONF_BOOST_DURATION_MINUTES,
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
    DEFAULT_AWAY_DURATION_MINUTES,
    DEFAULT_BOOST_DURATION_MINUTES,
    DEFAULT_FILTER_INTERVAL_DAYS,
    CONF_DAILY_TIME_SYNC,
    DAILY_TIME_SYNC_HOUR,
    DEFAULT_DAILY_TIME_SYNC,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    DEFAULT_FAN_LEVEL_1_PERCENTAGE,
    DEFAULT_FAN_LEVEL_2_PERCENTAGE,
    DEFAULT_FAN_LEVEL_3_PERCENTAGE,
    DOMAIN,
)
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
    build_mode_request,
    build_setting_frame,
    build_time_frame,
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
    "message_log_0",
    "message_log_1",
    "message_log_2",
    "message_history",
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
}


class NovusCoordinator(DataUpdateCoordinator[dict[str, NovusValue]]):
    """Read bus frames continuously in a dedicated serial thread."""

    def __init__(
        self, hass: HomeAssistant, config: dict[str, Any], entry_id: str
    ) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN)
        self._config = config
        self._parser = NovusFrameParser()
        self._serial: serial.Serial | None = None
        self._serial_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._values: dict[str, NovusValue] = dict(KNOWN_IDENTITIES)
        self._counter_store = Store[dict[str, NovusValue]](
            hass, 1, f"{DOMAIN}.{entry_id}.counters"
        )
        self._cancel_time_sync = None
        self._last_clock_at = 0.0
        self.data = {}

    async def async_start(self) -> None:
        """Start the serial reader thread."""
        await self._async_restore_counters()
        self._thread = threading.Thread(
            target=self._read_serial,
            name="novus300bus-reader",
            daemon=True,
        )
        self._thread.start()
        if self._config.get(CONF_DAILY_TIME_SYNC, DEFAULT_DAILY_TIME_SYNC) and str(
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
            if key in PERSISTED_KEYS and isinstance(value, float | int | str)
        }

    async def async_stop(self) -> None:
        """Stop the serial reader thread."""
        self._stop_event.set()
        if self._cancel_time_sync is not None:
            self._cancel_time_sync()
            self._cancel_time_sync = None
        await self.hass.async_add_executor_job(self._close_serial)
        if self._thread is not None:
            await self.hass.async_add_executor_job(self._thread.join, 5)

    def _close_serial(self) -> None:
        """Close the serial connection outside Home Assistant's event loop."""
        with self._serial_lock:
            if self._serial is not None:
                self._serial.close()

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
        with self._serial_lock:
            serial_port = self._serial
            if serial_port is None or not serial_port.port.startswith("socket://"):
                raise HomeAssistantError(
                    "Writing to the Novus bus requires the socket:// bridge connection"
                )
            serial_port.write(frame)

    async def async_set_ventilation_mode(self, mode: str) -> None:
        """Request a ventilation mode and wait until the unit reports it."""
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
        try:
            await self.hass.async_add_executor_job(self._send_frame, frame)
        except OSError as err:
            raise HomeAssistantError(f"Unable to write to the Novus bus: {err}") from err

    def setting_value(self, key: str) -> int:
        """Return a menu setting last seen on the bus, else the configured one."""
        value = self._values.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        configured = self._config.get(key, SETTING_DEFAULTS[key])
        return int(configured)

    def settings_from_bus(self) -> dict[str, int]:
        """Return the menu settings the unit itself has sent."""
        return {
            key: value
            for key in SETTING_DEFAULTS
            if isinstance(value := self._values.get(key), int)
            and not isinstance(value, bool)
        }

    def message_log(self) -> list[dict[str, str | int]]:
        """Return the last messages stored in the unit (newest first)."""
        entries = []
        for slot in range(3):
            value = self._values.get(f"message_log_{slot}")
            if isinstance(value, str) and value.count("|") >= 2:
                time, code, detail = value.split("|", 2)
                entries.append({"time": time, "code": int(code), "detail": detail})
        return entries

    def message_history(self) -> list[dict[str, str]]:
        """Return the last unit messages seen on the bus (newest first)."""
        try:
            return json.loads(str(self._values.get("message_history", "[]")))
        except ValueError:
            return []

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
            if not isinstance(self._values.get(key), int)
        ]

    async def async_write_settings(self, settings: dict[str, int]) -> None:
        """Store menu settings in the unit, as the panel does when saving."""
        for key, value in settings.items():
            if key not in SETTING_DEFAULTS:
                continue
            await self._async_send(build_setting_frame(key, int(value)))
            self._values[key] = int(value)
            await asyncio.sleep(1)
        self._counter_store.async_delay_save(self._persisted_values, 5)
        self.async_set_updated_data(dict(self._values))

    def filter_interval_days(self) -> int:
        """Return the filter interval last seen on the bus, in days."""
        seconds = self._values.get("filter_interval")
        if isinstance(seconds, float | int) and not isinstance(seconds, bool):
            return round(seconds / 86400)
        return DEFAULT_FILTER_INTERVAL_DAYS

    async def async_set_filter_interval(self, days: int) -> None:
        """Store the filter interval in the unit, as the panel does."""
        if days not in FILTER_INTERVAL_DAYS:
            raise HomeAssistantError("Filter interval must be 30 to 180 days in steps of 10")
        await self._async_send(build_filter_interval_frame(days))
        self._values["filter_interval"] = days * 86400
        self.async_set_updated_data(dict(self._values))

    async def async_reset_filter(self) -> None:
        """Restart the filter run time at the configured interval."""
        days = self.filter_interval_days()
        if days not in FILTER_INTERVAL_DAYS:
            raise HomeAssistantError(f"Unexpected filter interval of {days} days")
        await self._async_send(build_filter_reset_frame(days))
        self._values["filter_time_remaining"] = days * 86400
        self.async_set_updated_data(dict(self._values))

    async def async_sync_clock(self) -> None:
        """Set the unit's date and time to Home Assistant's local time."""
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
        clock = readings.get("clock")
        if isinstance(clock, str):
            now = dt_util.now().replace(tzinfo=None)
            readings["clock_drift"] = round(
                (datetime.fromisoformat(clock) - now).total_seconds(), 1
            )
            self._last_clock_at = dt_util.utcnow().timestamp()
        if "message" in readings and readings["message"] != self._values.get("message"):
            self._record_message(str(readings["message"]))
        self._values.update(readings)
        if any(key in PERSISTED_KEYS for key in readings):
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
        return None if key is None else self.setting_value(key)
