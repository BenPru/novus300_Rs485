# Paul Novus 300 - RS-485

This component has been created to be used with Home Assistant. This is a custom component for home assistant.

Home Assistant HACS component to readout values from a Paul Novus 300 ventilation system.

It allows read the temperatures, the bypass/heat recovery mode and the defroster state key from the Paul Novus 300 air ventilation.
Its necessary to connect the ventilation system bus network, to a usb rs-485 stick. So an additional hardware is needed.

The `Novus300-RS485` integration lets you read out values from a ventilation system. It is used by manufacturers and model such as:

- Paul Novus 300

## Configuration

To enable this component, add the following lines to your `configuration.yaml` file:

```
- platform: novus300bus
  serial_port: /dev/ttyUSB0
  # optional:
  # baudrate: 9600
  # name: ...
```

Todo:

- Remove hardcoded sensors and read them as config
- Add filter time as sensor
- Add project to hacs
- Add dokumentation how to connect USB RS-485
