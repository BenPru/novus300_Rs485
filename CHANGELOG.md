# Changelog

Date-based versioning: `YEAR.MONTH.DAY`. Deutsch: [CHANGELOG.de.md](CHANGELOG.de.md)

## 2026.11.17

### Added
- **Send the ventilation mode over RS-485:** `select.novus300_ventilation_mode` sets automatic, levels 1–3, away and boost directly on the bus.
- **`button.novus300_boost`** triggers the boost level on the bus (no longer via 0-10 V).
- **`novus300bus.sync_clock` service** to trigger the clock synchronization manually.
- **Synchronize time daily:** new option (default: on), syncs every day at 03:00 and verifies the resulting drift.
- **Unit settings over the bus:** fan levels 1–3 (%) and the boost/away durations are written to the unit when the options are saved. The values last seen on the bus are shown.
- **Serial bridge (`tools/`):** write access only for validated frames (mode, date/time, settings) with CRC and range checks; example systemd unit included.
- Documentation (EN/DE) and tests for clock, date and settings frames.

### Changed
- Options dialog reordered: serial connection, daily sync, levels in %, boost duration, away time (min/h), then the 0-10 V settings. Levels are plain number fields (0–100 %), durations are dropdowns, labels unified.
- Away is now "ventilation time per hour" (15 / 30 / 45 min/h, as in the manual) instead of a duration.

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
