# Changelog

Versionierung als Datum: `JAHR.MONAT.TAG`. English: [CHANGELOG.md](CHANGELOG.md)

## 2026.11.17

### Neu
- **Geräteinfo:** Modell Novus 300 (FOCUS250), Busversion 1.7.1; Bedienteil, Lüfter-Slave und Defroster als Untergeräte „Paul Novus 300 …“ mit Softwareversion (ETA0036E29A, SWZ0025B26A, ST00064E24A), gelesen aus der Start-Meldung der Anlage; bekannte Werte dienen als Vorgabe.
- **`sensor.novus300_message`:** aktuelle Meldung der Anlage (z. B. „Filter wechseln“, Code 0x41 in Register 0x09) mit Icon; Attribute `previous_message`, `previous_message_2`, `previous_message_3` enthalten die letzten drei Meldungen der Anlage als lesbaren Text (Zeit, Code, Meldung, übersetztes Detail); `occurred_at` und der neue `sensor.novus300_message_time` zeigen, wann die letzte Meldung auftrat (HAs eigenes „Letzte Aktualisierung“ lässt sich nicht setzen); Meldungs-Icon (Register 0x0A–0x0C, 0x88–0x8D, von der Anlage beim Start gesendet und von der Integration gespeichert); `observed` listet die von Home Assistant gesehenen Wechsel.
- **Diagnose-Rohwertsensoren** (standardmäßig deaktiviert) für die noch unbekannten Register 0x44 und 0x62.
- **Anlage aus:** `fan.novus300` zeigt aus (0 %, Attribut `run_state`), solange die Anlage "stopped" meldet; Temperaturen, Lüfteransteuerung, Luftweg und Bypass sind dann nicht verfügbar statt veraltet.
- **Filterlaufzeit zurücksetzen:** `button.novus300_filter_reset` und Dienst `novus300bus.reset_filter`.
- **Filterintervall ist jetzt eine Option** (30–180 d), wird in die Anlage geschrieben; `sensor.novus300_filter_interval` entfällt.
- **Modus per RS-485 senden:** `select.novus300_ventilation_mode` setzt Automatik, Stufe 1–3, Abwesend und Stoßlüftung direkt auf dem Bus.
- **`button.novus300_boost`** löst die Stufe Stoßlüftung auf dem Bus aus (nicht mehr per 0-10 V).
- **Dienst `novus300bus.sync_clock`**, um die Uhrzeit-Synchronisation manuell auszulösen.
- **Uhrzeit täglich synchronisieren:** neue Option (Standard: an), Sync täglich um 03:00 mit Prüfung der Abweichung.
- **Anlageneinstellungen per Bus:** Lüfterstufen 1–3 in % sowie Dauer Stoßlüftung und Abwesend werden beim Speichern der Optionen in die Anlage geschrieben. Angezeigt werden die zuletzt auf dem Bus gesehenen Werte.
- **Serielle Bridge (`tools/`):** Schreibzugriff nur für geprüfte Frames (Modus, Datum/Uhrzeit, Einstellungen) mit CRC- und Wertebereichsprüfung; optionales systemd-Beispiel.
- Dokumentation (EN/DE) und Tests für Uhr-, Datums- und Einstellungsframes.

### Geändert
- Lüfterstufen werden wie in der Anlage geprüft (17 % ≤ Stufe 1 < Stufe 2 < Stufe 3 ≤ 100 %); geschriebene Werte bleiben sichtbar, bis die Anlage sie erneut sendet.
- Vom der Anlage gesendete Menüeinstellungen (Lüfterstufen, Stoßlüftung, Abwesend) werden automatisch in die Optionen der Integration übernommen (ohne Neuladen).
- Anlageneinstellungen werden beim Schreiben nicht mehr zwischengespeichert; nur von der Anlage selbst gesendete Werte gelten als gelesen. Der Optionsdialog nennt, welche Werte noch Vorgaben sind. Standard Stoßlüftung 15 min (Werk).
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
