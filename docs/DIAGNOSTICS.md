# Report new hardware with integration diagnostics

[Deutsch](DIAGNOSTICS.de.md)

<a id="xor-beta-20261123b1"></a>

## XOR beta 2026.11.24b1

The separate `beta/xor-read-only` branch supports the checksum-valid alternative
protocol found in the issue #10 recordings. The labels identify **protocol
profiles**, not established hardware/firmware generations:

- **CRC16 - reference installation (TFT ETA0036E29A):** existing integration
  behaviour, including configured write features. Default for existing entries.
- **XOR - issue #10 variant (HW/FW unknown, read-only beta):** no serial writes,
  scheduled time synchronization, parameter requests, fan/select/switch controls
  or optional Tinkerforge output. Even direct write service calls are rejected.

The beta exposes **Selected fan stage (experimental)**,
`sensor.novus300_xor_fan_stage`, a validated-frame counter, the last changed raw data page
(`address:page`, hexadecimal) and an **experimental BCD bus clock**. Its clock
interpretation is not panel-confirmed and is never synchronized automatically.
All observed address/type counts and up to 64 recent raw pages are included in
diagnostics. The stage scale is **1-7**, not the TFT mode codes: 4/5/6 are
**not** boost/away/automatic. Values 1/2 follow the old labelled captures and the
new 1-2-1 sequence; 3-7 are inferred from the LED scale and still need validation.
The sensor attributes distinguish `capture_confirmed`, `inferred` and `unmapped`
and retain the raw byte. Other values, including 0, show **unknown**, not an
assumed standby state. This is the selected stage, not measured RPM, power or
proof that the fans are running. Boost is not decoded separately; a displayed 7
does not establish boost mode. Temperatures, bypass and equipment types remain
unmapped. Unknown firmware and fallback component identities are not reported
as detected XOR hardware.

**Writing remains blocked, without an unlock switch.** The observed stage
change involves a handshake and a 16-byte block, not an isolated stage command.
Bus roles, safe arbitration and preservation of the other fields are not
established. Replaying a captured block through a generic TCP converter is not
a verified write implementation, even after the stage display has been checked.

### Install and select the profile

1. Back up Home Assistant and the existing integration files.
2. Open **HACS > Paul Novus 300 RS-485 Bus > three-dot menu > Redownload**.
   Under **Need a different version?**, select **2026.11.24b1**, if listed.
   If the prerelease is not listed, use the manual alternative below.
3. Restart **Home Assistant**, not the ventilation unit. Open **Settings >
   Devices & services > Paul Novus 300 RS-485 Bus > Configure > General and unit
   settings** and set **Hardware / firmware profile > XOR**. Save.
   The same selector is in **Reconfigure > Interface: RS-485 bus** and initial
   setup. A profile change saves only the selection, ignores other edits in that
   submission and reloads the integration; reopen the form for further edits.
4. Keep the existing bridge URL and **9600, 8N1**, TCP Server and transparent
   Transfer Protocol None. The dynamic-address option applies only to CRC16.
   Do not select CRC16 on the XOR unit to try to enable controls.

**Manual alternative:** download the
[beta source ZIP](https://github.com/BenPru/novus300_Rs485/archive/refs/tags/2026.11.24b1.zip).
Move the old `/config/custom_components/novus300bus` folder to a backup location
**outside** `custom_components`. Extract only
`custom_components/novus300bus` from the ZIP into `/config/custom_components/`,
then follow steps 3-4. Do not copy the repository root or overwrite other
integrations. Roll back by reinstalling stable **2026.11.21** (or the backed-up
folder) and restarting HA; restore the backup if configuration recovery is needed.

### Record without sending any command

On the integration's **device page**, under **Diagnostic**, press
**Record 120 seconds (passive)** once. It uses the already-open receive connection
and sends **no commands**, including no register dump. Wait at least 125 seconds,
then download integration diagnostics as described below. An ongoing recording
cannot be overwritten; after downloading it, press again for a new one.

The JSON's `passive_recording` contains UTC timestamps, exact byte order, byte
count and status (`recording`, `complete` or `truncated`; initially `not_started`).
Tiny reads are combined into approximately 100 ms chunks; timestamps identify
each chunk's first read, not individual byte arrival times. Limits are 120 seconds,
1 MiB or 2400 chunks. `complete` with zero bytes means no data arrived, **not**
successful communication. Recordings are in memory until replaced or reloaded;
download before reloading/restarting HA.

First collect an unchanged baseline. For LED panel tests, use the sequences
below. Note exact action times with UTC offset, LED count and the HA stage;
the LED panel has no temperature or clock display. Read the actual unit,
panel, hardware and software/BUS versions from accessible info pages or labels;
photos/screenshots with serial numbers masked are useful. No powered covers,
frost/heater changes, resets, ventilation reboot or dump requests are needed.
**Review privacy before uploading:** see section 4 below.

### Validate all seven LED stages

Use the physical panel only, and only stages appropriate for normal operation.
Start from stage 1 if appropriate. Start a passive recording, then select stage 2
at +20 s, stage 3 at +50 s, and return to the original normal stage at +80 s.
Record every actual button press, LED count and HA reading after it has settled.
Wait until +125 s and download **before** starting the next recording.

If higher stages are appropriate, make another recording covering 4/5/6/7:
reach stage 4 at +20 s, 5 at +40 s, 6 at +60 s, 7 at +80 s, and restore the
original normal stage at +100 s. Record intermediate stages when multiple +/-
presses are needed. Do not select unusually high stages just for this test.
If the display is wrong, attach the same raw recording; it contains the bytes
needed to correct the mapping. Name files `stages-1-3.json` and `stages-4-7.json`.

For each action report: `local time + UTC offset | button/number of presses |
LED count | HA stage | raw_value | mapping_status`. Also note any automation,
boost or external input that might override the selection. Do not change
automations or wiring merely for the recording.

### Passive dumps for the other LED buttons

These are **receive-only captures**, not active register-dump requests. Use
a separate 120-second recording for each function, download at +125 s, and
note the original stage, mode LEDs and exact action time. Press the physical
button at approximately +20 s and observe the HA stage and all LEDs afterwards.
Restore the original mode during the recording only using its normal, known
operation; note how and when. If unsure, capture the next normal use instead.

| Button | Meaning in the Novus manual | Useful recording |
|---|---|---|
| + / - | Seven selected ventilation stages | Stage tests above |
| Boost ventilation | Timed stage 7; factory duration 15 minutes | `boost.json`: record activation during normal use and distinguish boost LED from stage LEDs; do not assume manual stage 7 means boost |
| Supply and extract | Balanced two-fan operation | `balanced.json`, including return from another permitted mode |
| Extract only | Supply fan disabled | `extract-only.json` **only if this mode is permitted for the installation** |
| Supply only | Extract fan disabled | `supply-only.json` **only if permitted for the installation** |
| Filter/reset | Resets the filter runtime counter | `filter-reset.json` **only during an actually due filter service**, never reset solely for diagnosis |

**Fireplace warning:** the manual requires extract-only operation to be disabled
when operating with a fireplace. Do not unlock it, bypass interlocks, or test
one-fan modes without knowing that they are permitted. Do not test hidden
combinations for fireplace configuration, bypass thresholds or imbalance.
No standby, mains restart, frost/heater changes or active dump is required.
Boost expiry needs a separate capture around its normal end if investigated;
the two-minute recording does not cover the factory 15-minute duration.

Diagnostics from another compatible ventilation unit or additional equipment
(for example an EWT/earth heat exchanger damper) can help identify unknown bus
registers. A report does not mean that the hardware is already supported.
Collect data through the existing integration connection; no extra TCP client,
bus wiring changes or separate capture tool is needed.

## 1. Describe the hardware

Record the exact ventilation-unit model, panel model and firmware versions
(where available), Home Assistant version and integration version. Include the
connection type and bridge version, if known.

List the equipment **physically installed**, such as bypass, EWT damper,
defroster, brine defroster and reheater, with model/type where available.
Separately describe what the panel and integration report as installed; do not
change installation flags to make them match. Note the missing or unexpected
values and the values actually shown on the panel.

## 2. Collect a baseline and one action at a time

1. With the integration connected and receiving data, download a baseline
   diagnostic file using the procedure below.
2. Record the date, exact local time **with timezone/UTC offset**, current mode
   and original value of the setting you will inspect.
3. If safe, open the relevant existing panel menu without saving changes.
   Record the time and displayed values, then download diagnostics immediately.
   Some values are sent only when a menu is saved or the unit starts; opening a
   menu is not guaranteed to expose them.
4. Only if appropriate for normal operation, change **one known, safe setting**
   on the physical panel. Record the exact action, time and before/after values,
   then download diagnostics immediately. Clearly distinguish panel actions
   from actions in Home Assistant or automations.
5. Restore the original setting if changed, verify it on the panel, record the
   time and download diagnostics again. Give each downloaded file a distinct
   name and associate it with the corresponding action.

A passive report without any changes is useful too. Do not change frost
protection, heater types, installation flags or unknown service parameters for
a recording. Do not power-cycle the unit just to collect missing registers.
Do not restart Home Assistant or reload the integration between an action and
its download.

Example action log (use your actual date, times, timezone and readings):

| Time including UTC offset | Action and location | Before | After | File |
|---|---|---|---|---|
| YYYY-MM-DD 14:01:00+01:00 | Downloaded baseline, no changes | ... | Unchanged | baseline.json |
| YYYY-MM-DD 14:02:10+01:00 | Opened EWT menu on panel, no save | Panel displayed ... | Unchanged | ewt-menu.json |

For fan-stage investigations, distinguish **switching to another stage** from
**pressing the already-active stage again**. Record panel stage, HA percentage,
original configured stage percentage and any active automations. A repeated bus
value alone does not prove that a button was pressed.

## 3. Download integration diagnostics

In Home Assistant, open **Settings > Devices & services > Integrations**,
find **Paul Novus 300 RS-485 Bus**, then use the relevant integration entry's
three-dot menu and select **Download diagnostics**. Depending on the frontend
version, open the integration details first to reach the entry menu.

The downloaded JSON includes decoded values, the known parameter block,
message/status history and `raw_bus_log.chunks`. The raw log preserves received
bytes **before parsing**, including values the integration does not yet
understand. Each chunk has a UTC `time` and hexadecimal `hex` bytes.

The raw log is a rolling, in-memory buffer of **3000 received chunks**, not a
fixed number of minutes. A chunk is a serial read block, not necessarily a
complete protocol frame. Older chunks are overwritten; restarting/reloading
the integration clears the buffer. Download promptly after each action. An
empty log or missing value is not proof that the hardware has no such value.

## 4. Review privacy before uploading

**Diagnostics are currently not anonymized by this integration.** They include
configuration/options, internal addresses or hostnames, and device identifiers.
The raw bytes may also contain identifiers. Home Assistant's diagnostic
wrapper can contain additional system information.

Review a **copy** of every file before posting publicly. Remove credentials,
tokens, personal information and identifying addresses/serial numbers wherever
present, including raw data if necessary. Keep timestamps, firmware versions
and relevant register bytes intact where possible; tell us which portions were
redacted. If you cannot confidently sanitize a file, do not upload it publicly.
Never attach `.storage/auth`, `secrets.yaml` or a full Home Assistant backup.

## 5. Open a GitHub issue

Use the [New hardware / diagnostic data issue form](https://github.com/BenPru/novus300_Rs485/issues/new?template=new-hardware.yml).
You can write in English or German.

Include the hardware/versions, physical equipment, observed problem or unknown
value and action log. Drag the reviewed diagnostic JSON files into the
diagnostics field and wait until the uploads finish; a ZIP is also suitable.
Do not paste thousands of raw log lines into the issue.

Submit the issue only after checking the preview and attachments. Diagnostics
help compare known and unknown registers; they do not by themselves establish
a safe write command or prove which physical device sent a frame.
