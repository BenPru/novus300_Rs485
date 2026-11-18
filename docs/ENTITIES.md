# Entities and attributes

Deutsch: [ENTITIES.de.md](ENTITIES.de.md)

All entities belong to the device **Paul Novus 300** (model Novus 300 (FOCUS250),
bus version 1.7.1). Their `unique_id` starts with `novus300bus_` followed by the
key shown below.

## Overview

| Entity ID | Platform | Name | Category | Available when the unit is off |
| --- | --- | --- | --- | --- |
| `switch.novus300_power` | switch | Betriebsstatus | – | yes |
| `switch.novus300_bypass` | switch | Bypass geöffnet | – | no |
| `fan.novus300` | fan | Lüftung | – | no |
| `select.novus300_ventilation_mode` | select | Lüftungsmodus | – | no |
| `button.novus300_boost` | button | Stoßlüftung | – | no |
| `button.novus300_filter_reset` | button | Filterlaufzeit zurücksetzen | – | no |
| `sensor.novus300_supply_air_temperature` | sensor | Zuluft Temperatur Räume | – | no |
| `sensor.novus300_outdoor_air_temperature` | sensor | Außenluft Temperatur | – | no |
| `sensor.novus300_extract_air_temperature` | sensor | Abluft Temperatur Räume | – | no |
| `sensor.novus300_exhaust_air_temperature` | sensor | Fortluft Temperatur | – | no |
| `sensor.novus300_message` | sensor | Meldung | diagnostic | yes |
| `sensor.novus300_operating_time` | sensor | Gesamtbetriebszeit | diagnostic | yes |
| `sensor.novus300_fan_operating_time` | sensor | Lüfterbetriebszeit | diagnostic | yes |
| `sensor.novus300_filter_time_remaining` | sensor | Filter Restlaufzeit | diagnostic | yes |
| `sensor.novus300_register_44` | sensor | Register 0x44 (Rohwert, unbekannt) | diagnostic, disabled by default | yes |
| `sensor.novus300_register_62` | sensor | Register 0x62 (Rohwert, unbekannt) | diagnostic, disabled by default | yes |

An entity is also unavailable until its register has been seen on the bus
(the unit broadcasts some registers only occasionally, e.g. when it starts).
"Unit off" always means the run state "stopped" reported by the unit.

## Switches

### `switch.novus300_power` – Betriebsstatus

Switches the unit on and off over the bus (the panel's frames for register
0x07) and shows the run state.

| State | Meaning |
| --- | --- |
| `on` | run state `running` or `starting` |
| `off` | run state `stopped` |
| `unknown` | run state not recognised |

| Attribute | Description |
| --- | --- |
| `run_state` | `stopped` (raw 0), `running` (raw 1), `starting` (raw 3) or `unknown` |
| `raw_value` | raw value of the run-state register |
| `config_fan_level_1_percentage`, `_2_`, `_3_`, `config_boost_duration_minutes`, `config_away_minutes_per_hour`, `config_filter_interval_days` | current settings (from the bus, else from the options) |
| `serial_panel`, `serial_fan_slave`, `serial_defroster` | serial numbers of the connected components (once seen on the bus) |

The icon follows the run state (stop, play, progress clock, help). After
sending, the integration waits up to 5 s for the new run state and retries up
to three times before it raises an error. The unit accepts "on" only about 30
seconds after "off", because the panel shows a message first. Requires the
`socket://` bridge started with `--allow-command-frames`.

### `switch.novus300_bypass` – Bypass geöffnet

Read-only: `turn_on` and `turn_off` raise an error until opening and closing
the bypass is known. `on` means the bypass is open or moving.

| Attribute | Description |
| --- | --- |
| `air_path` | `heat_recovery`, `bypass`, `transition` (both flags set) or `unknown` |
| `raw_value` | status word of the unit (flags 0x08 heat recovery, 0x20 bypass) |

Note: the bypass actuator of the author's unit is defective, so the states
`bypass` and `transition` could never be observed or recorded.

## Fan

### `fan.novus300` – Lüftung

Always present. It shows the percentage of the active level (e.g. 60 % in
level 2) and controls the ventilation with a target percentage. Its state is the
percentage (e.g. `60`) or `off`, with and without 0-10 V.

* Without 0-10 V: a target below level 2 selects level 1 and temporarily sets
  its percentage to the target, above level 2 level 3 likewise; the original
  percentages are restored when the level is left.
* With 0-10 V (option **0-10 V: Enable fan control**): a target above 0 selects
  automatic mode and writes the value via Tinkerforge.
* 1–16 % are raised to 17 %. 0 % and `turn_off` select away mode; the fan then
  shows 0 % / off.
* Unavailable while the unit is off.

| Attribute | Description |
| --- | --- |
| `ventilation_mode` | `automatic`, `level_1`, `level_2`, `level_3`, `boost`, `away`, `standby` or `unknown` |
| `original_levels` | levels temporarily overridden with their original percentage (`fan_level_1_percentage`, `fan_level_3_percentage`) |
| `bus_setpoint` | raw fan control value sent by the unit (register 0x55) in % |
| `away_minutes_per_hour` | only in away mode: ventilation minutes per hour |
| `run_state` | only with 0-10 V: run state of the unit |
| `analog_percentage` | only with 0-10 V: value of the analog output in % |
| `preset_modes`, `preset_mode` | only with 0-10 V in automatic mode: `Automatik` / `Manuell`, derived from the helper entity (default `input_boolean.luftung_automatik`) |

## Select and buttons

### `select.novus300_ventilation_mode` – Lüftungsmodus

Options: `automatic`, `level_1`, `level_2`, `level_3`, `away`, `boost`. The
current option is the mode the unit reports. Standby is not accepted by the
unit. Unavailable while the unit is off. While the fan percentage has temporarily
changed level 1 or 3, the select shows `automatic` (option **Show levels instead of
automatic…** shows the real level instead). Selecting a level restores its original
percentage.

### `button.novus300_boost` – Stoßlüftung

Selects boost mode and returns to the previous mode after the configured boost
duration. Unavailable while the unit is off.

### `button.novus300_filter_reset` – Filterlaufzeit zurücksetzen

Restarts the filter run time (writes the filter interval to the unit). Unavailable while the unit is off.

## Sensors

### Temperatures

`supply_air_temperature`, `outdoor_air_temperature`, `extract_air_temperature`
and `exhaust_air_temperature`: °C, device class temperature, state class
measurement, no extra attributes.

### `sensor.novus300_message` – Meldung

Diagnostic. The state is either a status change or the unit's own message.

* **Transition** (only while it lasts; stable states are shown by the
  switches): "Anlage fährt hoch", "Anlagenstatus unbekannt (Wert n)",
  "Bypass in Bewegung", "Luftweg unbekannt" (only while running), and
  "Anlage fährt runter" for 45 s after switching off (the unit reports no
  shutdown phase). While off, the last real unit message is shown.
* **Unit message** otherwise: "Keine Meldung", "Filter wechseln",
  "Fehler am Eingang", "Fehler Bypass" or "Meldung <code>".

| Attribute | Description |
| --- | --- |
| `code` | code of the unit's current message (0 = none, 0x41 = 65 filter change, 0x83 = 131 input error, 0x89 = 137 bypass error) |
| `occurred_at` | when the shown message or status change occurred (ISO time); Home Assistant's own "last updated" cannot be set |
| `previous_message`, `previous_message_2`, `previous_message_3` | the unit's own last three messages as text: time, code, message, translated detail |
| `observed` | message changes seen by Home Assistant (time, message), newest first, up to 10 |
| `status_events` | the last 10 changes of run state or air path as text with time, newest first |

The unit stores its last three messages and broadcasts them only when it
starts up; the integration keeps them.

### Counters (diagnostic)

| Entity | Unit | Description |
| --- | --- | --- |
| `operating_time` | h | total operating time |
| `fan_operating_time` | h | fan operating time |
| `filter_time_remaining` | d | remaining filter run time (0 = change the filter) |

They are broadcast with the unit's complete register dump; the last known value
is restored after a restart until a new one arrives.

### Raw registers (diagnostic, disabled by default)

`register_44` and `register_62` expose the still unidentified registers 0x44
and 0x62 as raw numbers.

## Services

| Service | Description |
| --- | --- |
| `novus300bus.sync_clock` | set the unit's date and time to Home Assistant's local time and verify the drift |
| `novus300bus.reset_filter` | restart the filter run time (same as the button) |

## Options

Serial device / bridge URL, baud rate, parity, **Synchronize time daily**
(03:00), ventilation levels 1–3 in % (17 % ≤ level 1 < level 2 < level 3 ≤
100 %), boost duration, away ventilation time (minutes per hour), filter
interval (30–180 d), and the 0-10 V options (enable, Tinkerforge host, port
and UID, automatic mode helper entity). Levels, durations and the filter
interval are written to the unit when the options are saved.
