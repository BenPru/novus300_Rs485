# Changelog

Date-based versioning: `YEAR.MONTH.DAY`. Deutsch: [CHANGELOG.de.md](CHANGELOG.de.md)

## 2026.11.21

### Highlights
- **Correct bypass detection:** the installation bit was interpreted backwards. An installed bypass is now recognised independently of its activation state, restoring the matching entity and equipment display.
- **Defroster presence from the short status:** distinguish installed/absent without opening the panel menu. The exact electric/PTC/brine type is deliberately not guessed.

### Fixed
- Decode bypass installation bit `0x04` separately from activation bit `0x08` in register `0x1B`. The configuration checkbox and parameter builder use the same validated interpretation and preserve the other flags.
- Enable bypass feedback for units with a bypass, and summer ventilation only for units configured without one. Preserve manually disabled entities.
- Keep short register `0x1E` as `defroster_status_raw`, separate from the extended panel type. Expose generic presence as `fan.novus300` attribute `defroster_installed`; confirmed absence hides both defroster overlays and no longer requires a missing panel type in the settings dialog.
- Accept the valid bypass flag combinations in the serial bridge whitelist, retaining CRC validation and restrictions on other writes.

### Upgrade and validation notes
- Update the integration **and the bridge script**, then restart Home Assistant and the bridge service. No ventilation-unit restart or automatic installation-parameter writes are needed. Dashboard files are unchanged.
- **61 bus-free regression tests pass.** Short-status presence was compared with two known hardware configurations; this does not establish a universal exact-type mapping.
- **Direct bypass opening/closing remains unsupported.** Correct equipment detection does not prove a physical flap position; summer ventilation does not force the flap.

## 2026.11.20

### Highlights
- **Automatable summer ventilation:** new `switch.novus300_summer_ventilation` replaces the activation checkbox in the options. It is offered only when the unit configuration confirms an installed bypass.
- **Fan imbalance fine adjustment:** each of the three ventilation levels now has its own signed adjustment, −50 to +50 % in 0.5-percent steps, next to its speed setting.
- **Dynamic second dashboard view:** the "Sensoren" view now uses a base diagram and separate equipment overlays, with temperatures at the sensor locations and a compact layout. Both views and the independent editable dashboard copy are now documented in English and German.
- **Optional dynamic bus addresses:** experimental receive-only compatibility setting, off by default, available during setup and bus reconfiguration. CRC validation stays enabled; write destinations and bus timing are unchanged.

### Added
- **Dynamic receive headers:** when enabled, accept CRC-valid frames with a first header byte other than `00/01`, including native `00` headers. The second header byte was already unrestricted. Retain the existing missing-marker repair and recover from incomplete false headers. This does not discover device/address mappings, change register layouts or establish a fix for issue #10.
- English/German diagnostic collection and privacy guides, plus a bug/hardware issue form with timestamped actions and raw-buffer limits. The form requires a `.json`/`.zip` diagnostic upload; blank issues are disabled for normal contributors. This does not enforce diagnostic content or prevent CLI/API-created issues. Diagnostics are not anonymized; review attachments before public upload.
- Signed decoding, encoding, persistence and options synchronization for imbalance registers `0x31`, `0x32` and `0x33`. Positive level/imbalance changes and summer on/off frames have regression tests from panel captures; negative values and boundaries are tested with generated frames.
- Summer activation changes only bit `0x80` in the known plant word `0x1B`. Parameter writes share a lock and installation changes merge against the latest word, preserving the summer flag.
- Summer commands wait up to 15 seconds for matching bus feedback and raise an explicit error on missing confirmation or write failure, without an optimistic state change.
- A summer-ventilation tile and automation examples; the existing bypass tile opens its details instead of attempting unsupported flap control.
- Fan attributes for installed bypass, reheater, earth heat exchanger, defroster and brine defroster, plus the automatic subtype when known.
- A structured `message_table` attribute and additional disabled-by-default diagnostic sensors for hardware configuration and system-status bits.

### Changed
- **Grouped options:** each ventilation level and its imbalance share a section. Frost protection (including minimum supply air temperature), reheating and summer ventilation have their own sections with shorter labels. Summer ventilation starts expanded; other sections start collapsed. The EWT installed field is a checkbox.
- **Settings order:** daily time sync, filter interval, automatic mode, then "Show levels instead of automatic" directly underneath, followed by the grouped ventilation levels. EWT is first on the plant page; defroster type precedes frost protection mode. Writable thresholds live in their matching sections; read-only characteristic values appear only on the final advanced page.
- "Summer ventilation active" is in the device's **Configuration** block. Filter reset is a diagnostic button.
- Bypass and summer switch entities are enabled/disabled from the plant flag as values arrive, preserving manual user disabling. Obsolete installed-part binary sensors are removed in favour of fan attributes.
- Replaced `novus300-schema.svg` with `novus300-base.svg` and transparent reheater/EWT/brine/bypass/defroster layers. The overview keeps its airflow graphic; both views need no custom frontend cards.
- Updated earth-heat-exchanger installation labels and English/German entity/dashboard documentation. YAML and editable UI dashboards are maintained independently; README links simplify HACS installation and integration setup.

### Fixed
- **Fan restoration:** preserve the remembered original percentage if a later temporary percentage change fails, allowing subsequent restoration of the inactive stage. Tests cover panel mode feedback, preservation of an active override and retry after write errors.
- **Half-percent imbalance:** accept 0.5 % steps without integer truncation in encoding, decoding and persistence (one signed raw increment = 0.5 %).
- Known unit readings populate section defaults and replace stale form values without writes. Unknown fields stay blank; invalid submissions remain visible for correction. Stored options stay compatible.
- Unknown imbalance fields stay blank and are not silently written as zero when other settings are saved. The existing ordering rule applies to fan speeds only, not imbalance.
- The general settings dialog now reports write failures instead of saving as if they succeeded. Bypass installation cannot be changed with an unknown plant word.
- The bridge whitelist accepts only the new single-register imbalance writes in the supported signed range; CRC checks and restrictions on other registers remain intact.

### Upgrade and validation notes
- This release was updated in place without a version bump. If already installed, re-download/reinstall **2026.11.20** to obtain the additions, then restart Home Assistant. Dynamic bus addresses remain disabled unless explicitly enabled under **Reconfigure → Interface: RS-485 bus**.
- **Update the bridge script** on the serial host as well as the integration, restart the bridge service and Home Assistant, then update the dashboard YAML and any editable copy independently. Integration/HACS updates do not overwrite a UI dashboard.
- Existing entity IDs remain stable. Automations using summer activation should use `switch.novus300_summer_ventilation`; installation and temperature thresholds remain in the options.
- **55 bus-free regression tests** cover protocol, bridge, coordinator, entity registry and config/options flows, including dynamic headers, CRC rejection, fragmented input and resynchronization. No ventilation settings or bypass position were changed for testing.
- Same-stage panel reselection is not established by existing captures. Stage writes do not wait for unit confirmation.
- **Direct bypass opening/closing is still not implemented.** Register `0x1A` is feedback, not a verified actuator command. Summer activation does not force the flap. Bus feedback is not hardware confirmation; physical flap movement was not tested.

## 2026.11.19

### Highlights
- **Writable unit parameters in the options dialog:** new dialogs "Plant parameters" (automatic mode, frost protection, minimum supply air, reheater, defroster, ground-heat-exchanger damper) and "Bypass and summer ventilation" (bypass installed, summer ventilation, thresholds, hysteresis). Temperatures with one decimal.
- **Gate dialog for missing unit values:** if values are missing, a menu names them and offers "Restart unit" (only on request), "Check again" and "Open anyway". Values only the panel sends are listed with the panel menu path and what to do there.
- **Easier dashboard installation:** the integration serves the graphic itself (no more copying to `config/www/`), plus a detailed guide: [docs/DASHBOARD.md](docs/DASHBOARD.md).

### New
- The "Advanced" dialog now lists only registers that are still unassigned; resolved ones live in the new dialogs.
- Diagnostics (`diagnostics.py`) and fr/es/it/nl translations (new dialogs in English for now).
- Temperature sensors with dedicated icons and a fixed order.
- **Error codes:** all codes from the manual (sensors, fans, bypass, bus/communication) are named; the message sensor gets a `hint` attribute with cause and action.
- **New dialog "Thresholds":** hysteresis (frost protection supply air, reheating, earth heat exchanger damper), brine defroster cooling threshold and damper thresholds are writable; the sensor characteristic is shown read-only. "Advanced" shows names and units from the register list of novus2mqtt.
- Fix: the start-up dump is now fully decoded (bypass/summer ventilation, reheating, damper, frost protection mode are read after a unit restart).
- **Bypass switch** is disabled by default (enable it if your unit has a bypass); new attribute bypass_present from the plant flag, writes are rejected with a matching message.
- **New button "Request all values"** (diagnostic): sends the memory dump request (0x83) so the unit resends all registers, e.g. to fill missing values without a restart. It briefly disturbs the panel. The bridge must be updated for it.
- **Dashboard view "Sensors":** own unit diagram (`novus300-schema.svg`) with the temperatures and bypass state in the place of the sensors.
- **Serial bridge (`tools/`):** whitelist extended for the parameter and selection registers (update it on the bridge host).

### Changed
- `dashboards/novus300.yaml` uses `/novus300bus/novus300-airflow.svg`. The SVG now lives in `custom_components/novus300bus/www/`. The integration now depends on `http`.

### Notes
- Writing parameters to the unit is still lightly tested. After updating, restart Home Assistant and update the bridge.

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
