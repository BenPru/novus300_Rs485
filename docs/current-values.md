# Paul Novus 300: aktuelle Buswerte

Gemessen am 2. November 2026 um 16:57 Uhr direkt am passiv gelesenen
RS-485-Bus.

| Wert | Aktueller Wert | HA-Entität |
|---|---:|---|
| Zuluft Temperatur Räume | 22,5 °C | `sensor.novus300_supply_air_temperature` |
| Außenluft Temperatur | 10,0 °C | `sensor.novus300_outdoor_air_temperature` |
| Abluft Temperatur Räume | 22,5 °C | `sensor.novus300_extract_air_temperature` |
| Fortluft Temperatur | 13,5 °C | `sensor.novus300_exhaust_air_temperature` |
| Bypass | Zu | `binary_sensor.novus300_bypass` |
| Luftweg | Wärmerückgewinnung | `sensor.novus300_air_path` |
| Lüfteransteuerung | Standby: 0 % | `sensor.novus300_fan_setpoint` |
| Lüftungsstufe | Abwesend (`raw_value: 5`) | `sensor.novus300_ventilation_mode` |
| Betriebsstatus | Läuft (`raw_value: 1`) | `sensor.novus300_run_state` |
| Luftweg-Rohwert | `13` (`0x0D`) | Attribut `raw_value` von `sensor.novus300_air_path` |

Die Sensoren für Gesamtbetriebszeit, Lüfterbetriebszeit, Filterintervall und
Filter-Restlaufzeit werden erst sichtbar, wenn die Steuerung ihren vollständigen
Register-Dump nach einem Neustart sendet. Filterintervall und Filter-Restlaufzeit
werden in Tagen angezeigt; die Gesamtbetriebszeit wird in Stunden angezeigt.
