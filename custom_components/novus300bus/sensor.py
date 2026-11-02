"""Sensors for the Paul Novus 300 bus."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NovusCoordinator


@dataclass(frozen=True)
class NovusSensorDescription:
    """Describe a Novus sensor."""

    key: str
    name: str
    device_class: SensorDeviceClass | None = None
    native_unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None
    entity_category: EntityCategory | None = None
    options: tuple[str, ...] | None = None


SENSORS = (
    NovusSensorDescription(
        "supply_air_temperature",
        "Zuluft Temperatur Räume",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "outdoor_air_temperature",
        "Außenluft Temperatur",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "extract_air_temperature",
        "Abluft Temperatur Räume",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "exhaust_air_temperature",
        "Fortluft Temperatur",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "fan_setpoint",
        "Lüfter Sollwert",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "run_state",
        "Betriebsstatus",
        SensorDeviceClass.ENUM,
        options=("stopped", "running", "starting", "unknown"),
    ),
    NovusSensorDescription(
        "run_state_raw",
        "Betriebsstatus Rohwert",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "air_path",
        "Luftweg",
        SensorDeviceClass.ENUM,
        options=("heat_recovery", "bypass", "transition", "unknown"),
    ),
    NovusSensorDescription(
        "status_word",
        "Statuswort",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "operating_time",
        "Gesamtbetriebszeit",
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        SensorStateClass.TOTAL_INCREASING,
        EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "fan_operating_time",
        "Lüfterbetriebszeit",
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        SensorStateClass.TOTAL_INCREASING,
        EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "filter_time_remaining",
        "Filter Restlaufzeit",
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "filter_interval",
        "Filterintervall",
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Novus sensors."""
    coordinator: NovusCoordinator = entry.runtime_data
    async_add_entities(
        [NovusSensor(coordinator, description) for description in SENSORS]
    )


class NovusSensor(CoordinatorEntity[NovusCoordinator], SensorEntity):
    """Expose a parsed Novus register as a sensor."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NovusCoordinator, description: NovusSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._description = description
        self._attr_name = description.name
        self._attr_unique_id = f"novus300bus_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_options = description.options
        self.entity_id = f"sensor.novus300_{description.key}"
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300",
        }

    @property
    def available(self) -> bool:
        """Return whether this register has been observed."""
        return self._description.key in self.coordinator.data

    @property
    def native_value(self) -> float | int | str | None:
        """Return the decoded register value."""
        value = self.coordinator.data.get(self._description.key)
        return value if isinstance(value, float | int | str) else None
