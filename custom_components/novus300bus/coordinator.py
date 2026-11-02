"""Serial coordinator for the Paul Novus 300 bus."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import serial
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BAUDRATE, CONF_PARITY, CONF_SERIAL_PORT, DOMAIN
from .protocol import NovusFrameParser

LOGGER = logging.getLogger(__name__)


class NovusCoordinator(DataUpdateCoordinator[dict[str, float | int | bool]]):
    """Read bus frames continuously in a dedicated serial thread."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN)
        self._config = config
        self._parser = NovusFrameParser()
        self._serial: serial.Serial | None = None
        self._serial_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._values: dict[str, float | int | bool] = {}
        self.data = {}

    async def async_start(self) -> None:
        """Start the serial reader thread."""
        self._thread = threading.Thread(
            target=self._read_serial,
            name="novus300bus-reader",
            daemon=True,
        )
        self._thread.start()

    async def async_stop(self) -> None:
        """Stop the serial reader thread."""
        self._stop_event.set()
        with self._serial_lock:
            if self._serial is not None:
                self._serial.close()
        if self._thread is not None:
            await self.hass.async_add_executor_job(self._thread.join, 5)

    def _read_serial(self) -> None:
        """Read and decode the serial byte stream until stopped."""
        parity = (
            serial.PARITY_MARK
            if self._config[CONF_PARITY] == "mark"
            else serial.PARITY_NONE
        )
        while not self._stop_event.is_set():
            try:
                with serial.Serial(
                    self._config[CONF_SERIAL_PORT],
                    baudrate=self._config[CONF_BAUDRATE],
                    bytesize=serial.EIGHTBITS,
                    parity=parity,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                    rtscts=False,
                    dsrdtr=False,
                    exclusive=True,
                ) as serial_port:
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

    def _async_publish(self, readings: dict[str, float | int | bool]) -> None:
        """Publish decoded readings on Home Assistant's event loop."""
        self._values.update(readings)
        self.async_set_updated_data(dict(self._values))
