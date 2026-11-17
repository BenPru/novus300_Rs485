"""Paul Novus 300 RS-485 Bus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import NovusCoordinator

PLATFORMS = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.BUTTON,
    Platform.SELECT,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the manual clock synchronization and filter reset services."""

    async def _sync_clock(call: ServiceCall) -> None:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("No loaded Novus 300 entry")
        for entry in entries:
            await entry.runtime_data.async_sync_clock()

    async def _reset_filter(call: ServiceCall) -> None:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("No loaded Novus 300 entry")
        for entry in entries:
            await entry.runtime_data.async_reset_filter()

    hass.services.async_register(DOMAIN, "sync_clock", _sync_clock)
    hass.services.async_register(DOMAIN, "reset_filter", _reset_filter)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Novus integration from a config entry."""
    config = {**entry.data, **entry.options}
    coordinator = NovusCoordinator(hass, config, entry.entry_id)
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Novus integration."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
