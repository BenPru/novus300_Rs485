# Paul Novus 300 - RS-485

This component has been created to be used with Home Assistant.

The `Novus300-RS485` integration lets you read out values from a ventilation system. It is used by manufacturers and model such as:

- Paul Novus 300

Its necessary to connect the ventilation system bus network, to a usb rs-485 stick. So an additional hardware is needed.

## Configuration

To enable this component, add the following lines to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
fan:
  - platform: novus300
```
