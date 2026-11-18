"""Buttons for the Paul Novus 300 bus integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BOOST_DURATION_MINUTES
from .coordinator import NovusCoordinator


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Novus buttons."""
    config = {**entry.data, **entry.options}
    async_add_entities(
        [
            NovusBoostButton(hass, entry.runtime_data, config),
            NovusFilterResetButton(entry.runtime_data),
        ]
    )


class NovusBoostButton(CoordinatorEntity[NovusCoordinator], ButtonEntity):
    """Trigger the boost ventilation mode on the bus."""

    _attr_has_entity_name = True
    _attr_translation_key = "boost"
    _attr_unique_id = "novus300bus_boost"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: NovusCoordinator,
        config: dict[str, Any],
    ) -> None:
        """Initialize the boost button."""
        super().__init__(coordinator)
        self.hass = hass
        self.entity_id = "button.novus300_boost"
        self._coordinator = coordinator
        self._restore_mode: str | None = None
        self._cancel_restore: CALLBACK_TYPE | None = None
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
        return super().available and not self._coordinator.is_stopped

    @property
    def icon(self) -> str:
        """Return a different icon while boost ventilation is active."""
        if self._coordinator.data.get("ventilation_mode") == "boost":
            return "mdi:fan-alert"
        return "mdi:weather-windy"

    async def async_press(self) -> None:
        """Start boost ventilation and return to the previous mode afterwards."""
        if self._cancel_restore is None:
            mode = self._coordinator.data.get("ventilation_mode")
            self._restore_mode = mode if mode not in (None, "boost", "standby") else None
        else:
            self._cancel_restore()
        await self._coordinator.async_set_ventilation_mode("boost")
        self._cancel_restore = async_call_later(
            self.hass,
            timedelta(
                minutes=self._coordinator.setting_value(CONF_BOOST_DURATION_MINUTES)
            ).total_seconds(),
            self._async_schedule_restore,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel an outstanding restore when unloading the integration."""
        if self._cancel_restore is not None:
            self._cancel_restore()
            self._cancel_restore = None

    @callback
    def _async_schedule_restore(self, now: datetime) -> None:
        """Schedule the mode restoration outside the timer callback."""
        self._cancel_restore = None
        self.hass.async_create_task(self._async_restore())

    async def _async_restore(self) -> None:
        """Restore the earlier mode unless the mode was changed meanwhile."""
        restore_mode, self._restore_mode = self._restore_mode, None
        if restore_mode and self._coordinator.data.get("ventilation_mode") == "boost":
            await self._coordinator.async_set_ventilation_mode(restore_mode)


class NovusFilterResetButton(ButtonEntity):
    """Restart the filter run time in the unit."""

    _attr_has_entity_name = True
    _attr_translation_key = "filter_reset"
    _attr_unique_id = "novus300bus_filter_reset"
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the filter reset button."""
        self.entity_id = "button.novus300_filter_reset"
        self._coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300 (FOCUS250)",
            "sw_version": "BUS 1.7.1",
        }

    @property
    def available(self) -> bool:
        """Return False while the unit is off."""
        return not self._coordinator.is_stopped

    async def async_press(self) -> None:
        """Reset the filter run time."""
        await self._coordinator.async_reset_filter()
