# Paul Novus 300: aktuelle Buswerte

Gemessen am 2. November 2026 direkt am passiv gelesenen RS-485-Bus.

| Wert | Aktueller Wert | HA-Entität |
|---|---:|---|
| Zuluft Temperatur Räume | 22,5 °C | `sensor.novus300_supply_air_temperature` |
| Außenluft Temperatur | 10,0 °C | `sensor.novus300_outdoor_air_temperature` |
| Abluft Temperatur Räume | 23,0 °C | `sensor.novus300_extract_air_temperature` |
| Fortluft Temperatur | 14,0 °C | `sensor.novus300_exhaust_air_temperature` |
| Bypass | geschlossen | `binary_sensor.novus300_bypass` |
| Luftweg | Wärmerückgewinnung | `sensor.novus300_air_path` |
| Lüfter-Sollwert | 39,9 % | `sensor.novus300_fan_setpoint` |
| Betriebsstatus | läuft | `sensor.novus300_run_state` |
| Betriebsstatus Rohwert | `1` | `sensor.novus300_run_state_raw` |
| Statuswort | `13` (`0x0D`) | `sensor.novus300_status_word` |

Die Sensoren für Gesamtbetriebszeit, Lüfterbetriebszeit, Filterintervall und
Filter-Restlaufzeit werden erst sichtbar, wenn die Steuerung ihren vollständigen
Register-Dump nach einem Neustart sendet.
