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
from homeassistant.helpers.restore_state import RestoreEntity
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
    translation_key: str | None = None


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
        "Lüfteransteuerung",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "ventilation_mode",
        "Lüftungsstufe",
        SensorDeviceClass.ENUM,
        options=(
            "standby",
            "automatic",
            "level_1",
            "level_2",
            "level_3",
            "boost",
            "away",
            "unknown",
        ),
        translation_key="ventilation_mode",
    ),
    NovusSensorDescription(
        "run_state",
        "Betriebsstatus",
        SensorDeviceClass.ENUM,
        options=("stopped", "running", "starting", "unknown"),
        translation_key="run_state",
    ),
    NovusSensorDescription(
        "air_path",
        "Luftweg",
        SensorDeviceClass.ENUM,
        options=("heat_recovery", "bypass", "transition", "unknown"),
        translation_key="air_path",
    ),
    NovusSensorDescription(
        "operating_time",
        "Gesamtbetriebszeit",
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        SensorStateClass.TOTAL_INCREASING,
        EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "fan_operating_time",
        "Lüfterbetriebszeit",
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        SensorStateClass.TOTAL_INCREASING,
        EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "filter_time_remaining",
        "Filter Restlaufzeit",
        SensorDeviceClass.DURATION,
        UnitOfTime.DAYS,
        SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NovusSensorDescription(
        "filter_interval",
        "Filterintervall",
        SensorDeviceClass.DURATION,
        UnitOfTime.DAYS,
        SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Novus sensors."""
    coordinator: NovusCoordinator = entry.runtime_data
    async_add_entities(
        [NovusSensor(coordinator, description) for description in SENSORS]
    )


class NovusSensor(CoordinatorEntity[NovusCoordinator], SensorEntity, RestoreEntity):
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
        self._attr_translation_key = description.translation_key
        self._restored_value: float | None = None
        self.entity_id = f"sensor.novus300_{description.key}"
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300",
        }

    async def async_added_to_hass(self) -> None:
        """Restore duration readings until their next bus update."""
        await super().async_added_to_hass()
        if self._description.key not in (
            "operating_time",
            "fan_operating_time",
            "filter_time_remaining",
            "filter_interval",
        ):
            return

        last_state = await self.async_get_last_state()
        if (
            last_state is None
            or self._description.key in self.coordinator.data
            or last_state.attributes.get("unit_of_measurement")
            not in (UnitOfTime.SECONDS, UnitOfTime.HOURS, UnitOfTime.DAYS)
        ):
            return

        try:
            restored_value = float(last_state.state)
        except ValueError:
            return

        previous_unit = last_state.attributes["unit_of_measurement"]
        if (
            previous_unit == UnitOfTime.SECONDS
            and self._description.key
            in ("operating_time", "fan_operating_time")
        ):
            restored_value /= 3600
        elif (
            previous_unit == UnitOfTime.SECONDS
            and self._description.key
            in ("filter_time_remaining", "filter_interval")
        ):
            restored_value /= 86400

        self._restored_value = round(restored_value, 2)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return whether this register has been observed."""
        return (
            self._description.key in self.coordinator.data
            or self._restored_value is not None
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the decoded register value."""
        value = self.coordinator.data.get(self._description.key)
        if value is None:
            return self._restored_value
        if self._description.key == "fan_setpoint":
            fixed_level_value = self.coordinator.fan_level_percentage(
                self.coordinator.data.get("ventilation_mode", "")
            )
            if fixed_level_value is not None:
                return fixed_level_value
        if self._description.key in (
            "operating_time",
            "fan_operating_time",
        ) and isinstance(
            value, float | int
        ):
            return round(value / 3600, 2)
        if (
            self._description.key in ("filter_time_remaining", "filter_interval")
            and isinstance(value, float | int)
        ):
            return round(value / 86400, 2)
        return value if isinstance(value, float | int | str) else None

    @property
    def icon(self) -> str | None:
        """Return an icon matching the current operating state."""
        if self._description.key == "fan_setpoint":
            return "mdi:fan"
        state_icons = {
            "run_state": {
                "stopped": "mdi:stop-circle-outline",
                "running": "mdi:play-circle-outline",
                "starting": "mdi:progress-clock",
                "unknown": "mdi:help-circle-outline",
            },
            "air_path": {
                "heat_recovery": "mdi:heat-wave",
                "bypass": "mdi:arrow-right-bold-circle-outline",
                "transition": "mdi:swap-horizontal-circle-outline",
                "unknown": "mdi:help-circle-outline",
            },
            "ventilation_mode": {
                "standby": "mdi:power-standby",
                "automatic": "mdi:auto-mode",
                "level_1": "mdi:fan-speed-1",
                "level_2": "mdi:fan-speed-2",
                "level_3": "mdi:fan-speed-3",
                "boost": "mdi:weather-windy",
                "away": "mdi:home-export-outline",
                "unknown": "mdi:help-circle-outline",
            },
        }
        return state_icons.get(self._description.key, {}).get(self.native_value)

    @property
    def extra_state_attributes(self) -> dict[str, float | int | str]:
        """Expose source registers and mapped fixed levels as attributes."""
        if self._description.key == "fan_setpoint":
            bus_value = self.coordinator.data.get("fan_setpoint")
            panel_mode = self.coordinator.data.get("ventilation_mode")
            if isinstance(bus_value, float | int) and isinstance(panel_mode, str):
                return {
                    "bus_value": bus_value,
                    "panel_mode": panel_mode,
                }
        raw_key = {
            "run_state": "run_state_raw",
            "air_path": "status_word",
            "ventilation_mode": "ventilation_mode_raw",
        }.get(self._description.key)
        if raw_key is None:
            return {}
        raw_value = self.coordinator.data.get(raw_key)
        return {"raw_value": raw_value} if isinstance(raw_value, int) else {}
