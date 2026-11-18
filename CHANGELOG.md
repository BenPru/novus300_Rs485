# Changelog

Date-based versioning: `YEAR.MONTH.DAY`. Deutsch: [CHANGELOG.de.md](CHANGELOG.de.md)

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
