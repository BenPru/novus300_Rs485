"""Paul Novus 300 RS-485 Bus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import NovusCoordinator

SUB_DEVICES = (
    ("serial_panel", "panel", "Bedienteil", "TFT"),
    ("serial_fan_slave", "fan_slave", "Lüfter-Slave", "Slave"),
    ("serial_defroster", "defroster", "Defroster", "Defroster"),
)


def _register_sub_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Create the connected components as sub-devices of the unit."""
    registry = dr.async_get(hass)
    values = entry.runtime_data.data
    main = registry.async_get_device(identifiers={(DOMAIN, "novus300")})
    if main is None:
        return
    for key, slug, name, model in SUB_DEVICES:
        serial = values.get(key)
        if isinstance(serial, str):
            registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, f"novus300_{slug}")},
                via_device_id=main.id,
                name=f"Novus 300 {name}",
                manufacturer="Paul",
                model=model,
                serial_number=serial,
            )

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
    _register_sub_devices(hass, entry)
    entry.async_on_unload(
        coordinator.async_add_listener(lambda: _register_sub_devices(hass, entry))
    )
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
