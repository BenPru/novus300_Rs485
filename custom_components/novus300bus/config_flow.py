"""Config flow for the Paul Novus 300 bus integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BAUDRATE,
    CONF_FAN_DEFAULT_PERCENTAGE,
    CONF_FAN_ENABLED,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    CONF_TINKERFORGE_HOST,
    CONF_TINKERFORGE_PORT,
    CONF_TINKERFORGE_UID,
    DEFAULT_BAUDRATE,
    DEFAULT_FAN_DEFAULT_PERCENTAGE,
    DEFAULT_FAN_ENABLED,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
    DEFAULT_TINKERFORGE_HOST,
    DEFAULT_TINKERFORGE_PORT,
    DEFAULT_TINKERFORGE_UID,
    DOMAIN,
    PARITY_OPTIONS,
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

    def _value(self, key: str, default: str | int | bool) -> str | int | bool:
        """Return an option, falling back to the original config entry data."""
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Configure serial transport and optional 0-10 V fan control."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SERIAL_PORT,
                    default=self._value(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT),
                ): str,
                vol.Required(
                    CONF_BAUDRATE,
                    default=self._value(CONF_BAUDRATE, DEFAULT_BAUDRATE),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    CONF_PARITY,
                    default=self._value(CONF_PARITY, DEFAULT_PARITY),
                ): vol.In(PARITY_OPTIONS),
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
                    CONF_FAN_DEFAULT_PERCENTAGE,
                    default=self._value(
                        CONF_FAN_DEFAULT_PERCENTAGE, DEFAULT_FAN_DEFAULT_PERCENTAGE
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
