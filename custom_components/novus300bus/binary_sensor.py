"""Binary sensors for the Paul Novus 300 bus integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NovusCoordinator
from .switch import DEVICE_INFO


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the Novus binary sensors."""
    coordinator: NovusCoordinator = entry.runtime_data
    async_add_entities(
        [
            NovusMessageActive(coordinator),
            NovusFilterDue(coordinator),
            NovusBoostActive(coordinator),
        ]
    )


class NovusBinarySensor(CoordinatorEntity[NovusCoordinator], BinarySensorEntity):
    """Base class for the Novus binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NovusCoordinator, key: str) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"novus300bus_{key}"
        self.entity_id = f"binary_sensor.novus300_{key}"
        self._attr_device_info = DEVICE_INFO


class NovusMessageActive(NovusBinarySensor):
    """On while the unit reports a message."""

    _attr_name = "Meldung aktiv"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the message sensor."""
        super().__init__(coordinator, "message_active")

    @property
    def available(self) -> bool:
        """Return whether a message state has been received."""
        return "message" in self.coordinator.data

    @property
    def is_on(self) -> bool:
        """Return whether a message is pending."""
        return self.coordinator.data.get("message") != "none"


class NovusFilterDue(NovusBinarySensor):
    """On when the filter runtime has expired."""

    _attr_name = "Filterwechsel fällig"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the filter sensor."""
        super().__init__(coordinator, "filter_due")

    @property
    def available(self) -> bool:
        """Return whether the remaining filter time is known."""
        return isinstance(
            self.coordinator.data.get("filter_time_remaining"), float | int
        )

    @property
    def is_on(self) -> bool:
        """Return whether the filter runtime is used up."""
        return self.coordinator.data["filter_time_remaining"] <= 0


class NovusBoostActive(NovusBinarySensor):
    """On while the boost ventilation runs."""

    _attr_name = "Stoßlüftung aktiv"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the boost sensor."""
        super().__init__(coordinator, "boost_active")

    @property
    def available(self) -> bool:
        """Return whether the ventilation mode is known."""
        return "ventilation_mode" in self.coordinator.data

    @property
    def is_on(self) -> bool:
        """Return whether the boost mode is active."""
        return self.coordinator.data.get("ventilation_mode") == "boost"
