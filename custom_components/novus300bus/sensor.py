"""Sensors for the Paul Novus 300 bus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_AWAY_DURATION_MINUTES
from .coordinator import NovusCoordinator
from .protocol import MESSAGES


MESSAGE_TEXTS = {
    "none": "Keine Meldung",
    "filter_change": "Filter wechseln",
    "input_error": "Fehler am Eingang",
    "bypass_error": "Fehler Bypass",
}

DETAIL_TEXTS = {
    "Out of range": "Wert außerhalb des Bereichs",
}


def describe_message(entry: dict[str, str | int]) -> str:
    """Return a readable line: time, code, message and translated detail."""
    code = int(entry["code"])
    text = MESSAGE_TEXTS.get(MESSAGES.get(code, ""), f"Meldung {code}")
    detail = str(entry["detail"])
    if detail.startswith("TempFromBu"):
        detail = f"Temperatur vom Bus ({detail})"
    detail = DETAIL_TEXTS.get(detail, detail)
    moment = datetime.fromisoformat(str(entry["time"]))
    line = f"{moment:%d.%m.%Y %H:%M:%S} · Code {code} · {text}"
    return f"{line} – {detail}" if detail else line


LIVE_KEYS = (
    "supply_air_temperature",
    "outdoor_air_temperature",
    "extract_air_temperature",
    "exhaust_air_temperature",
    "fan_setpoint",
    "air_path",
)


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
    enabled_default: bool = True


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
        "run_state",
        "Betriebsstatus",
        SensorDeviceClass.ENUM,
        options=("stopped", "running", "starting", "unknown"),
        translation_key="run_state",
    ),
    NovusSensorDescription(
        "message",
        "Meldung",
    ),
    NovusSensorDescription(
        "message_time",
        "Meldung Zeitpunkt",
        SensorDeviceClass.TIMESTAMP,
    ),
    NovusSensorDescription(
        "air_path",
        "Luftweg",
        SensorDeviceClass.ENUM,
        options=("heat_recovery", "bypass", "transition", "unknown"),
        translation_key="air_path",
    ),
    NovusSensorDescription(
        "register_44",
        "Register 0x44 (Rohwert, unbekannt)",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
    ),
    NovusSensorDescription(
        "register_62",
        "Register 0x62 (Rohwert, unbekannt)",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_default=False,
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
        self._attr_entity_registry_enabled_default = description.enabled_default
        self._attr_options = description.options
        self._attr_translation_key = description.translation_key
        self._restored_value: float | None = None
        self.entity_id = f"sensor.novus300_{description.key}"
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300 (FOCUS250)",
            "sw_version": "BUS 1.7.1",
        }

    async def async_added_to_hass(self) -> None:
        """Restore duration readings until their next bus update."""
        await super().async_added_to_hass()
        if self._description.key not in (
            "operating_time",
            "fan_operating_time",
            "filter_time_remaining",
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
            and self._description.key == "filter_time_remaining"
        ):
            restored_value /= 86400

        self._restored_value = round(restored_value, 2)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return whether this register has been observed."""
        if self._description.key == "message_time":
            return self.coordinator.message_time() is not None
        if self.coordinator.is_stopped and self._description.key in LIVE_KEYS:
            return False
        return (
            self._description.key in self.coordinator.data
            or self._restored_value is not None
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the decoded register value."""
        if self._description.key == "message_time":
            return self.coordinator.message_time()
        value = self.coordinator.data.get(self._description.key)
        if value is None:
            return self._restored_value
        if self._description.key == "message":
            return MESSAGE_TEXTS.get(value, f"Meldung {value.removeprefix('code_')}")
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
            self._description.key == "filter_time_remaining"
            and isinstance(value, float | int)
        ):
            return round(value / 86400, 2)
        return value if isinstance(value, float | int | str) else None

    @property
    def icon(self) -> str | None:
        """Return an icon matching the current operating state."""
        if self._description.key == "fan_setpoint":
            return "mdi:fan"
        if self._description.key == "message":
            return (
                "mdi:message-check-outline"
                if self.native_value == "Keine Meldung"
                else "mdi:message-alert-outline"
            )
        if self._description.key == "message_time":
            return "mdi:message-text-clock-outline"
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
        }
        return state_icons.get(self._description.key, {}).get(self.native_value)

    @property
    def extra_state_attributes(self) -> dict[str, float | int | str]:
        """Expose source registers and mapped fixed levels as attributes."""
        if self._description.key == "fan_setpoint":
            bus_value = self.coordinator.data.get("fan_setpoint")
            panel_mode = self.coordinator.data.get("ventilation_mode")
            if isinstance(bus_value, float | int) and isinstance(panel_mode, str):
                attributes: dict[str, float | int | str] = {
                    "bus_value": bus_value,
                    "panel_mode": panel_mode,
                }
                if panel_mode == "away":
                    attributes["away_minutes_per_hour"] = (
                        self.coordinator.setting_value(CONF_AWAY_DURATION_MINUTES)
                    )
                return attributes
        if self._description.key == "message":
            attributes = {"code": self.coordinator.data.get("message_code")}
            time = self.coordinator.message_time()
            if time is not None:
                attributes["occurred_at"] = time.isoformat(timespec="seconds")
            names = ("previous_message", "previous_message_2", "previous_message_3")
            for name, entry in zip(names, self.coordinator.message_log(), strict=False):
                attributes[name] = describe_message(entry)
            attributes["observed"] = self.coordinator.message_history()
            return attributes
        raw_key = {
            "run_state": "run_state_raw",
            "air_path": "status_word",
        }.get(self._description.key)
        if raw_key is None:
            return {}
        raw_value = self.coordinator.data.get(raw_key)
        return {"raw_value": raw_value} if isinstance(raw_value, int) else {}
