# Changelog

Versionierung als Datum: `JAHR.MONAT.TAG`. English: [CHANGELOG.md](CHANGELOG.md)

## 2026.11.17

### Neu
- **Modus per RS-485 senden:** `select.novus300_ventilation_mode` setzt Automatik, Stufe 1–3, Abwesend und Stoßlüftung direkt auf dem Bus.
- **`button.novus300_boost`** löst die Stufe Stoßlüftung auf dem Bus aus (nicht mehr per 0-10 V).
- **Dienst `novus300bus.sync_clock`**, um die Uhrzeit-Synchronisation manuell auszulösen.
- **Uhrzeit täglich synchronisieren:** neue Option (Standard: an), Sync täglich um 03:00 mit Prüfung der Abweichung.
- **Anlageneinstellungen per Bus:** Lüfterstufen 1–3 in % sowie Dauer Stoßlüftung und Abwesend werden beim Speichern der Optionen in die Anlage geschrieben. Angezeigt werden die zuletzt auf dem Bus gesehenen Werte.
- **Serielle Bridge (`tools/`):** Schreibzugriff nur für geprüfte Frames (Modus, Datum/Uhrzeit, Einstellungen) mit CRC- und Wertebereichsprüfung; optionales systemd-Beispiel.
- Dokumentation (EN/DE) und Tests für Uhr-, Datums- und Einstellungsframes.

### Geändert
- Options-Dialog neu geordnet: Serielle Verbindung, tägliche Synchronisation, Stufen in %, Dauer Stoßlüftung, Abwesend (min/h), danach die 0-10-V-Einstellungen; Stufen sind normale Zahlenfelder (0–100 %), Zeiten Auswahllisten, Bezeichnungen vereinheitlicht.
- Abwesend ist jetzt „Lüftungszeit pro Stunde“ (15 / 30 / 45 min/h laut Anleitung) statt einer Dauer.

- `sensor.novus300_fan_setpoint` zeigt den Stufen-% auch bei Stoßlüftung (Stufe 3) und Abwesend (Stufe 1, Attribut `away_minutes_per_hour`). Auf dem Bus ist es nur das gemessene 0-10-V-Steuersignal, nicht die echte Drehzahl.

### Entfernt
- Prozentwerte für Stoßlüftung und Abwesend.
- `sensor.novus300_clock` und `sensor.novus300_clock_drift`.
- `sensor.novus300_ventilation_mode` (ersetzt durch `select.novus300_ventilation_mode`).

### Behoben
- `fan.py`: Callback-Fehler beim Zustandswechsel.

### Hinweise
- Die Anlage lässt sich nicht auslesen; die Wirkung geschriebener Einstellungen wurde nur mit unveränderten Werten geprüft.
- Das Bedienteil zeigt nach einem Busbefehl evtl. weiter den alten Modus an.
- Wer den Sensor im Dashboard nutzt, muss auf das Select umstellen.

## 2026.11.2

- Erstes HACS-fähiges Release: RS-485-Anbindung des Paul Novus 300, deutsche und englische Einrichtungsdokumentation, optionale Tinkerforge-Hinweise, HACS-Icon, GPL-3.0-only und Validierungs-Workflows.
