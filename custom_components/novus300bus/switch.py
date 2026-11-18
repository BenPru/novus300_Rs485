"""Switches for the Paul Novus 300 bus integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AWAY_DURATION_MINUTES,
    CONF_BOOST_DURATION_MINUTES,
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
)
from .coordinator import NovusCoordinator

DEVICE_INFO = {
    "identifiers": {("novus300bus", "novus300")},
    "name": "Paul Novus 300",
    "manufacturer": "Paul",
    "model": "Novus 300 (FOCUS250)",
    "sw_version": "BUS 1.7.1",
}

RUN_STATE_ICONS = {
    "stopped": "mdi:stop-circle-outline",
    "running": "mdi:play-circle-outline",
    "starting": "mdi:progress-clock",
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the Novus switches."""
    coordinator: NovusCoordinator = entry.runtime_data
    async_add_entities([NovusPowerSwitch(coordinator), NovusBypassSwitch(coordinator)])


class NovusPowerSwitch(CoordinatorEntity[NovusCoordinator], SwitchEntity):
    """Show and switch the unit's operating state on the bus."""

    _attr_has_entity_name = True
    _attr_name = "Betriebsstatus"
    _attr_unique_id = "novus300bus_power"

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the operating state switch."""
        super().__init__(coordinator)
        self.entity_id = "switch.novus300_power"
        self._attr_device_info = DEVICE_INFO

    @property
    def is_on(self) -> bool | None:
        """Return whether the unit is running or starting."""
        state = self.coordinator.data.get("run_state")
        if state in ("running", "starting"):
            return True
        return False if state == "stopped" else None

    @property
    def icon(self) -> str:
        """Return an icon matching the run state."""
        return RUN_STATE_ICONS.get(
            self.coordinator.data.get("run_state"), "mdi:help-circle-outline"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the unit's run state."""
        attributes: dict[str, Any] = {
            "run_state": self.coordinator.data.get("run_state")
        }
        raw = self.coordinator.data.get("run_state_raw")
        if isinstance(raw, int):
            attributes["raw_value"] = raw
        for key in ("serial_panel", "serial_fan_slave", "serial_defroster"):
            if isinstance(serial := self.coordinator.data.get(key), str):
                attributes[key] = serial
        settings = self.coordinator.setting_value
        attributes["config_fan_level_1_percentage"] = settings(
            CONF_FAN_LEVEL_1_PERCENTAGE
        )
        attributes["config_fan_level_2_percentage"] = settings(
            CONF_FAN_LEVEL_2_PERCENTAGE
        )
        attributes["config_fan_level_3_percentage"] = settings(
            CONF_FAN_LEVEL_3_PERCENTAGE
        )
        attributes["config_boost_duration_minutes"] = settings(
            CONF_BOOST_DURATION_MINUTES
        )
        attributes["config_away_minutes_per_hour"] = settings(
            CONF_AWAY_DURATION_MINUTES
        )
        attributes["config_filter_interval_days"] = (
            self.coordinator.filter_interval_days()
        )
        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the unit on."""
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the unit off."""
        await self.coordinator.async_set_power(False)


class NovusBypassSwitch(CoordinatorEntity[NovusCoordinator], SwitchEntity):
    """Show whether the bypass is open (read-only until writing is known)."""

    _attr_has_entity_name = True
    _attr_name = "Bypass geöffnet"
    _attr_unique_id = "novus300bus_bypass"

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the bypass switch."""
        super().__init__(coordinator)
        self.entity_id = "switch.novus300_bypass"
        self._attr_device_info = DEVICE_INFO

    @property
    def available(self) -> bool:
        """Return whether the status word has been received."""
        return (
            "bypass_open" in self.coordinator.data
            and not self.coordinator.is_stopped
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the bypass is open."""
        return self.coordinator.data.get("bypass_open")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the air path and its status word."""
        data = self.coordinator.data
        attributes: dict[str, Any] = {"air_path": data.get("air_path")}
        if isinstance(raw := data.get("status_word"), int):
            attributes["raw_value"] = raw
        return attributes

    @property
    def icon(self) -> str:
        """Return an icon matching the current bypass state."""
        return (
            "mdi:arrow-right-bold-circle-outline"
            if self.is_on
            else "mdi:heat-wave"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Reject writes: the bypass cannot be set over the bus yet."""
        raise HomeAssistantError("The bypass is read-only")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Reject writes: the bypass cannot be set over the bus yet."""
        raise HomeAssistantError("The bypass is read-only")
