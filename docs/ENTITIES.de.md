# Entitäten und Attribute

English: [ENTITIES.md](ENTITIES.md)

Alle Entitäten gehören zum Gerät **Paul Novus 300** (Modell Novus 300
(FOCUS250), Busversion 1.7.1). Ihre `unique_id` beginnt mit `novus300bus_`,
gefolgt vom unten genannten Schlüssel.

## Übersicht

| Entity-ID | Plattform | Name | Kategorie | Bei ausgeschalteter Anlage verfügbar |
| --- | --- | --- | --- | --- |
| `switch.novus300_power` | switch | Betriebsstatus | – | ja |
| `switch.novus300_bypass` | switch | Bypass geöffnet | – | nein |
| `fan.novus300` | fan | Lüftung | – | nein |
| `select.novus300_ventilation_mode` | select | Lüftungsmodus | – | nein |
| `button.novus300_boost` | button | Stoßlüftung | – | nein |
| `button.novus300_filter_reset` | button | Filterlaufzeit zurücksetzen | – | nein |
| `sensor.novus300_supply_air_temperature` | sensor | Zuluft Temperatur Räume | – | nein |
| `sensor.novus300_outdoor_air_temperature` | sensor | Außenluft Temperatur | – | nein |
| `sensor.novus300_extract_air_temperature` | sensor | Abluft Temperatur Räume | – | nein |
| `sensor.novus300_exhaust_air_temperature` | sensor | Fortluft Temperatur | – | nein |
| `sensor.novus300_message` | sensor | Meldung | Diagnose | ja |
| `sensor.novus300_operating_time` | sensor | Gesamtbetriebszeit | Diagnose | ja |
| `sensor.novus300_fan_operating_time` | sensor | Lüfterbetriebszeit | Diagnose | ja |
| `sensor.novus300_filter_time_remaining` | sensor | Filter Restlaufzeit | Diagnose | ja |
| `sensor.novus300_register_44` | sensor | Register 0x44 (Rohwert, unbekannt) | Diagnose, standardmäßig deaktiviert | ja |
| `sensor.novus300_register_62` | sensor | Register 0x62 (Rohwert, unbekannt) | Diagnose, standardmäßig deaktiviert | ja |

Eine Entität ist außerdem nicht verfügbar, bis ihr Register auf dem Bus
gesehen wurde (die Anlage sendet manche Register nur gelegentlich, z. B. beim
Start). „Anlage aus“ bedeutet immer den von der Anlage gemeldeten
Betriebsstatus „stopped“.

## Schalter

### `switch.novus300_power` – Betriebsstatus

Schaltet die Anlage über den Bus ein und aus (die Panel-Frames für Register
0x07) und zeigt den Betriebsstatus.

| Zustand | Bedeutung |
| --- | --- |
| `on` | Betriebsstatus `running` oder `starting` |
| `off` | Betriebsstatus `stopped` |
| `unknown` | Betriebsstatus nicht erkannt |

| Attribut | Beschreibung |
| --- | --- |
| `run_state` | `stopped` (Rohwert 0), `running` (1), `starting` (3) oder `unknown` |
| `serial_panel`, `serial_fan_slave`, `serial_defroster` | Seriennummern der angeschlossenen Komponenten (sobald am Bus gesehen) |
| `raw_value` | Rohwert des Betriebsstatus-Registers |

Das Icon folgt dem Betriebsstatus (Stopp, Play, Fortschrittsuhr, Hilfe). Nach
dem Senden wartet die Integration bis zu 5 s auf den neuen Betriebsstatus und
versucht es bis zu dreimal, bevor sie einen Fehler meldet. Die Anlage nimmt
„Ein“ erst etwa 30 Sekunden nach „Aus“ an, weil das Panel zuerst eine Meldung
zeigt. Voraussetzung ist die `socket://`-Bridge mit `--allow-command-frames`.

### `switch.novus300_bypass` – Bypass geöffnet

Nur lesbar: `turn_on` und `turn_off` lösen einen Fehler aus, bis das Öffnen und
Schließen des Bypasses bekannt ist. `on` bedeutet, der Bypass ist offen oder in
Bewegung.

| Attribut | Beschreibung |
| --- | --- |
| `air_path` | `heat_recovery`, `bypass`, `transition` (beide Flags gesetzt) oder `unknown` |
| `raw_value` | Statuswort der Anlage (Flags 0x08 Wärmerückgewinnung, 0x20 Bypass) |

Hinweis: Der Bypass-Stellmotor der Anlage des Autors ist defekt, daher konnten
die Zustände `bypass` und `transition` nie beobachtet oder mitgeschnitten
werden.

## Lüfter

### `fan.novus300` – Lüftung

Immer vorhanden. Zeigt den Prozentwert der aktiven Stufe (z. B. 60 % in Stufe 2)
und steuert die Lüftung über einen Soll-Prozentwert.

* Ohne 0-10 V: Ein Soll-Wert unter Stufe 2 wählt Stufe 1 und setzt deren
  Prozentwert vorübergehend auf den Soll-Wert, darüber entsprechend Stufe 3;
  die ursprünglichen Prozentwerte werden beim Verlassen der Stufe
  wiederhergestellt.
* Mit 0-10 V (Option **0-10 V: Lüftersteuerung aktivieren**): Ein Soll-Wert
  über 0 wählt Automatik und schreibt den Wert über Tinkerforge.
* 1–16 % werden auf 17 % angehoben. 0 % und `turn_off` wählen den Modus
  Abwesend; der Fan zeigt dann 0 % / aus.
* Nicht verfügbar, solange die Anlage aus ist.

| Attribut | Beschreibung |
| --- | --- |
| `ventilation_mode` | `automatic`, `level_1`, `level_2`, `level_3`, `boost`, `away`, `standby` oder `unknown` |
| `original_levels` | vorübergehend überschriebene Stufen mit ihrem ursprünglichen Prozentwert (`fan_level_1_percentage`, `fan_level_3_percentage`) |
| `bus_setpoint` | Rohwert der Lüfteransteuerung der Anlage (Register 0x55) in % |
| `away_minutes_per_hour` | nur im Modus Abwesend: Lüftungsminuten pro Stunde |
| `run_state` | nur mit 0-10 V: Betriebsstatus der Anlage |
| `analog_percentage` | nur mit 0-10 V: Wert des Analogausgangs in % |
| `preset_modes`, `preset_mode` | nur mit 0-10 V im Automatikmodus: `Automatik` / `Manuell`, abgeleitet von der Hilfsentität (Standard `input_boolean.luftung_automatik`) |

## Auswahl und Schaltflächen

### `select.novus300_ventilation_mode` – Lüftungsmodus

Optionen: `automatic`, `level_1`, `level_2`, `level_3`, `away`, `boost`. Die
aktuelle Option ist der von der Anlage gemeldete Modus. Standby nimmt die
Anlage nicht an. Nicht verfügbar, solange die Anlage aus ist.

### `button.novus300_boost` – Stoßlüftung

Wählt den Stoßlüftungsmodus und kehrt nach der eingestellten Stoßlüftungsdauer
zum vorherigen Modus zurück. Nicht verfügbar, solange die Anlage aus ist.

### `button.novus300_filter_reset` – Filterlaufzeit zurücksetzen

Startet die Filterlaufzeit neu (schreibt das Filterintervall in die Anlage).
Bei ausgeschalteter Anlage nicht verfügbar.

## Sensoren

### Temperaturen

`supply_air_temperature`, `outdoor_air_temperature`, `extract_air_temperature`
und `exhaust_air_temperature`: °C, Geräteklasse Temperatur, Statusklasse
Messwert, keine weiteren Attribute.

### `sensor.novus300_message` – Meldung

Diagnose. Der Zustand ist entweder ein Statuswechsel oder die eigene Meldung
der Anlage.

* **Übergang** (nur solange er andauert; stabile Zustände zeigen die
  Schalter): „Anlage fährt hoch“, „Anlagenstatus unbekannt (Wert n)“,
  „Bypass in Bewegung“, „Luftweg unbekannt“ (nur im Betrieb) sowie
  „Anlage fährt runter“ für 45 s nach dem Ausschalten (die Anlage meldet keine
  Abschaltphase). Bei ausgeschalteter Anlage steht wieder die letzte echte
  Meldung.
* **Meldung der Anlage** sonst: „Keine Meldung“, „Filter wechseln“,
  „Fehler am Eingang“, „Fehler Bypass“ oder „Meldung <Code>“.

| Attribut | Beschreibung |
| --- | --- |
| `code` | Code der aktuellen Meldung der Anlage (0 = keine, 0x41 = 65 Filter wechseln, 0x83 = 131 Fehler am Eingang, 0x89 = 137 Fehler Bypass) |
| `occurred_at` | Zeitpunkt der angezeigten Meldung bzw. des Statuswechsels (ISO-Zeit); das „zuletzt aktualisiert“ von Home Assistant lässt sich nicht setzen |
| `previous_message`, `previous_message_2`, `previous_message_3` | die letzten drei eigenen Meldungen der Anlage als Text: Zeit, Code, Meldung, übersetztes Detail |
| `observed` | von Home Assistant gesehene Meldungswechsel (Zeit, Meldung), neueste zuerst, bis zu 10 |
| `status_events` | die letzten 10 Wechsel von Betriebsstatus oder Luftweg als Text mit Zeit, neueste zuerst |

Die Anlage speichert ihre letzten drei Meldungen und sendet sie nur beim Start;
die Integration behält sie.

### Zähler (Diagnose)

| Entität | Einheit | Beschreibung |
| --- | --- | --- |
| `operating_time` | h | Gesamtbetriebszeit |
| `fan_operating_time` | h | Lüfterbetriebszeit |
| `filter_time_remaining` | d | Filter-Restlaufzeit (0 = Filter wechseln) |

Sie werden mit dem kompletten Registerdump der Anlage gesendet; der letzte
bekannte Wert wird nach einem Neustart wiederhergestellt, bis ein neuer kommt.

### Rohregister (Diagnose, standardmäßig deaktiviert)

`register_44` und `register_62` zeigen die noch nicht identifizierten Register
0x44 und 0x62 als Rohwerte.

## Dienste

| Dienst | Beschreibung |
| --- | --- |
| `novus300bus.sync_clock` | Datum und Uhrzeit der Anlage auf die lokale Zeit von Home Assistant setzen und die Abweichung prüfen |
| `novus300bus.reset_filter` | Filterlaufzeit neu starten (wie die Schaltfläche) |

## Optionen

Serielles Gerät / Bridge-URL, Baudrate, Parität, **Uhrzeit täglich
synchronisieren** (03:00), Lüftungsstufen 1–3 in % (17 % ≤ Stufe 1 < Stufe 2 <
Stufe 3 ≤ 100 %), Stoßlüftungsdauer, Abwesend-Lüftungszeit (Minuten pro
Stunde), Filterintervall (30–180 d) und die 0-10-V-Optionen (aktivieren,
Tinkerforge-Host, Port und UID, Hilfsentität für den Automatikmodus). Stufen,
Dauern und Filterintervall werden beim Speichern der Optionen in die Anlage
geschrieben.
