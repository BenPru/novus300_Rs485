# Paul Novus 300 - RS-485

[![Validate with HACS validation](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml/badge.svg)](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml)

This component has been created to be used with Home Assistant. This is a custom component for home assistant.

Home Assistant HACS component to readout values from a Paul Novus 300 ventilation system.

It allows read the temperatures, the bypass/heat recovery mode and the defroster state key from the Paul Novus 300 air ventilation.
Its necessary to connect the ventilation system bus network, to a usb rs-485 stick. So an additional hardware is needed.

The `Novus300-RS485` integration lets you read out values from a ventilation system. It is used by manufacturers and model such as:

- Paul Novus 300

## Configuration

Install the repository through HACS, then add **Paul Novus 300 RS-485 Bus**
from **Settings → Devices & services → Add integration**.

For a directly attached adapter, select its stable `/dev/serial/by-id/...` path
and choose `mark` parity. For a serial-over-TCP bridge, enter
`socket://<host>:<port>` and use `none` parity. The integration only reads the
bus and never sends bytes to the ventilation system.

**Note:**
Not all data received by the this controller is understood by now as the protocol is not publicly documented.  

## Sensors

The integration creates entities for:

- supply, outdoor, extract and exhaust air temperatures
- bypass status
- fan setpoint, including automatically/external controlled operation
- raw run state and status word for diagnostics
- total and fan operating time, plus filter interval and remaining filter time
  when the controller broadcasts its restart register dump

## Protocol notes

The bus uses 9600 baud with a ninth marker bit. A PC UART can receive a
directly attached bus with mark parity. For a TCP bridge the parity has already
been handled by the remote serial reader, so use `none` in the integration.

Not every register is emitted continuously. In particular, filter and operating
time counters are sent as part of the controller's full register dump after a
restart.
