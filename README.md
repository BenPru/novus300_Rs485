# Paul Novus 300 RS-485 Bus

[![HACS validation](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml/badge.svg)](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml)
[![Hassfest](https://github.com/BenPru/novus300_Rs485/actions/workflows/hassfest.yml/badge.svg)](https://github.com/BenPru/novus300_Rs485/actions/workflows/hassfest.yml)

[Deutsche Dokumentation](README.de.md)

Home Assistant integration for passively reading a Paul Novus 300 ventilation
unit through its RS-485 bus. It exposes temperatures, operating state, air
path, filter and operating times, and the ventilation level selected at the
unit's panel.

An existing Tinkerforge Industrial Analog Out V2 can optionally be exposed as
`fan.novus300` to control the unit's external 0-10 V input. This output is
controllable only while the unit panel is in **Automatic** mode. The RS-485
connection is always read-only.

## Requirements

- Home Assistant with HACS
- Paul Novus 300 with an accessible RS-485 service/bus connection
- A suitable RS-485 adapter, or a separate serial-to-TCP reader
- Optional for `fan.novus300`: a Tinkerforge Master/Bricklet setup with an
  **Industrial Analog Out V2**, Brick Daemon, and network access

> [!WARNING]
> Work on the ventilation unit and its bus wiring is at your own risk. Switch
> off the unit before connecting or altering any wiring. Always follow the
> connection pinout, permitted cable length, and termination guidance in the
> Paul documentation for the specific unit. This integration never transmits
> RS-485 frames and must not be extended to write to the bus.

## Install with HACS

1. Open **HACS → Integrations**.
2. Select the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/BenPru/novus300_Rs485` with category
   **Integration**.
4. Download the integration and restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and select
   **Paul Novus 300 RS-485 Bus**.

The RS-485 integration is configured entirely in the UI; YAML is not needed.

## Connect and configure RS-485

### Direct USB-to-RS-485 adapter

1. Use an adapter whose UART supports **MARK parity** at 9600 baud. In Home
   Assistant, use its stable `/dev/serial/by-id/...` path instead of
   `/dev/ttyUSB0`.
2. With the unit powered off, connect the adapter to the RS-485 interface
   specified for your ventilation unit:
   - adapter `A`/`D+` to unit `A`/`D+`;
   - adapter `B`/`D-` to unit `B`/`D-`;
   - connect signal ground only where the Paul wiring diagram specifies it.
3. Do not feed bus power or add termination resistors unless the unit
   documentation specifically requires this.
4. In the integration, select the `/dev/serial/by-id/...` path, **9600** baud,
   and **mark** parity.

If no readings arrive, first verify A/B against the unit documentation.
Wire colours are not standardized and must not be used to identify A and B.

### Serial over TCP

The RS-485 interface can instead be read by a separate computer and made
available as a TCP stream. This keeps the physical bus connection independent
of the Home Assistant host.

- The serial reader handles 9600 baud and MARK parity on its local UART.
- Enter `socket://<host>:<port>` in the integration, for example
  `socket://10.0.17.45:9700`.
- Select **none** parity in the integration because the serial reader already
  processed the parity.

The TCP reader must either accept only one client or serialize access. A
second concurrent connection can replace the Home Assistant connection.

## Optional Tinkerforge 0-10 V fan control

RS-485 monitoring works without Tinkerforge. This section is only required
for the additional `fan.novus300` entity.

### Prepare Tinkerforge

1. Connect the **Industrial Analog Out V2** to the Tinkerforge stack and find
   its UID in Brick Viewer.
2. Run Brick Daemon on the host/gateway that reaches the Tinkerforge stack.
   Its default port is `4223`.
3. Allow the Home Assistant host to reach `<tinkerforge-host>:4223`.
4. In the integration options, enable **0-10 V fan control** and enter the
   host, port, and UID.

### Connect the 0-10 V output

1. Switch off the ventilation unit and Tinkerforge hardware before wiring.
2. Connect `OUT` on the Industrial Analog Out V2 to the external **0-10 V
   control input** named in the Paul documentation.
3. Connect the analog output `GND` to the corresponding control-input signal
   ground. Never connect it to RS-485 A or B.
4. Verify allowed voltages, ground reference, and any required galvanic
   isolation in the unit documentation before powering up.
5. Test at 0% first, then use low values before increasing the output.

`fan.novus300` reads the existing analog voltage at startup. Writing is only
allowed while the unit panel is in **Automatic** mode. At panel levels 1–3,
boost, away, or standby, the entity is intentionally read-only.

When the configured automatic-mode helper exists, `fan.novus300` additionally
offers the **Automatic** and **Manual** presets. They toggle only that helper
and are also available only in panel Automatic mode. The
`button.novus300_boost` button is subject to the same restriction; it applies
the configured **Panel boost** value for the configured duration and then
restores the prior output.

## Panel levels and values

The unit broadcasts a fixed panel level but not its percentage. The integration
therefore maps these configurable values:

| Panel mode | Default | Option |
|---|---:|---|
| Level 1 | 35% | Panel level 1 |
| Level 2 | 60% | Panel level 2 |
| Level 3 | 90% | Panel level 3 |
| Boost ventilation | 75% | Panel boost |
| Away | 15% | Panel away |

These are numeric inputs from 0 to 100%. Turning on `fan.novus300` uses the
configured **Panel level 2** value; the boost button uses **Panel boost**.
Standby has no mapped percentage and shows the raw bus value instead.

## Entities

- supply, outdoor, extract, and exhaust air temperatures
- `sensor.novus300_ventilation_mode` for standby, automatic, levels 1–3,
  boost, and away
- `sensor.novus300_fan_setpoint` for the fan control value
- run state, air path, and bypass state
- operating time, fan operating time, filter interval, and remaining filter
  time when the controller broadcasts its complete register dump
- optional `fan.novus300` and `button.novus300_boost`

Not every register is sent continuously. After a Home Assistant restart, you
may need to change the panel level once for the current mode to be broadcast
again.

## Troubleshooting

| Symptom | Check |
|---|---|
| No RS-485 readings | Verify the stable `/dev/serial/by-id/...` path, 9600 baud, MARK parity, and A/B wiring. |
| TCP connection drops | Ensure only one client is connected to the serial TCP reader. |
| `fan.novus300` cannot be controlled | Set the panel to Automatic and verify Tinkerforge host, port, UID, and Brick Daemon. |
| Fixed panel level has the wrong percentage | Adjust the corresponding panel-level option. |
| Filter or operating time is missing | Wait for the unit's complete register dump; these registers are not broadcast continuously. |

## Passive bus capture preparation

The receive-only capture utility and its later operating procedure are in
[docs/full-duplex-capture.md](docs/full-duplex-capture.md). It is installed
but inactive on the bridge host and must only be started for a planned,
documented recording session.

## HACS

This repository is ready to be added as a custom HACS repository. It includes
one integration, a root `hacs.json`, the required integration manifest, a
brand icon, a GPL-3.0-only license, and HACS and Hassfest validation workflows.

The repository is already listed alphabetically in the official
[hacs/default integration list](https://github.com/hacs/default/blob/master/integration).
Release [v2026.11.02.12](https://github.com/BenPru/novus300_Rs485/releases/tag/v2026.11.02.12)
is available after successful HACS and Hassfest validation. HACS will discover
the release during its next scheduled scan; no additional catalog pull request
is necessary.

## License

This project is licensed under [GPL-3.0-only](LICENSE).
