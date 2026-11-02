"""Buttons for the Paul Novus 300 bus integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.const import STATE_ON
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_BOOST_DURATION_MINUTES,
    CONF_BOOST_PERCENTAGE,
    CONF_FAN_AUTOMATIC_ENTITY,
    CONF_FAN_ENABLED,
    DEFAULT_BOOST_DURATION_MINUTES,
    DEFAULT_BOOST_PERCENTAGE,
    DEFAULT_FAN_AUTOMATIC_ENTITY,
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Novus buttons."""
    config = {**entry.data, **entry.options}
    if not config.get(CONF_FAN_ENABLED, False):
        return
    async_add_entities([NovusBoostButton(hass, config)])


class NovusBoostButton(ButtonEntity):
    """Temporarily increase the ventilation fan output."""

    _attr_name = "Stoßlüftung"
    _attr_unique_id = "novus300bus_boost"
    _attr_icon = "mdi:weather-windy"

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the boost button."""
        self.hass = hass
        self.entity_id = "button.novus300_boost"
        self._boost_percentage = config.get(
            CONF_BOOST_PERCENTAGE, DEFAULT_BOOST_PERCENTAGE
        )
        self._duration = timedelta(
            minutes=config.get(
                CONF_BOOST_DURATION_MINUTES, DEFAULT_BOOST_DURATION_MINUTES
            )
        )
        self._automatic_entity = config.get(
            CONF_FAN_AUTOMATIC_ENTITY, DEFAULT_FAN_AUTOMATIC_ENTITY
        )
        self._restore_percentage: int | None = None
        self._restore_automatic: bool | None = None
        self._cancel_restore: CALLBACK_TYPE | None = None
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300",
        }

    async def async_press(self) -> None:
        """Start or extend the configured ventilation boost."""
        fan_state = self.hass.states.get("fan.novus300")
        if fan_state is None:
            raise HomeAssistantError("Novus fan entity is unavailable")

        if self._cancel_restore is None:
            self._restore_percentage = self._fan_percentage(fan_state)
            self._restore_automatic = self.hass.states.is_state(
                self._automatic_entity, STATE_ON
            )
        else:
            self._cancel_restore()

        if self._restore_automatic:
            await self.hass.services.async_call(
                "input_boolean",
                "turn_off",
                {"entity_id": self._automatic_entity},
                blocking=True,
            )
        await self.hass.services.async_call(
            "fan",
            "set_percentage",
            {"entity_id": "fan.novus300", "percentage": self._boost_percentage},
            blocking=True,
        )
        self._cancel_restore = async_call_later(
            self.hass, self._duration.total_seconds(), self._async_schedule_restore
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel an outstanding restore when unloading the integration."""
        if self._cancel_restore is not None:
            self._cancel_restore()
            self._cancel_restore = None

    @staticmethod
    def _fan_percentage(fan_state) -> int:
        """Return the current percentage from a compatible fan state."""
        percentage = fan_state.attributes.get("percentage", fan_state.state)
        try:
            return int(float(percentage))
        except (TypeError, ValueError) as err:
            raise HomeAssistantError("Novus fan percentage is unavailable") from err

    @callback
    def _async_schedule_restore(self, now: datetime) -> None:
        """Schedule state restoration outside the timer callback."""
        self._cancel_restore = None
        self.hass.async_create_task(self._async_restore())

    async def _async_restore(self) -> None:
        """Restore the fan percentage and automatic mode from before the boost."""
        if self._restore_percentage is None or self._restore_automatic is None:
            return
        await self.hass.services.async_call(
            "fan",
            "set_percentage",
            {
                "entity_id": "fan.novus300",
                "percentage": self._restore_percentage,
            },
            blocking=True,
        )
        await self.hass.services.async_call(
            "input_boolean",
            "turn_on" if self._restore_automatic else "turn_off",
            {"entity_id": self._automatic_entity},
            blocking=True,
        )
        self._restore_percentage = None
        self._restore_automatic = None
