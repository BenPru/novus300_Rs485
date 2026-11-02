"""Binary sensors for the Paul Novus 300 bus."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NovusCoordinator


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Novus binary sensors."""
    coordinator: NovusCoordinator = entry.runtime_data
    async_add_entities([NovusBypassSensor(coordinator)])


class NovusBypassSensor(CoordinatorEntity[NovusCoordinator], BinarySensorEntity):
    """Report whether air bypasses the heat exchanger."""

    _attr_has_entity_name = True
    _attr_name = "Bypass"
    _attr_unique_id = "novus300bus_bypass"
    _attr_translation_key = "bypass"

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the bypass sensor."""
        super().__init__(coordinator)
        self.entity_id = "binary_sensor.novus300_bypass"
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300",
        }

    @property
    def available(self) -> bool:
        """Return whether the status word has been received."""
        return "bypass_open" in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return whether the bypass is open."""
        return self.coordinator.data.get("bypass_open")

    @property
    def icon(self) -> str:
        """Return an icon matching the current bypass state."""
        return (
            "mdi:arrow-right-bold-circle-outline"
            if self.is_on
            else "mdi:heat-wave"
        )
