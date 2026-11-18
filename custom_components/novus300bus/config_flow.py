"""Config flow for the Paul Novus 300 bus integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import (
    CONF_AWAY_DURATION_MINUTES,
    CONF_BAUDRATE,
    CONF_DAILY_TIME_SYNC,
    CONF_BOOST_DURATION_MINUTES,
    CONF_FILTER_INTERVAL_DAYS,
    CONF_SHOW_FAN_LEVELS,
    DEFAULT_SHOW_FAN_LEVELS,
    CONF_FAN_AUTOMATIC_ENTITY,
    CONF_FAN_ENABLED,
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_TINKERFORGE_HOST,
    CONF_TINKERFORGE_PORT,
    CONF_TINKERFORGE_UID,
    DEFAULT_AWAY_DURATION_MINUTES,
    DEFAULT_FILTER_INTERVAL_DAYS,
    DEFAULT_BAUDRATE,
    DEFAULT_DAILY_TIME_SYNC,
    DEFAULT_BOOST_DURATION_MINUTES,
    DEFAULT_FAN_AUTOMATIC_ENTITY,
    DEFAULT_FAN_ENABLED,
    DEFAULT_FAN_LEVEL_1_PERCENTAGE,
    DEFAULT_FAN_LEVEL_2_PERCENTAGE,
    DEFAULT_FAN_LEVEL_3_PERCENTAGE,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
    DEFAULT_TINKERFORGE_HOST,
    DEFAULT_TINKERFORGE_PORT,
    DEFAULT_TINKERFORGE_UID,
    DOMAIN,
    PARITY_OPTIONS,
)

LOGGER = logging.getLogger(__name__)

BUS_SETTING_KEYS = (
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
    CONF_BOOST_DURATION_MINUTES,
    CONF_AWAY_DURATION_MINUTES,
)
INT_KEYS = (*BUS_SETTING_KEYS, CONF_FILTER_INTERVAL_DAYS)

SETTING_GRIDS = {
    CONF_BOOST_DURATION_MINUTES: range(5, 121, 5),
    CONF_AWAY_DURATION_MINUTES: range(15, 46, 15),
    CONF_FILTER_INTERVAL_DAYS: range(30, 181, 10),
}
PERCENTAGE_KEYS = (
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_2_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
)


def _label(key: str, value: int) -> str:
    if key == CONF_AWAY_DURATION_MINUTES:
        return f"{value} min/h"
    if key == CONF_FILTER_INTERVAL_DAYS:
        return f"{value} d"
    return f"{value} min"


def _setting_selector(key: str, current: int) -> selector.SelectSelector:
    """Return a dropdown for a unit setting, keeping an off-grid current value."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": str(value), "label": _label(key, value)}
                for value in sorted({*SETTING_GRIDS[key], current})
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _percentage_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=17,
            max=100,
            step=1,
            unit_of_measurement="%",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


class NovusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Novus bus configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str | int] | None = None
    ) -> FlowResult:
        """Configure the local serial device."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Paul Novus 300 ({user_input[CONF_SERIAL_PORT]})",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT, default=DEFAULT_SERIAL_PORT): str,
                vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                vol.Required(CONF_PARITY, default=DEFAULT_PARITY): vol.In(
                    PARITY_OPTIONS
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NovusOptionsFlow:
        """Return the options flow."""
        return NovusOptionsFlow(config_entry)


class NovusOptionsFlow(config_entries.OptionsFlow):
    """Handle Novus integration options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    def _source_text(self, missing: list[str]) -> str:
        """Describe whether the shown settings were read from the unit."""
        german = self.hass.config.language.startswith("de")
        if not missing:
            return (
                "Stufen und Zeiten wurden aus der Anlage gelesen."
                if german
                else "Fan levels and durations were read from the unit."
            )
        names = ", ".join(missing)
        return (
            f"Noch nicht aus der Anlage gelesen (Bedienteil-Menü einmal öffnen): {names}. Hier gelten Ersatzwerte."
            if german
            else f"Not yet read from the unit (open the panel menu once): {names}. Fallback values are shown."
        )

    def _value(self, key: str, default: str | int | bool) -> str | int | bool:
        """Return a bus setting as known by the unit, else the stored option."""
        if key == CONF_FILTER_INTERVAL_DAYS:
            coordinator = getattr(self._config_entry, "runtime_data", None)
            if coordinator is not None:
                return coordinator.filter_interval_days()
        if key in BUS_SETTING_KEYS:
            coordinator = getattr(self._config_entry, "runtime_data", None)
            if coordinator is not None:
                return coordinator.setting_value(key)
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Configure the bus, the unit's settings and optional 0-10 V control."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {
                key: int(value) if key in INT_KEYS else value
                for key, value in user_input.items()
            }
            levels = [user_input[k] for k in PERCENTAGE_KEYS]
            if not 17 <= levels[0] < levels[1] < levels[2] <= 100:
                errors["base"] = "levels_order"
            coordinator = getattr(self._config_entry, "runtime_data", None)
            if coordinator is not None and not errors:
                try:
                    await coordinator.async_write_settings(
                        {key: user_input[key] for key in BUS_SETTING_KEYS}
                    )
                    coordinator.clear_temporary_settings()
                    interval = user_input[CONF_FILTER_INTERVAL_DAYS]
                    if interval != coordinator.filter_interval_days():
                        await coordinator.async_set_filter_interval(interval)
                except HomeAssistantError as err:
                    LOGGER.warning("Unable to write settings to the Novus: %s", err)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        fields: dict = {
            vol.Required(
                CONF_SERIAL_PORT,
                default=self._value(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT),
            ): str,
            vol.Required(
                CONF_BAUDRATE, default=self._value(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(
                CONF_PARITY, default=self._value(CONF_PARITY, DEFAULT_PARITY)
            ): vol.In(PARITY_OPTIONS),
            vol.Required(
                CONF_DAILY_TIME_SYNC,
                default=self._value(CONF_DAILY_TIME_SYNC, DEFAULT_DAILY_TIME_SYNC),
            ): bool,
        }
        fields[
            vol.Required(
                CONF_SHOW_FAN_LEVELS,
                default=self._value(CONF_SHOW_FAN_LEVELS, DEFAULT_SHOW_FAN_LEVELS),
            )
        ] = bool
        for key, default in (
            (CONF_FAN_LEVEL_1_PERCENTAGE, DEFAULT_FAN_LEVEL_1_PERCENTAGE),
            (CONF_FAN_LEVEL_2_PERCENTAGE, DEFAULT_FAN_LEVEL_2_PERCENTAGE),
            (CONF_FAN_LEVEL_3_PERCENTAGE, DEFAULT_FAN_LEVEL_3_PERCENTAGE),
            (CONF_BOOST_DURATION_MINUTES, DEFAULT_BOOST_DURATION_MINUTES),
            (CONF_AWAY_DURATION_MINUTES, DEFAULT_AWAY_DURATION_MINUTES),
            (CONF_FILTER_INTERVAL_DAYS, DEFAULT_FILTER_INTERVAL_DAYS),
        ):
            current = int(self._value(key, default))
            if key in PERCENTAGE_KEYS:
                fields[vol.Required(key, default=current)] = _percentage_selector()
            else:
                fields[vol.Required(key, default=str(current))] = _setting_selector(
                    key, current
                )
        fields.update(
            {
                vol.Required(
                    CONF_FAN_ENABLED,
                    default=self._value(CONF_FAN_ENABLED, DEFAULT_FAN_ENABLED),
                ): bool,
                vol.Required(
                    CONF_TINKERFORGE_HOST,
                    default=self._value(
                        CONF_TINKERFORGE_HOST, DEFAULT_TINKERFORGE_HOST
                    ),
                ): str,
                vol.Required(
                    CONF_TINKERFORGE_PORT,
                    default=self._value(
                        CONF_TINKERFORGE_PORT, DEFAULT_TINKERFORGE_PORT
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_TINKERFORGE_UID,
                    default=self._value(CONF_TINKERFORGE_UID, DEFAULT_TINKERFORGE_UID),
                ): str,
                vol.Required(
                    CONF_FAN_AUTOMATIC_ENTITY,
                    default=self._value(
                        CONF_FAN_AUTOMATIC_ENTITY, DEFAULT_FAN_AUTOMATIC_ENTITY
                    ),
                ): str,
            }
        )
        coordinator = getattr(self._config_entry, "runtime_data", None)
        missing = coordinator.settings_not_read() if coordinator else []
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "source": self._source_text(missing)
            },
        )
