"""Optional 0-10 V fan control through Tinkerforge."""

from __future__ import annotations

import logging
import threading
from time import monotonic
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from tinkerforge.bricklet_industrial_analog_out_v2 import (
    BrickletIndustrialAnalogOutV2,
)
from tinkerforge.ip_connection import Error, IPConnection

from .const import (
    CONF_AWAY_DURATION_MINUTES,
    CONF_FAN_AUTOMATIC_ENTITY,
    CONF_FAN_ENABLED,
    CONF_FAN_LEVEL_1_PERCENTAGE,
    CONF_FAN_LEVEL_3_PERCENTAGE,
    CONF_TINKERFORGE_HOST,
    CONF_TINKERFORGE_PORT,
    CONF_TINKERFORGE_UID,
    DEFAULT_FAN_AUTOMATIC_ENTITY,
)
from .coordinator import NovusCoordinator

LOGGER = logging.getLogger(__name__)

MIN_LEVEL_PERCENTAGE = 17
LEVEL_KEYS = {
    "level_1": CONF_FAN_LEVEL_1_PERCENTAGE,
    "level_3": CONF_FAN_LEVEL_3_PERCENTAGE,
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the optional Tinkerforge fan."""
    config = {**entry.data, **entry.options}
    if config.get(CONF_FAN_ENABLED, False):
        async_add_entities([NovusFanEntity(entry.runtime_data, config)])
    else:
        async_add_entities([NovusBusFanEntity(entry.runtime_data)])


class NovusBusFanEntity(CoordinatorEntity[NovusCoordinator], FanEntity):
    """Fan control through the bus levels, without 0-10 V hardware.

    A target below level 2 temporarily sets level 1 to the target, above level 2
    it sets level 3. The original percentage is restored when the level is left.
    """

    _attr_name = "Lüftung"
    _attr_unique_id = "novus300bus_fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 100

    def __init__(self, coordinator: NovusCoordinator) -> None:
        """Initialize the bus fan."""
        super().__init__(coordinator)
        self.entity_id = "fan.novus300"
        self._busy = False
        self._retry_at = 0.0
        self._attr_device_info = {
            "identifiers": {("novus300bus", "novus300")},
            "name": "Paul Novus 300",
            "manufacturer": "Paul",
            "model": "Novus 300 (FOCUS250)",
            "sw_version": "BUS 1.7.1",
        }

    @property
    def percentage(self) -> int | None:
        """Return the percentage of the active level."""
        mode = self.coordinator.data.get("ventilation_mode")
        if self.coordinator.is_stopped or mode in ("standby", "away"):
            return 0
        return self.coordinator.fan_level_percentage(mode)

    @property
    def is_on(self) -> bool | None:
        """Return whether the unit is ventilating."""
        mode = self.coordinator.data.get("ventilation_mode")
        if mode is None:
            return None
        return mode not in ("standby", "away") and not self.coordinator.is_stopped

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the active mode and temporarily changed levels."""
        data = self.coordinator.data
        attributes: dict[str, Any] = {
            "ventilation_mode": data.get("ventilation_mode"),
            "original_levels": self.coordinator.temporary_settings(),
        }
        if isinstance(setpoint := data.get("fan_setpoint"), float | int):
            attributes["bus_setpoint"] = setpoint
        if data.get("ventilation_mode") == "away":
            attributes["away_minutes_per_hour"] = self.coordinator.setting_value(
                CONF_AWAY_DURATION_MINUTES
            )
        return attributes

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Start ventilating at the given percentage or at level 2."""
        await self.async_set_percentage(
            percentage
            if percentage is not None
            else self.coordinator.fan_level_percentage("level_2")
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch to away mode (0 %)."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Select level 1 or 3 and set its percentage to the target."""
        coordinator = self.coordinator
        target = max(0, min(100, round(percentage)))
        level_2 = coordinator.fan_level_percentage("level_2") or 0
        self._busy = True
        try:
            keep = None
            if target == 0:
                mode = "away"
            elif target == level_2:
                mode = "level_2"
            elif target < level_2:
                mode, keep = "level_1", CONF_FAN_LEVEL_1_PERCENTAGE
                target = max(MIN_LEVEL_PERCENTAGE, min(target, level_2 - 1))
            else:
                mode, keep = "level_3", CONF_FAN_LEVEL_3_PERCENTAGE
                target = min(100, max(target, level_2 + 1))
            if keep is not None and coordinator.setting_value(keep) != target:
                await coordinator.async_set_temporary_setting(keep, target)
            await coordinator.async_set_ventilation_mode(mode)
            await coordinator.async_restore_settings(keep=keep)
        finally:
            self._busy = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Restore original levels once their level is no longer active."""
        super()._handle_coordinator_update()
        mode = self.coordinator.data.get("ventilation_mode")
        if self._busy or mode is None or monotonic() < self._retry_at:
            return
        keep = LEVEL_KEYS.get(mode)
        if any(key != keep for key in self.coordinator.temporary_settings()):
            self._busy = True
            self.hass.async_create_task(self._async_restore(keep))

    async def _async_restore(self, keep: str | None) -> None:
        try:
            await self.coordinator.async_restore_settings(keep=keep)
        except HomeAssistantError as err:
            LOGGER.warning("Unable to restore Novus fan levels: %s", err)
            self._retry_at = monotonic() + 60
        finally:
            self._busy = False


class NovusFanEntity(NovusBusFanEntity):
    """Control the Novus 0-10 V fan input via Tinkerforge (automatic mode)."""

    def __init__(self, coordinator: NovusCoordinator, config: dict[str, Any]) -> None:
        """Initialize the fan controller."""
        super().__init__(coordinator)
        self._host = config[CONF_TINKERFORGE_HOST]
        self._port = config[CONF_TINKERFORGE_PORT]
        self._uid = config[CONF_TINKERFORGE_UID]
        self._default_percentage = coordinator.fan_level_percentage("level_2") or 0
        self._automatic_entity = config.get(
            CONF_FAN_AUTOMATIC_ENTITY, DEFAULT_FAN_AUTOMATIC_ENTITY
        )
        self._has_automatic_entity = False
        self._percentage: int | None = None
        self._available = False
        self._ipcon: IPConnection | None = None
        self._analog_out: BrickletIndustrialAnalogOutV2 | None = None
        self._lock = threading.Lock()

    @property
    def _analog_active(self) -> bool:
        return self.coordinator.data.get("ventilation_mode") == "automatic"

    @property
    def percentage(self) -> int | None:
        """Return the 0-10 V value in automatic mode, else the active level."""
        if self.coordinator.is_stopped:
            return 0
        if self._analog_active:
            return self._percentage
        return super().percentage

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return the controls; presets only while the unit is in automatic."""
        features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        if self._analog_active and self._has_automatic_entity:
            features |= FanEntityFeature.PRESET_MODE
        return features

    @property
    def preset_modes(self) -> tuple[str, ...] | None:
        """Return automation presets while panel control is available."""
        if (
            self.coordinator.data.get("ventilation_mode") != "automatic"
            or not self._has_automatic_entity
        ):
            return None
        return ("Automatik", "Manuell")

    @property
    def is_on(self) -> bool | None:
        """Return whether a non-zero voltage is output."""
        if not self._analog_active:
            return super().is_on
        return (
            self._percentage is not None
            and self._percentage > 0
            and not self.coordinator.is_stopped
        )

    @property
    def state(self) -> str:
        """Return the legacy numeric state used by existing automations."""
        return str(self.percentage) if self.is_on else STATE_OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the unit's run state next to the analog output."""
        return {
            **super().extra_state_attributes,
            "run_state": self.coordinator.data.get("run_state"),
            "analog_percentage": self._percentage,
        }

    @property
    def preset_mode(self) -> str | None:
        """Return whether existing automations control the ventilation."""
        if self.preset_modes is None:
            return None
        return (
            "Automatik"
            if self.hass.states.is_state(self._automatic_entity, STATE_ON)
            else "Manuell"
        )

    @property
    def available(self) -> bool:
        """Stay available; the level control works without Tinkerforge."""
        return True

    async def async_added_to_hass(self) -> None:
        """Read the existing analog output without changing it."""
        self._has_automatic_entity = (
            self.hass.states.get(self._automatic_entity) is not None
        )
        if self._has_automatic_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._automatic_entity],
                    self._handle_automation_mode_change,
                )
            )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                ["select.novus300_ventilation_mode"],
                self._handle_panel_mode_change,
            )
        )
        await self.async_update()

    async def async_will_remove_from_hass(self) -> None:
        """Close the Tinkerforge connection."""
        await self.hass.async_add_executor_job(self._disconnect)

    async def async_update(self) -> None:
        """Refresh the current analog output voltage."""
        try:
            self._percentage = await self.hass.async_add_executor_job(
                self._read_percentage
            )
        except (Error, OSError) as err:
            LOGGER.warning("Unable to read Novus fan control: %s", err)
            self._available = False
        else:
            self._available = True

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Enable the output at the requested or configured default percentage."""
        await self.async_set_percentage(
            self._default_percentage if percentage is None else percentage
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch to away mode (0 %)."""
        await self.async_set_percentage(0)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Switch between the existing automatic and manual control modes."""
        self._ensure_panel_automatic()
        if not self._has_automatic_entity:
            raise HomeAssistantError(
                f"Automatic mode entity {self._automatic_entity} is unavailable"
            )
        if preset_mode not in (self.preset_modes or ()):
            raise HomeAssistantError(f"Unsupported fan preset: {preset_mode}")
        await self.hass.services.async_call(
            "input_boolean",
            "turn_on" if preset_mode == "Automatik" else "turn_off",
            {"entity_id": self._automatic_entity},
            blocking=True,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Select automatic mode and write the percentage as 0-10 V."""
        target = max(0, min(100, round(percentage)))
        if target == 0:
            await super().async_set_percentage(0)
            return
        target = max(MIN_LEVEL_PERCENTAGE, target)
        if not self._analog_active:
            await self.coordinator.async_set_ventilation_mode("automatic")
        try:
            await self.hass.async_add_executor_job(self._set_percentage, target)
        except (Error, OSError) as err:
            self._available = False
            raise HomeAssistantError(
                f"Unable to set Novus fan control: {err}"
            ) from err
        self._percentage = target
        self._available = True
        self.async_write_ha_state()

    def _connect(self) -> BrickletIndustrialAnalogOutV2:
        """Connect to the configured Tinkerforge analog output."""
        if self._analog_out is None:
            self._ipcon = IPConnection()
            self._analog_out = BrickletIndustrialAnalogOutV2(self._uid, self._ipcon)
            self._ipcon.connect(self._host, self._port)
        return self._analog_out

    def _read_percentage(self) -> int:
        """Read the current analog output voltage as a percentage."""
        with self._lock:
            return round(self._connect().get_voltage() / 100)

    def _ensure_panel_automatic(self) -> None:
        """Allow analog control only while the panel selects automatic mode."""
        if self.coordinator.data.get("ventilation_mode") != "automatic":
            raise HomeAssistantError(
                "Novus fan control is available only in panel automatic mode"
            )

    def _set_percentage(self, percentage: int) -> None:
        """Set the analog output voltage."""
        with self._lock:
            analog_out = self._connect()
            analog_out.set_voltage(percentage * 100)
            analog_out.set_enabled(True)

    def _disconnect(self) -> None:
        """Disconnect the Tinkerforge client."""
        with self._lock:
            if self._ipcon is not None:
                self._ipcon.disconnect()
                self._ipcon = None
                self._analog_out = None

    @callback
    def _handle_panel_mode_change(self, event) -> None:
        """Refresh the analog value and controls after the panel mode changes."""
        self.hass.async_create_task(self._async_refresh_state())

    async def _async_refresh_state(self) -> None:
        await self.async_update()
        self.async_write_ha_state()

    @callback
    def _handle_automation_mode_change(self, event) -> None:
        """Refresh the displayed preset after an automation mode change."""
        self.async_write_ha_state()
