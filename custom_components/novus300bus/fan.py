"""Optional 0-10 V fan control through Tinkerforge."""

from __future__ import annotations

import logging
import threading
from typing import Any

from homeassistant.components.fan import ATTR_PERCENTAGE, FanEntity, FanEntityFeature
from homeassistant.const import STATE_OFF
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from tinkerforge.bricklet_industrial_analog_out_v2 import (
    BrickletIndustrialAnalogOutV2,
)
from tinkerforge.ip_connection import Error, IPConnection

from .const import (
    CONF_FAN_ENABLED,
    CONF_FAN_DEFAULT_PERCENTAGE,
    CONF_TINKERFORGE_HOST,
    CONF_TINKERFORGE_PORT,
    CONF_TINKERFORGE_UID,
    DEFAULT_FAN_DEFAULT_PERCENTAGE,
)
from .coordinator import NovusCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the optional Tinkerforge fan."""
    config = {**entry.data, **entry.options}
    if not config.get(CONF_FAN_ENABLED, False):
        return
    async_add_entities([NovusFanEntity(entry.runtime_data, config)])


class NovusFanEntity(CoordinatorEntity[NovusCoordinator], FanEntity):
    """Control the Novus 0-10 V fan input via Tinkerforge."""

    _attr_name = "Lüftung"
    _attr_unique_id = "novus300bus_fan"
    def __init__(self, coordinator: NovusCoordinator, config: dict[str, Any]) -> None:
        """Initialize the fan controller."""
        super().__init__(coordinator)
        self.entity_id = "fan.novus300"
        self._host = config[CONF_TINKERFORGE_HOST]
        self._port = config[CONF_TINKERFORGE_PORT]
        self._uid = config[CONF_TINKERFORGE_UID]
        self._default_percentage = config.get(
            CONF_FAN_DEFAULT_PERCENTAGE, DEFAULT_FAN_DEFAULT_PERCENTAGE
        )
        self._percentage: int | None = None
        self._available = False
        self._ipcon: IPConnection | None = None
        self._analog_out: BrickletIndustrialAnalogOutV2 | None = None
        self._lock = threading.Lock()
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300",
        }

    @property
    def available(self) -> bool:
        """Return whether the Tinkerforge controller is reachable."""
        return self._available

    @property
    def percentage(self) -> int | None:
        """Return the current 0-10 V control value."""
        return self._percentage

    @property
    def percentage_step(self) -> int:
        """Return the UI increment for the analog control value."""
        return 5

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return controls only while the panel selects automatic mode."""
        return (
            FanEntityFeature.SET_SPEED
            if self.coordinator.data.get("ventilation_mode") == "automatic"
            else FanEntityFeature(0)
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether a non-zero voltage is output."""
        return self._percentage is not None and self._percentage > 0

    @property
    def state(self) -> str:
        """Return the legacy numeric state used by existing automations."""
        return str(self._percentage) if self.is_on else STATE_OFF

    async def async_added_to_hass(self) -> None:
        """Read the existing analog output without changing it."""
        await self.async_update()

    async def async_will_remove_from_hass(self) -> None:
        """Close the Tinkerforge connection."""
        await self.hass.async_add_executor_job(self._disconnect)

    async def async_update(self) -> None:
        """Refresh the current analog output voltage."""
        try:
            self._percentage = await self.hass.async_add_executor_job(
                self._read_percentage
            )
        except (Error, OSError) as err:
            LOGGER.warning("Unable to read Novus fan control: %s", err)
            self._available = False
        else:
            self._available = True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the output at the requested or configured default percentage."""
        percentage = kwargs.get(ATTR_PERCENTAGE, self._default_percentage)
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set the analog output to zero."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the 0-10 V output percentage in panel automatic mode."""
        self._ensure_panel_automatic()
        target = max(0, min(100, round(percentage)))
        try:
            await self.hass.async_add_executor_job(self._set_percentage, target)
        except (Error, OSError) as err:
            self._available = False
            raise HomeAssistantError(
                f"Unable to set Novus fan control: {err}"
            ) from err
        self._percentage = target
        self._available = True
        self.async_write_ha_state()

    def _connect(self) -> BrickletIndustrialAnalogOutV2:
        """Connect to the configured Tinkerforge analog output."""
        if self._analog_out is None:
            self._ipcon = IPConnection()
            self._analog_out = BrickletIndustrialAnalogOutV2(self._uid, self._ipcon)
            self._ipcon.connect(self._host, self._port)
        return self._analog_out

    def _read_percentage(self) -> int:
        """Read the current analog output voltage as a percentage."""
        with self._lock:
            return round(self._connect().get_voltage() / 100)

    def _ensure_panel_automatic(self) -> None:
        """Allow analog control only while the panel selects automatic mode."""
        if self.coordinator.data.get("ventilation_mode") != "automatic":
            raise HomeAssistantError(
                "Novus fan control is available only in panel automatic mode"
            )

    def _set_percentage(self, percentage: int) -> None:
        """Set the analog output voltage."""
        with self._lock:
            analog_out = self._connect()
            analog_out.set_voltage(percentage * 100)
            analog_out.set_enabled(True)

    def _disconnect(self) -> None:
        """Disconnect the Tinkerforge client."""
        with self._lock:
            if self._ipcon is not None:
                self._ipcon.disconnect()
                self._ipcon = None
                self._analog_out = None
