"""Config flow for the Paul Novus 300 bus integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_SERIAL_PORT,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_PORT,
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
