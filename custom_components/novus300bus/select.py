"""Ventilation mode selection for the Paul Novus 300 bus."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NovusCoordinator
from .fan import LEVEL_KEYS
from .protocol import MODE_REQUEST_VALUES

MODE_ORDER = ("automatic", "level_1", "level_2", "level_3", "away", "boost")


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the ventilation mode select."""
    async_add_entities([NovusModeSelect(entry.runtime_data)])


class NovusModeSelect(CoordinatorEntity[NovusCoordinator], SelectEntity):
    """Select the ventilation mode on the RS-485 bus."""

    _attr_has_entity_name = True
    _attr_unique_id = "novus300bus_mode_select"
    _attr_translation_key = "ventilation_mode"
    _attr_icon = "mdi:fan"
    _attr_options = [mode for mode in MODE_ORDER if mode in MODE_REQUEST_VALUES]

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self.entity_id = "select.novus300_ventilation_mode"
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300 (FOCUS250)",
            "sw_version": "BUS 1.7.1",
        }

    @property
    def available(self) -> bool:
        """Return whether the unit is switched on."""
        return super().available and not self.coordinator.is_stopped

    @property
    def current_option(self) -> str | None:
        """Return the mode last reported by the unit."""
        mode = self.coordinator.data.get("ventilation_mode")
        if (
            not self.coordinator.show_fan_levels
            and LEVEL_KEYS.get(mode) in self.coordinator.temporary_settings()
        ):
            return "automatic"
        return mode if mode in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Request the selected mode on the bus."""
        await self.coordinator.async_set_ventilation_mode(option)
        await self.coordinator.async_restore_settings()
        self.async_write_ha_state()
