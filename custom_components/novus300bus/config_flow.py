"""Config flow for the Paul Novus 300 bus integration."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .protocol import PARAMETER_LIMITS
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
    FAN_STAGE_KEYS,
    FAN_IMBALANCE_KEYS,
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
    *FAN_IMBALANCE_KEYS,
)
INT_KEYS = (
    *(key for key in BUS_SETTING_KEYS if key not in FAN_IMBALANCE_KEYS),
    CONF_FILTER_INTERVAL_DAYS,
)

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


# field -> (register, bit mask or None, {option: (value, de, en)})
PLANT_SELECTS = {
    "defroster": (0x1E, None, {"1": (1, "Elektro", "Electric"), "2": (2, "PTC", "PTC"), "3": (3, "Sole", "Brine")}),
    "reheater": (0x21, None, {"0": (0, "Keine", "None"), "1": (1, "Elektroheizregister", "Electric heater"), "3": (3, "Warmwasserheizregister", "Water heater")}),
    "ewt": (0x24, None, {"0": (0, "Nicht vorhanden", "Not present"), "4": (4, "Vorhanden", "Present")}),
    "automatic": (0x63, 0x08, {"time": (0, "Zeitautomatik", "Time automatic"), "sensor": (0x08, "Sensorautomatik", "Sensor automatic")}),
    "frost": (0x7B, None, {"0": (0, "Eco", "Eco"), "1": (1, "Sicher", "Safe"), "2": (2, "Feuchte WT", "Humidity HX")}),
}
RESOLVED_REGISTERS = {0x48, 0x56, 0x5C, 0x5F, 0x60, 0x61, 0x41, 0x42, 0x43, 0x47, 0x49, 0x4A, 0x4B, 0x4C, 0x5A, 0x63, 0x1B, 0x1E, 0x21, 0x24, 0x7B}
# checkbox -> (register, bit mask, set bit means unchecked)
PLANT_FLAGS = {"bypass": (0x1B, 0x04, True)}
SELECT_DEFAULT_BASE = {0x63: 0x1F0}

BYPASS_NUMBERS = (0x41, 0x42, 0x43, 0x49)
HYSTERESIS_REGISTERS = (0x43, 0x48, 0x5C, 0x61)
PLANT_NUMBERS = (0x4A, 0x4B, 0x4C, 0x47, 0x48, 0x5A, 0x5C, 0x56, 0x5F, 0x60, 0x61)
PLANT_FORM_GROUPS = {
    "ewt": ("ewt", 0x5F, 0x60, 0x61),
    "frost_protection": ("defroster", "frost", 0x4A, 0x4B, 0x4C, 0x47, 0x48, 0x56),
    "reheating": ("reheater", 0x5A, 0x5C),
}
DIALOG_REGISTERS = {
    "plant": ((0x47, 0x48, 0x4A, 0x4B, 0x4C, 0x5A, 0x5C, 0x56, 0x5F, 0x60, 0x61, 0x24, 0x7B), (0x1E, 0x21)),
    "bypass": ((0x41, 0x42, 0x43, 0x49, 0x1B), ()),
}
PANEL_PAGES = {
    0x1B: ("Setup > Bypass (installiert)", "Setup > By-pass (installed)"),
    0x1E: ("Setup > Frostschutz > Defroster-Typ", "Setup > Frost protection > Defroster type"),
    0x21: ("Setup > Nachheizung > Typ", "Setup > Reheating > Type"),
    0x24: ("Setup > Erdwärmetauscher-Klappe (vorhanden)", "Setup > Ground pipe diverter valve (available)"),
    0x7B: ("Einstellungen > Frostschutz (Eco/Safe/Feuchte-WT)", "Settings > Frost protection (Eco/Safe/Moisture HX)"),
}

# register -> (de, en, unit, divisor). "?" marks names that are not confirmed on the unit;
# the others follow the register list of github.com/larda3141/novus2mqtt and the manual.
PARAMETER_INFO: dict[int, tuple[str, str, str, int]] = {
    0x44: ("Statusbits (?)", "Status bits (?)", "", 1),
    0x45: ("Grenztemperatur (?)", "Limit temperature (?)", "°C", 10),
    0x46: ("Referenzwert (?)", "Reference value (?)", "", 10),
    0x48: ("Frostschutz Zuluft Hysterese", "Frost protection supply air hysteresis", "K", 10),
    0x4D: ("Sensorautomatik Spannung U_min (?)", "Sensor automatic voltage U_min", "V", 10),
    0x4E: ("Sensorautomatik Drehzahl n_min (Spannung)", "Sensor automatic speed n_min (voltage)", "%", 1),
    0x4F: ("Sensorautomatik Spannung U_max (?)", "Sensor automatic voltage U_max", "V", 10),
    0x50: ("Sensorautomatik Drehzahl n_max (Spannung)", "Sensor automatic speed n_max (voltage)", "%", 1),
    0x51: ("Sensorautomatik Strom I_min", "Sensor automatic current I_min", "mA", 10),
    0x52: ("Sensorautomatik Drehzahl n_min (Strom)", "Sensor automatic speed n_min (current)", "%", 1),
    0x53: ("Sensorautomatik Strom I_max", "Sensor automatic current I_max", "mA", 10),
    0x54: ("Sensorautomatik Drehzahl n_max (Strom)", "Sensor automatic speed n_max (current)", "%", 1),
    0x56: ("Sole-Defroster Kühlschwelle", "Brine defroster cooling threshold", "°C", 10),
    0x57: ("Sensorautomatik (?)", "Sensor automatic (?)", "", 1),
    0x58: ("Sensorautomatik (?)", "Sensor automatic (?)", "", 1),
    0x59: ("Sensorautomatik Plausibilität (?)", "Sensor automatic plausibility (?)", "", 1),
    0x5B: ("Lüfter Nenndrehzahl (Spiegel)", "Fan nominal speed (mirror)", "%", 1),
    0x5C: ("Nachheizung Hysterese", "Reheating hysteresis", "K", 10),
    0x5D: ("Nachheizung Kanal-Sollwert (?)", "Reheating duct setpoint (?)", "°C", 1),
    0x5E: ("EWT-Klappe vorhanden (Spiegel)", "EWT damper present (mirror)", "", 1),
    0x5F: ("EWT-Klappe untere Schwelle", "EWT damper lower threshold", "°C", 10),
    0x60: ("EWT-Klappe obere Schwelle", "EWT damper upper threshold", "°C", 10),
    0x61: ("EWT-Klappe Hysterese", "EWT damper hysteresis", "K", 10),
}


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


def _percentage_selector(minimum: int = 17) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
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

    async def async_step_reconfigure(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Offer the two interface settings as a menu."""
        return self.async_show_menu(
            step_id="reconfigure", menu_options=["bus", "fan_control"]
        )

    def _current(self, key: str, default: str | int | bool) -> str | int | bool:
        entry = self._get_reconfigure_entry()
        return entry.options.get(key, entry.data.get(key, default))

    def _store(self, user_input: dict[str, str | int | bool]) -> FlowResult:
        """Save interface settings; the update listener reloads the entry."""
        entry = self._get_reconfigure_entry()
        self.hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, **user_input},
            options={**entry.options, **user_input},
        )
        return self.async_abort(reason="reconfigure_successful")

    async def async_step_bus(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Configure how Home Assistant reaches the RS-485 bus."""
        if user_input is not None:
            return self._store(user_input)
        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERIAL_PORT,
                        default=self._current(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT),
                    ): str,
                    vol.Required(
                        CONF_BAUDRATE,
                        default=self._current(CONF_BAUDRATE, DEFAULT_BAUDRATE),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                    vol.Required(
                        CONF_PARITY, default=self._current(CONF_PARITY, DEFAULT_PARITY)
                    ): vol.In(PARITY_OPTIONS),
                }
            ),
        )

    async def async_step_fan_control(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Configure the optional 0-10 V fan control."""
        if user_input is not None:
            return self._store(user_input)
        return self.async_show_form(
            step_id="fan_control",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FAN_ENABLED,
                        default=self._current(CONF_FAN_ENABLED, DEFAULT_FAN_ENABLED),
                    ): bool,
                    vol.Required(
                        CONF_TINKERFORGE_HOST,
                        default=self._current(
                            CONF_TINKERFORGE_HOST, DEFAULT_TINKERFORGE_HOST
                        ),
                    ): str,
                    vol.Required(
                        CONF_TINKERFORGE_PORT,
                        default=self._current(
                            CONF_TINKERFORGE_PORT, DEFAULT_TINKERFORGE_PORT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Required(
                        CONF_TINKERFORGE_UID,
                        default=self._current(
                            CONF_TINKERFORGE_UID, DEFAULT_TINKERFORGE_UID
                        ),
                    ): str,
                    vol.Required(
                        CONF_FAN_AUTOMATIC_ENTITY,
                        default=self._current(
                            CONF_FAN_AUTOMATIC_ENTITY, DEFAULT_FAN_AUTOMATIC_ENTITY
                        ),
                    ): str,
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NovusOptionsFlow:
        """Return the options flow."""
        return NovusOptionsFlow(config_entry)


class NovusOptionsFlow(config_entries.OptionsFlow):
    _dialog = "plant"

    """Handle Novus integration options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    def _source_text(self, missing: list[str]) -> str:
        """Describe whether the shown settings were read from the unit."""
        german = self.hass.config.language.startswith("de")
        if not missing:
            return (
                "Stufen, Disbalance und Zeiten wurden aus der Anlage gelesen."
                if german
                else "Fan levels, imbalance and durations were read from the unit."
            )
        names = ", ".join(missing)
        return (
            f"Noch nicht aus der Anlage gelesen (Bedienteil-Menü einmal öffnen): {names}. Unbekannte Disbalance bleibt leer; andere Felder zeigen Ersatzwerte."
            if german
            else f"Not yet read from the unit (open the panel menu once): {names}. Unknown imbalance stays blank; other fields show fallback values."
        )

    def _value(self, key: str, default: str | int | bool) -> str | int | bool:
        """Return a bus setting as known by the unit, else the stored option."""
        if key == CONF_FILTER_INTERVAL_DAYS:
            coordinator = getattr(self._config_entry, "runtime_data", None)
            if coordinator is not None:
                return coordinator.filter_interval_days()
        if key in BUS_SETTING_KEYS or key in FAN_STAGE_KEYS:
            coordinator = getattr(self._config_entry, "runtime_data", None)
            if coordinator is not None:
                return coordinator.setting_value(key)
        return self._config_entry.options.get(
            key, self._config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Offer the settings groups as a menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["general", "plant", "bypass", "advanced"],
        )

    def _save(self, user_input: dict[str, str | int | bool]) -> FlowResult:
        """Store one dialog's values without dropping the other dialogs' options."""
        return self.async_create_entry(
            title="", data={**self._config_entry.options, **user_input}
        )

    @staticmethod
    def _flatten_sections(user_input, names):
        values = dict(user_input)
        for name in names:
            values.update(values.pop(name, {}))
        return values

    @staticmethod
    def _section_field(name, fields, required=False, collapsed=True):
        defaults = {
            marker.schema: marker.default()
            for marker in fields
            if marker.default is not vol.UNDEFINED
        }
        marker = vol.Required if required else vol.Optional
        return marker(name, default=defaults), section(
            vol.Schema(fields), {"collapsed": collapsed}
        )

    async def async_step_general(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure the bus and the unit's settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._flatten_sections(
                user_input, (f"fan_level_{level}" for level in range(1, 4))
            )
            for key in FAN_IMBALANCE_KEYS:
                if key in user_input and user_input[key] is not None and (
                    isinstance(user_input[key], bool)
                    or not isinstance(user_input[key], int | float)
                    or user_input[key] * 2 not in range(-100, 101)
                ):
                    errors["base"] = "invalid_imbalance"
            if errors:
                return self.async_show_form(
                    step_id="general",
                    data_schema=self._general_schema(user_input),
                    errors=errors,
                    description_placeholders={"source": self._source_text([])},
                )
            user_input = {
                key: int(value) if key in INT_KEYS else value
                for key, value in user_input.items()
                if key not in FAN_IMBALANCE_KEYS or value is not None
            }
            levels = [user_input[k] for k in PERCENTAGE_KEYS]
            if not 17 <= levels[0] < levels[1] < levels[2] <= 100:
                errors["base"] = "levels_order"
            coordinator = getattr(self._config_entry, "runtime_data", None)
            if coordinator is not None and not errors:
                try:
                    changes: dict[int, int] = {}
                    data = coordinator.unit_values()
                    if "automatic" in user_input and "param_63" not in data:
                        raise HomeAssistantError("Automatic mode configuration is unknown")
                    self._select_changes(user_input, data, changes)
                    await coordinator.async_write_settings(
                        {key: user_input[key] for key in BUS_SETTING_KEYS if key in user_input}
                    )
                    coordinator.clear_temporary_settings()
                    interval = user_input[CONF_FILTER_INTERVAL_DAYS]
                    if interval != coordinator.filter_interval_days():
                        await coordinator.async_set_filter_interval(interval)
                    if changes:
                        await coordinator.async_write_parameters(changes)
                except HomeAssistantError as err:
                    LOGGER.warning("Unable to write settings to the Novus: %s", err)
                    errors["base"] = "write_failed"
            if not errors:
                return self._save(
                    {key: value for key, value in user_input.items() if key != "automatic"}
                )

        coordinator = getattr(self._config_entry, "runtime_data", None)
        missing = (
            [k for k in coordinator.settings_not_read() if k not in FAN_STAGE_KEYS]
            if coordinator
            else []
        )
        return self.async_show_form(
            step_id="general",
            data_schema=self._general_schema(user_input),
            errors=errors,
            description_placeholders={"source": self._source_text(missing)},
        )

    def _general_schema(self, user_input=None) -> vol.Schema:
        fields: dict = {
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
        interval = (
            user_input.get(CONF_FILTER_INTERVAL_DAYS)
            if user_input and CONF_FILTER_INTERVAL_DAYS in user_input
            else self._value(CONF_FILTER_INTERVAL_DAYS, DEFAULT_FILTER_INTERVAL_DAYS)
        )
        fields[vol.Required(CONF_FILTER_INTERVAL_DAYS, default=str(interval))] = (
            _setting_selector(CONF_FILTER_INTERVAL_DAYS, int(interval))
        )
        fields.update([self._select_field("automatic", self._unit(), user_input)])
        for key, default in (
            (CONF_FAN_LEVEL_1_PERCENTAGE, DEFAULT_FAN_LEVEL_1_PERCENTAGE),
            (CONF_FAN_LEVEL_2_PERCENTAGE, DEFAULT_FAN_LEVEL_2_PERCENTAGE),
            (CONF_FAN_LEVEL_3_PERCENTAGE, DEFAULT_FAN_LEVEL_3_PERCENTAGE),
            (CONF_BOOST_DURATION_MINUTES, DEFAULT_BOOST_DURATION_MINUTES),
            (CONF_AWAY_DURATION_MINUTES, DEFAULT_AWAY_DURATION_MINUTES),
        ):
            current = int(
                user_input.get(key, self._value(key, default))
                if user_input
                else self._value(key, default)
            )
            if key in PERCENTAGE_KEYS:
                level_fields = {
                    vol.Required(key, default=current): _percentage_selector()
                }
                imbalance_key = FAN_IMBALANCE_KEYS[PERCENTAGE_KEYS.index(key)]
                imbalance = self._unit().get(imbalance_key)
                if user_input and imbalance_key in user_input:
                    imbalance = user_input[imbalance_key]
                elif imbalance is None:
                    imbalance = self._config_entry.options.get(imbalance_key)
                marker = (
                    vol.Optional(imbalance_key, default=imbalance)
                    if imbalance is not None
                    else vol.Optional(imbalance_key)
                )
                level_fields[marker] = selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-50,
                        max=50,
                        step=0.5,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="%",
                    )
                )
                level = PERCENTAGE_KEYS.index(key) + 1
                fields.update(
                    [self._section_field(f"fan_level_{level}", level_fields, required=True)]
                )
            else:
                fields[vol.Required(key, default=str(current))] = _setting_selector(
                    key, current
                )
        return vol.Schema(fields)

    def _unit(self) -> dict:
        coordinator = getattr(self._config_entry, "runtime_data", None)
        return coordinator.unit_values() if coordinator is not None else {}

    def _german(self) -> bool:
        return self.hass.config.language.startswith("de")

    def _missing(self) -> tuple[list[int], list[int]]:
        """Return (registers sent at power-on, registers sent by the panel menus) not yet known."""
        data = self._unit()
        boot, panel = DIALOG_REGISTERS[self._dialog]
        return (
            [reg for reg in boot if f"param_{reg:02x}" not in data],
            [reg for reg in panel if f"param_{reg:02x}" not in data],
        )

    async def _gate(self) -> FlowResult:
        """Explain missing unit values before the dialog opens."""
        boot, panel = self._missing()
        if not boot and not panel:
            return await self._open_dialog()
        german = self._german()
        parts = []
        if boot:
            parts.append(
                ("Wird nur beim Einschalten der Anlage gemeldet: " if german
                 else "Reported only when the unit is switched on: ")
                + ", ".join(f"0x{reg:02X}" for reg in boot)
            )
        if panel:
            names = "\n".join(
                f"- {PANEL_PAGES[reg][0 if german else 1]} (0x{reg:02X})" for reg in panel
            )
            parts.append(
                (
                    "**Am Bedienteil nötig:** Diese Werte sendet nur das Bedienteil. Öffne dort die Seite und bestätige den bereits eingestellten Wert nochmal (gleichen Eintrag auswählen/speichern, nichts ändern). Danach hier **Erneut prüfen**:\n"
                    if german
                    else "**Needed on the panel:** only the panel sends these values. Open the page there and confirm the already selected value again (select/save the same entry, change nothing). Then **Check again** here:\n"
                )
                + names
            )
        if getattr(self, "_rechecked", False):
            self._rechecked = False
            parts.insert(
                0,
                "**Erneut geprüft: Die Werte fehlen weiterhin.**" if german
                else "**Checked again: the values are still missing.**",
            )
        options = ["missing_restart", "missing_recheck", "missing_open"]
        return self.async_show_menu(
            step_id="missing",
            menu_options=options,
            description_placeholders={"missing": "\n\n".join(parts)},
        )

    async def _open_dialog(self) -> FlowResult:
        if self._dialog == "bypass":
            return await self.async_step_bypass_form()
        return await self.async_step_plant_form()

    async def async_step_plant(self, user_input=None) -> FlowResult:
        """Open the plant parameters, explaining missing unit values first."""
        self._dialog = "plant"
        return await self._gate()

    async def async_step_bypass(self, user_input=None) -> FlowResult:
        """Open the bypass and summer ventilation settings."""
        self._dialog = "bypass"
        return await self._gate()

    async def async_step_missing(self, user_input=None) -> FlowResult:
        return await self._gate()

    async def async_step_missing_recheck(self, user_input=None) -> FlowResult:
        self._rechecked = True
        return await self._gate()

    async def async_step_missing_open(self, user_input=None) -> FlowResult:
        return await self._open_dialog()

    async def async_step_missing_restart(self, user_input=None) -> FlowResult:
        """Power-cycle the unit so it re-sends its start-up parameters, then wait."""
        coordinator = getattr(self._config_entry, "runtime_data", None)
        if coordinator is not None:
            try:
                if coordinator.unit_values().get("run_state") != "stopped":
                    await coordinator.async_set_power(False)
                    await asyncio.sleep(3)
                await coordinator.async_set_power(True)
            except HomeAssistantError:
                pass
            for _ in range(60 if self._missing()[0] else 20):
                if not any(self._missing()):
                    break
                await asyncio.sleep(1)
        return await self._gate()

    async def _write(self, changes: dict[int, int]) -> str | None:
        coordinator = getattr(self._config_entry, "runtime_data", None)
        if coordinator is None:
            return "not_loaded"
        try:
            await coordinator.async_write_parameters(changes)
        except (HomeAssistantError, ValueError):
            return "write_failed"
        return None

    def _number_fields(self, regs, data, user_input) -> dict:
        """Temperature fields as text so they always show one decimal ("23.0")."""
        fields = {}
        for reg in regs:
            key = f"p{reg:02x}"
            if user_input and key in user_input:
                current = str(user_input[key])
            elif data.get(f"param_{reg:02x}") is not None:
                current = f"{data[f'param_{reg:02x}'] / 10:.1f}"
            else:
                current = None
            marker = (
                vol.Optional(key, default=current)
                if current is not None
                else vol.Optional(key)
            )
            fields[marker] = selector.TextSelector(
                selector.TextSelectorConfig(
                    suffix="K" if reg in HYSTERESIS_REGISTERS else "°C",
                )
            )
        return fields

    @staticmethod
    def _number_changes(regs, user_input, data, changes, errors=None) -> None:
        for reg in regs:
            key = f"p{reg:02x}"
            text = str(user_input.get(key) or "").strip().replace(",", ".")
            if not text:
                continue
            low, high = PARAMETER_LIMITS[reg]
            try:
                raw = round(float(text) * 10)
            except ValueError:
                raw = None
            if raw is None or not low <= raw <= high or (
                reg in HYSTERESIS_REGISTERS and raw % 5
            ):
                if errors is not None:
                    errors[key] = "invalid_number"
                continue
            if raw != data.get(f"param_{reg:02x}"):
                changes[reg] = raw

    def _select_field(self, name, data, user_input):
        reg, mask, options = PLANT_SELECTS[name]
        german = self._german()
        raw = data.get(f"param_{reg:02x}")
        current = None
        if raw is not None:
            key = raw if mask is None else raw & mask
            current = next((o for o, (v, _, _) in options.items() if v == key), None)
        if user_input and name in user_input:
            current = user_input[name]
        if name == "ewt" and current is not None and not isinstance(current, bool):
            current = current == "4"
        marker = (
            vol.Optional(name, default=current) if current is not None else vol.Optional(name)
        )
        if name == "ewt":
            return marker, selector.BooleanSelector()
        return marker, selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=o, label=de if german else en)
                    for o, (_, de, en) in options.items()
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )

    @staticmethod
    def _select_changes(user_input, data, changes) -> None:
        for name, (reg, mask, options) in PLANT_SELECTS.items():
            selected = user_input.get(name)
            if name == "ewt" and isinstance(selected, bool):
                selected = "4" if selected else "0"
            if selected not in options:
                continue
            value = options[selected][0]
            if mask is not None:
                value = (data.get(f"param_{reg:02x}", SELECT_DEFAULT_BASE[reg]) & ~mask) | value
            if value != data.get(f"param_{reg:02x}"):
                changes[reg] = value

    async def async_step_plant_form(self, user_input=None) -> FlowResult:
        """Automatic mode, frost protection, reheating and installation types."""
        data = self._unit()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._flatten_sections(user_input, PLANT_FORM_GROUPS)
            changes: dict[int, int] = {}
            self._number_changes(PLANT_NUMBERS, user_input, data, changes, errors)
            if errors:
                errors["base"] = "invalid_number"
            self._select_changes(user_input, data, changes)
            if not errors:
                error = await self._write(changes)
                if not error:
                    return self._save({})
                errors["base"] = error
        numbers = dict(zip(PLANT_NUMBERS, self._number_fields(PLANT_NUMBERS, data, user_input).items()))
        fields = {}
        for name, items in PLANT_FORM_GROUPS.items():
            group = {}
            for item in items:
                marker, sel = (
                    numbers[item] if isinstance(item, int)
                    else self._select_field(item, data, user_input)
                )
                group[marker] = sel
            fields.update([self._section_field(name, group)])
        return self.async_show_form(
            step_id="plant_form", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_bypass_form(self, user_input=None) -> FlowResult:
        """Bypass installation and temperature thresholds.

        Installation changes require a known unit word so unrelated flags survive.
        """
        data = self._unit()
        word = data.get("param_1b")
        known = word is not None
        shown = {
            name: (bool(word & mask) != inverted) if known else name == "bypass"
            for name, (_, mask, inverted) in PLANT_FLAGS.items()
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = self._flatten_sections(user_input, ("summer_ventilation",))
            changes: dict[int, int] = {}
            self._number_changes(BYPASS_NUMBERS, user_input, data, changes, errors)
            value = word
            for name, (_, mask, inverted) in PLANT_FLAGS.items():
                if name in user_input and bool(user_input[name]) != shown[name]:
                    if not known:
                        errors["base"] = "configuration_unknown"
                        continue
                    on = bool(user_input[name]) != inverted
                    value = (value | mask) if on else (value & ~mask)
                    changes[0x1B] = value
            if not errors:
                error = await self._write(changes)
                if not error:
                    return self._save({})
                errors["base"] = error
        german = self._german()
        fields = {
            vol.Optional(
                name,
                default=bool(user_input[name]) if user_input and name in user_input else shown[name],
            ): selector.BooleanSelector()
            for name in PLANT_FLAGS
        }
        fields.update(
            [
                self._section_field(
                    "summer_ventilation",
                    self._number_fields(BYPASS_NUMBERS, data, user_input),
                    collapsed=False,
                )
            ]
        )
        note = ""
        if not known:
            note = (
                "**Aktueller Wert unbekannt** (am Bedienteil die Seite „Bypass“ öffnen). Die Installation kann erst nach Empfang des Anlagenwerts geändert werden.\n\n"
                if german
                else "**Current value unknown** (open the bypass page on the panel). Installation can only be changed after the unit configuration has been received.\n\n"
            )
        return self.async_show_form(
            step_id="bypass_form",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={"state": note},
        )

    async def _threshold_form(self, step_id, regs, user_input) -> FlowResult:
        data = self._unit()
        errors: dict[str, str] = {}
        if user_input is not None:
            changes: dict[int, int] = {}
            self._number_changes(regs, user_input, data, changes, errors)
            if not errors:
                error = await self._write(changes)
                if not error:
                    return self._save({})
                errors["base"] = error
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(self._number_fields(regs, data, user_input)),
            errors=errors,
        )

    async def async_step_bypass_settings(self, user_input=None) -> FlowResult:
        """Bypass thresholds; without a bypass only the summer ventilation ones remain."""
        word = self._unit().get("param_1b")
        if word is not None and word & 0x04:
            return await self.async_step_summer_settings()
        return await self._threshold_form("bypass_settings", (0x41, 0x42, 0x43, 0x49), user_input)

    async def async_step_summer_settings(self, user_input=None) -> FlowResult:
        """Summer ventilation without bypass (shares registers with the bypass)."""
        word = self._unit().get("param_1b")
        if word is None or not word & 0x80:
            return self._save({})
        return await self._threshold_form("summer_settings", (0x41, 0x43, 0x49), user_input)

    async def async_step_advanced(
        self, user_input: dict[str, str | int | bool] | None = None
    ) -> FlowResult:
        """Show the unit's start-up parameter block (read only)."""
        if user_input is not None:
            return self._save({})
        coordinator = getattr(self._config_entry, "runtime_data", None)
        data = coordinator.unit_values() if coordinator is not None else {}
        german = self.hass.config.language.startswith("de")
        params = sorted(
            (key, value)
            for key, value in data.items()
            if key.startswith("param_")
            and int(key[6:], 16) not in RESOLVED_REGISTERS
        )
        if params:
            lines = []
            for key, value in params:
                reg = int(key[6:], 16)
                info = PARAMETER_INFO.get(reg)
                label = (info[0] if german else info[1]) if info else (
                    "unbekannt" if german else "unknown"
                )
                if info:
                    unit, divisor = info[2], info[3]
                    shown = f"{value / divisor:.1f}" if divisor > 1 else str(value)
                    shown = f"{shown} {unit}".strip()
                else:
                    shown = str(value)
                lines.append(f"- 0x{reg:02X} {label}: **{shown}** (raw {value})")
            values = "\n".join(lines)
        else:
            values = (
                "Noch nicht gelesen. Die Anlage sendet diese Werte nur beim Einschalten."
                if german
                else "Not read yet. The unit only sends these values at power-on."
            )
        return self.async_show_form(
            step_id="advanced",
            data_schema=vol.Schema({}),
            description_placeholders={"values": values},
        )
