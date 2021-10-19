# Paul Novus 300 - RS-485

[![Validate with HACS validation](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml/badge.svg)](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml)

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

**Note:**
Not all data received by the this controller is understood by now as the protocol is not publicly documented.  

## Sensor
This sensor allows you to monitor the following status values:
- novus300_temp_house_air_out
- novus300_temp_indoor
- novus300_temp_indoor_in
- novus300_temp_outdoor

TODO Sensors:
- novus300_heat_recovery
- Filter days

## Todo

- Remove hardcoded sensors and read them as config
- Add filter time as sensor
- Add project to hacs
- Add dokumentation how to connect USB RS-485
