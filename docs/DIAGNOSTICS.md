# Report new hardware with integration diagnostics

[Deutsch](DIAGNOSTICS.de.md)

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
