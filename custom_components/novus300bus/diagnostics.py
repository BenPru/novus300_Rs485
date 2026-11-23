"""Diagnostics for the Paul Novus 300 bus integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the configuration, all decoded values and the raw bus bytes."""
    coordinator = entry.runtime_data
    values = dict(coordinator.data)
    return {
        "hardware_profile": coordinator.hardware_profile,
        "read_only": coordinator.read_only,
        "protocol": coordinator.protocol_diagnostics(),
        "passive_recording": coordinator.passive_recording.snapshot(),
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "values": values,
        "parameter_block": {
            key: value for key, value in sorted(values.items()) if key.startswith("param_")
        },
        "message_history": coordinator.message_history(),
        "status_events": coordinator.status_events(),
        "raw_bus_log": {
            "description": "Last received serial chunks (UTC time, hex bytes)",
            "chunks": [{"time": t, "hex": h} for t, h in list(coordinator.raw_log)],
        },
    }
