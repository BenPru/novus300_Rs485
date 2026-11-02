"""Serial coordinator for the Paul Novus 300 bus."""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import timedelta
from typing import Any

import serial
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_BAUDRATE, CONF_PARITY, CONF_SERIAL_PORT, DOMAIN
from .protocol import NovusFrameParser, NovusValue, VENTILATION_MODES

LOGGER = logging.getLogger(__name__)

COUNTER_ENTITY_IDS = {
    "operating_time": "sensor.novus300_operating_time",
    "fan_operating_time": "sensor.novus300_fan_operating_time",
    "filter_time_remaining": "sensor.novus300_filter_time_remaining",
    "filter_interval": "sensor.novus300_filter_interval",
}

PERSISTED_KEYS = {
    *COUNTER_ENTITY_IDS,
    "ventilation_mode",
    "ventilation_mode_raw",
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
        self._values: dict[str, NovusValue] = {}
        self._counter_store = Store[dict[str, NovusValue]](
            hass, 1, f"{DOMAIN}.{entry_id}.counters"
        )
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

    def _async_publish(self, readings: dict[str, NovusValue]) -> None:
        """Publish decoded readings on Home Assistant's event loop."""
        self._values.update(readings)
        if any(key in PERSISTED_KEYS for key in readings):
            self._counter_store.async_delay_save(self._persisted_values, 5)
        self.async_set_updated_data(dict(self._values))
