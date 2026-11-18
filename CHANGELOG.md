# Changelog

Date-based versioning: `YEAR.MONTH.DAY`. Deutsch: [CHANGELOG.de.md](CHANGELOG.de.md)

## 2026.11.18

### Highlights
- **Continuously variable fan control over the bus:** `fan.novus300` now works with a slider and percentage directly over RS-485, no 0-10 V hardware (Tinkerforge) needed. Automatic mode shows the real control percentage.
- **Switch the unit on and off** (`switch.novus300_power`) and see bypass and run state.
- **Ready-made dashboard** from standard cards only: airflow graphic, highlighted mode buttons, colour-coded boost / message / filter tiles, status-change history. Screenshots in the README.
- **Clear mode display:** the select stays on "Automatic" while a percentage is set; levels keep their original percentages (optionally show real levels).
- **Messages and status changes** of the unit with history, plus extended documentation, automation examples and a full entity list.

### Added
- **`switch.novus300_power` ("Betriebsstatus")** switches the unit on and off over the bus (panel frames for register 0x07) and shows the run state with its icon and the attribute `run_state`. Switching on is only accepted by the unit about 30 seconds after switching off.
- **`switch.novus300_bypass` ("Bypass geöffnet")**: read-only bypass state (opening/closing is not known yet), attributes `air_path` and `raw_value`.
- **Status changes in `sensor.novus300_message`:** every change of the run state (e.g. "Anlage fährt hoch") or the air path (e.g. "Bypass in Bewegung") is logged in the attribute `status_events`; transitions only ("Anlage startet", "Bypass in Bewegung", unknown values) are shown as the message while they last, taking precedence over the unit's own message. Stable states are not shown (see the switches).
- `fan.novus300` has the attributes `bus_setpoint` and, in away mode, `away_minutes_per_hour`.
- `switch.novus300_power` also exposes the serial numbers of the panel, fan slave and defroster and the current settings (`config_*`) as attributes.
- **Fan (bus mode):** the state is now the percentage (or `off`) like with 0-10 V, so the slider and percentage are shown instead of on/off.
- **Fan (bus mode):** in automatic mode the percentage is the 0-10 V signal the unit measures (`bus_setpoint`, last known value if it drops to 0) instead of 0 %/off.
- **Fan levels:** when the fan percentage temporarily overrides level 1/3, the mode select shows `automatic` by default (new option to show the real level); selecting a level restores its original percentage. The options now show the original level percentage instead of the temporary one.
- **Dashboard:** ready-made `dashboards/novus300.yaml` built from standard Home Assistant cards only (no HACS cards): airflow graphic with clickable temperatures, mode buttons with the active level highlighted (`select-options` tile feature), fan slider, boost / bypass / run-state tiles, colour-highlighted tiles that appear only when relevant (boost active = blue, message present = red, filter remaining time 0 = red), maintenance card, attribute details and status-change list. Screenshots: [docs/images/dashboard.png](docs/images/dashboard.png).
- **Option "Show levels instead of automatic when the fan is set by percentage"** (`show_fan_levels`, off by default): off = the mode select stays on `automatic` while a fan percentage is active; on = it shows level 1/3 like the unit.
- **Documentation:** complete list of all entities and attributes in [docs/ENTITIES.md](docs/ENTITIES.md).
- **Serial bridge (`tools/`):** the power frames (off/on) are now allowed.

### Fixed
- Switching from a level to automatic no longer leaves the unit at 0 %; the last automatic percentage is used.
- `fan.turn_on` failed with an error (also with 0-10 V); 0 % / `turn_off` now select away mode.

### Changed
- **Entity names are now translatable:** English is the default (e.g. "Boost ventilation", "Operating state", "Supply air temperature"), German remains available for German installations. Entity IDs are unchanged. [docs/ENTITIES.md](docs/ENTITIES.md) lists the English names.
- `sensor.novus300_message` is now a diagnostic entity.
- `fan.novus300`, `select.novus300_ventilation_mode` and `button.novus300_boost` and `button.novus300_filter_reset` are unavailable while the unit is off.
- Level percentages in the options dialog start at 17 % (levels must satisfy 17 % ≤ level 1 < level 2 < level 3 ≤ 100 %). `fan.novus300` raises targets of 1–16 % to 17 %, also with 0-10 V (the Home Assistant slider itself cannot be limited). 0 % (and turn off) selects away mode; the fan then shows 0 % / off.

### Documentation
- Table of contents, updated introduction (the integration no longer only reads), screenshots, automation examples and a detailed description of every field in the options dialog.

## 2026.11.17

### Added
- **`fan.novus300` is always available** and shows the percentage of the active level (e.g. level 2). Setting a percentage: with 0-10 V enabled it selects automatic mode and writes the value via Tinkerforge; without 0-10 V it controls the unit over the bus.
- **Fan without 0-10 V:** the bus control works as follows. A target below level 2 selects level 1 and temporarily sets its percentage to the target, above level 2 it selects level 3 likewise; the original level 1/3 percentage is stored (persistently) and written back when the level is left.
- **Device info:** model Novus 300 (FOCUS250), bus version 1.7.1; panel, fan slave and defroster appear as "Paul Novus 300 …" sub-devices whose software versions (ETA0036E29A, SWZ0025B26A, ST00064E24A) are read from the unit's start-up announcement; known values are used as defaults.
- **`sensor.novus300_message`:** current unit message (e.g. "Filter wechseln", code 0x41 in register 0x09) with icon; attributes `previous_message`, `previous_message_2`, `previous_message_3` hold the unit's own last three messages as readable text (time, code, message, translated detail), `occurred_at` gives when the latest message occurred (Home Assistant's own "last updated" cannot be set); message icon (registers 0x0A–0x0C, 0x88–0x8D, broadcast by the unit when it starts up and stored by the integration); `observed` lists changes seen by Home Assistant.
- **Diagnostic raw sensors** (disabled by default) for the still unidentified registers 0x44 and 0x62.
- **Unit off:** `fan.novus300` shows off (0 %, attribute `run_state`) while the unit reports "stopped"; temperatures, fan setpoint, air path and bypass become unavailable instead of showing stale values.
- **Filter runtime reset:** `button.novus300_filter_reset` and `novus300bus.reset_filter` service.
- **Filter interval is now an option** (30–180 d) written to the unit; `sensor.novus300_filter_interval` was removed.
- **Send the ventilation mode over RS-485:** `select.novus300_ventilation_mode` sets automatic, levels 1–3, away and boost directly on the bus.
- **`button.novus300_boost`** triggers the boost level on the bus (no longer via 0-10 V).
- **`novus300bus.sync_clock` service** to trigger the clock synchronization manually.
- **Synchronize time daily:** new option (default: on), syncs every day at 03:00 and verifies the resulting drift.
- **Unit settings over the bus:** fan levels 1–3 (%) and the boost/away durations are written to the unit when the options are saved. The values last seen on the bus are shown.
- **Serial bridge (`tools/`):** write access only for validated frames (mode, date/time, settings) with CRC and range checks; example systemd unit included.
- Documentation (EN/DE) and tests for clock, date and settings frames.

### Changed
- Fan levels are validated like the unit does (17 % ≤ level 1 < level 2 < level 3 ≤ 100 %); written values stay visible until the unit broadcasts them again.
- Menu settings (fan levels, boost, away) sent by the unit are stored in the integration options automatically (no reload).
- Unit settings are no longer cached when written; only values the unit sends itself count as read. The options dialog states which values are still defaults. Boost default 15 min (factory).
- Options dialog reordered: serial connection, daily sync, levels in %, boost duration, away time (min/h), then the 0-10 V settings. Levels are plain number fields (0–100 %), durations are dropdowns, labels unified.
- Away is now "ventilation time per hour" (15 / 30 / 45 min/h, as in the manual) instead of a duration.

- `sensor.novus300_fan_setpoint` shows the level percentage also for boost (level 3) and away (level 1, attribute `away_minutes_per_hour`). On the bus it is only the measured 0-10 V control signal, not the real fan speed.

### Removed
- Percentage values for boost and away.
- `sensor.novus300_clock` and `sensor.novus300_clock_drift`.
- `sensor.novus300_ventilation_mode` (replaced by `select.novus300_ventilation_mode`).

### Fixed
- `fan.py`: callback error on state changes.

### Notes
- The unit cannot be queried; the effect of written settings was only verified with unchanged values.
- The control panel may keep showing the previous mode after a bus command.
- If a dashboard uses the removed sensor, switch it to the select entity.

## 2026.11.2

- First HACS-ready release: RS-485 integration for the Paul Novus 300, English and German setup documentation, optional Tinkerforge guidance, HACS brand icon, GPL-3.0-only license and validation workflows.
