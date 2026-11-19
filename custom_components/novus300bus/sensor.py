"""Sensors for the Paul Novus 300 bus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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


STATUS_EVENT_TEXTS = {
    "run_state": {
        "stopped": "Anlage ausgeschaltet",
        "running": "Anlage läuft",
        "starting": "Anlage fährt hoch",
        "unknown": "Anlagenstatus unbekannt",
    },
    "air_path": {
        "heat_recovery": "Wärmerückgewinnung aktiv",
        "bypass": "Bypass offen",
        "transition": "Bypass in Bewegung",
        "unknown": "Luftweg unbekannt",
    },
}


def describe_status_event(event: dict[str, str], transient: bool = False) -> str:
    """Return a readable text for a run state or air path change."""
    if transient and event["kind"] == "run_state" and event["state"] == "stopped":
        return "Anlage fährt runter"
    text = STATUS_EVENT_TEXTS[event["kind"]].get(event["state"], event["state"])
    if event["state"] == "unknown" and event.get("raw"):
        text = f"{text} (Wert {event['raw']})"
    return text


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


TEMPERATURE_ICONS = {
    "outdoor_air_temperature": "mdi:sun-thermometer-outline",
    "supply_air_temperature": "mdi:thermometer-chevron-up",
    "exhaust_air_temperature": "mdi:thermometer-chevron-down",
    "extract_air_temperature": "mdi:home-thermometer-outline",
}

SENSORS = (
    NovusSensorDescription(
        "supply_air_temperature",
        "2 Zuluft Temperatur Räume",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "outdoor_air_temperature",
        "1 Außenluft Temperatur",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "extract_air_temperature",
        "3 Abluft Temperatur Räume",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "exhaust_air_temperature",
        "4 Fortluft Temperatur",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    NovusSensorDescription(
        "message",
        "Aktuelle Meldung",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        self._attr_unique_id = f"novus300bus_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = description.enabled_default
        self._attr_options = description.options
        self._attr_translation_key = description.key
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
        if self.coordinator.is_stopped and self._description.key in LIVE_KEYS:
            return False
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
        if self._description.key == "message":
            transient = self.coordinator.transient_event()
            if transient is not None:
                return describe_status_event(transient, True)
            return MESSAGE_TEXTS.get(value, f"Meldung {value.removeprefix('code_')}")
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
        if self._description.key in TEMPERATURE_ICONS:
            return TEMPERATURE_ICONS[self._description.key]
        if self._description.key == "message":
            if self.coordinator.transient_event() is not None:
                return "mdi:message-processing-outline"
            return (
                "mdi:message-check-outline"
                if self.native_value == "Keine Meldung"
                else "mdi:message-alert-outline"
            )
        if self._description.key == "filter_time_remaining":
            remaining = self.coordinator.data.get("filter_time_remaining")
            return (
                "mdi:air-filter"
                if not isinstance(remaining, float | int) or remaining > 0
                else "mdi:alert-circle-outline"
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, float | int | str]:
        """Expose the message details and observed status changes."""
        if self._description.key == "message":
            attributes = {"code": self.coordinator.data.get("message_code")}
            time = self.coordinator.message_time()
            transient = self.coordinator.transient_event()
            if transient:
                time = datetime.fromisoformat(transient["time"])
            if time is not None:
                attributes["occurred_at"] = time.isoformat(timespec="seconds")
            names = ("previous_message", "previous_message_2", "previous_message_3")
            for name, entry in zip(names, self.coordinator.message_log(), strict=False):
                attributes[name] = describe_message(entry)
            attributes["observed"] = self.coordinator.message_history()
            attributes["status_events"] = [
                f"{datetime.fromisoformat(event['time']):%d.%m.%Y %H:%M:%S} · "
                f"{describe_status_event(event)}"
                for event in self.coordinator.status_events()
            ]
            return attributes
        return {}
