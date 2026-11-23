# Changelog

Versionierung als Datum: `JAHR.MONAT.TAG`. English: [CHANGELOG.md](CHANGELOG.md)

## 2026.11.23b1 (Beta)

### Highlights
- **Hardware-/Firmwareprofile:** bisherige CRC16-Referenz und XOR-Variante aus Ticket #10.
- **XOR strikt nur lesend:** geprüfte Telegramme, Rohseitendiagnose und experimentelle Busuhr; keine Steuerung, Uhrzeitsynchronisation, Dumps oder 0-10-V-Schreibzugriffe.
- **120 Sekunden passiv aufzeichnen:** Diagnosetaste, begrenzter Speicher und JSON-Export über die bestehende Verbindung.

### Hinweise
- Separater Zweig `beta/xor-read-only`; Stable 2026.11.21 bleibt unverändert.
- Tatsächliche XOR-Hardware/Firmware und Temperatur-/Stufenzuordnung noch offen; keine Ersatzkennungen oder CRC16-Cachewerte übernommen.
- 80 Offline-Regressionstests und Replay aller vier Mitschnitte aus Ticket #10 bestanden; keine produktiven Busbefehle zum Testen.
- [Installation und Aufzeichnung](docs/DIAGNOSTICS.de.md#xor-beta-20261123b1).

## 2026.11.21

### Highlights
- **Stabilität:** Reload-Schleife, veraltete Bypass-Werte und Socket-Lesefehler behoben.
- **Ausstattung:** Defroster-Präsenz erkennen, ohne den Typ zu raten; Bypass-/Sommerlüftungs-Anzeige angepasst.

### Hinweise
- **Nachträglich ergänzt:** **2026.11.21** erneut installieren und HA neu starten. Bridge ebenfalls aktualisieren/neustarten, falls für diese Version noch nicht erledigt. Kein Lüftungsneustart.
- **Bypass-Einschränkung:** Bedeutung der Panel-Schreibwerte weiter offen; keine direkte Klappensteuerung.
- **65 Regressionstests bestanden.**

## 2026.11.20

### Highlights
- **Automatisierbare Sommerlüftung:** `switch.novus300_summer_ventilation` ersetzt die Aktivierungs-Checkbox in den Optionen. Der Schalter wird nur angeboten, wenn die Anlagenkonfiguration einen vorhandenen Bypass bestätigt.
- **Disbalance-Feineinstellung:** Jede der drei Lüftungsstufen erhält direkt neben dem Prozentwert eine eigene Einstellung von −50 bis +50 % in 0,5-Prozentschritten.
- **Dynamische zweite Dashboard-Ansicht:** „Sensoren“ nutzt ein Basisschema mit separaten Ausstattungsebenen, Temperaturen an den Sensorpositionen und kompakter Darstellung. Beide Ansichten und die unabhängige editierbare Dashboard-Kopie sind jetzt deutsch und englisch dokumentiert.
- **Optionale dynamische Bus-Adressen:** experimentelle, standardmäßig ausgeschaltete Empfangsoption bei Einrichtung und Bus-Neukonfiguration. CRC-Prüfung bleibt aktiv; Schreibziele und Bus-Timing bleiben unverändert.

### Neu
- **Dynamische Empfangsheader:** Aktiviert werden CRC-gültige Frames mit einem anderen ersten Headerbyte als `00/01` akzeptiert, einschließlich nativer `00`-Header. Das zweite Headerbyte war bereits uneingeschränkt. Bestehende Marker-Reparatur bleibt erhalten; unvollständige falsche Header blockieren die Neusynchronisation nicht. Keine automatische Geräte-/Adresszuordnung, keine geänderten Registerlayouts und kein belegter Fix für Issue #10.
- Deutsche/englische Diagnose- und Datenschutzanleitung sowie Fehler-/Hardware-Issue-Formular mit Aktionszeitpunkten und Rohpuffergrenzen. Das Formular verlangt einen Diagnose-Upload als `.json`/`.zip`; leere Issues sind für normale Nutzer deaktiviert. Keine Prüfung des Diagnoseinhalts oder Sperre für CLI/API-Issues. Diagnosen sind nicht anonymisiert; Anhänge vor öffentlichem Upload prüfen.
- Vorzeichenrichtige Auswertung, Codierung, Speicherung und Optionsübernahme der Disbalance-Register `0x31`, `0x32` und `0x33`. Positive Stufen-/Disbalance-Änderungen und Sommerlüftung An/Aus sind mit Panel-Mitschnitten getestet; negative Werte und Grenzen mit erzeugten Frames.
- Sommeraktivierung ändert ausschließlich Bit `0x80` des bekannten Anlagenworts `0x1B`. Parameterschreiben nutzt eine gemeinsame Sperre; Installationsänderungen werden mit dem aktuellen Wort zusammengeführt und erhalten das Sommerflag.
- Sommerbefehle warten bis zu 15 Sekunden auf passende Bus-Rückmeldung. Fehlende Bestätigung und Schreibfehler werden ausdrücklich gemeldet; keine optimistische Zustandsänderung.
- Sommerlüftungs-Kachel und Automationsbeispiele; die bestehende Bypass-Kachel öffnet Details statt einen nicht unterstützten Stellbefehl zu versuchen.
- Lüfterattribute für vorhandenen Bypass, Nachheizung, EWT, Defroster und Sole-Defroster sowie den bekannten Automatik-Untertyp.
- Strukturiertes Attribut `message_table` und zusätzliche, standardmäßig deaktivierte Diagnosesensoren für Hardware-Konfiguration und Systemstatus-Bits.

### Geändert
- **Gruppierte Optionen:** Jede Lüftungsstufe steht mit ihrer Disbalance in einem Abschnitt. Frostschutz (einschließlich minimaler Zulufttemperatur), Nachheizung und Sommerlüftung haben eigene Blöcke mit kürzeren Feldnamen. Sommerlüftung startet aufgeklappt, andere Blöcke zugeklappt. „EWT-Klappe vorhanden“ ist eine Checkbox.
- **Reihenfolge:** Tägliche Uhrzeitsynchronisation, Filterintervall, Automatikmodus, direkt darunter „Stufen statt Automatik anzeigen“, danach die gruppierten Lüftungsstufen. EWT steht zuerst auf der Anlagenseite, Defroster-Typ vor Frostschutzmodus. Schreibbare Schwellen stehen in ihren Anlagenblöcken; reine Kennlinien-Lesewerte nur auf der letzten erweiterten Seite.
- „Sommerlüftung aktiv“ steht im Geräteblock **Konfiguration**. Filter-Reset ist ein Diagnosebutton.
- Bypass- und Sommerschalter werden anhand eintreffender Anlagenflags aktiviert/deaktiviert; manuelles Deaktivieren bleibt erhalten. Alte Ausstattungs-Binärsensoren werden zugunsten von Lüfterattributen entfernt.
- `novus300-schema.svg` durch `novus300-base.svg` und transparente Nachheizungs-/EWT-/Sole-/Bypass-/Defroster-Ebenen ersetzt. Die Übersicht behält ihre Luftstromgrafik; beide Ansichten benötigen keine Zusatzkarten.
- EWT-Beschriftungen und deutsche/englische Entitäts-/Dashboard-Dokumentation überarbeitet. YAML und editierbare UI-Kopie werden unabhängig gepflegt; README-Links vereinfachen HACS-Installation und Integrationseinrichtung.

### Behoben
- **Stufenwiederherstellung:** Gespeicherten Original-Prozentwert erhalten, wenn eine weitere temporäre Prozentänderung fehlschlägt, damit die inaktive Stufe später zurückgesetzt werden kann. Tests prüfen Panel-Modusrückmeldung, Erhalt einer aktiven Überschreibung und Wiederholung nach Schreibfehlern.
- **Halbe Disbalance-Prozente:** 0,5-%-Schritte ohne Ganzzahl-Abschneiden bei Codierung, Auswertung und Speicherung (ein signed Rohwertschritt = 0,5 %).
- Bekannte Anlagenwerte stehen in Abschnittsvorgaben und ersetzen veraltete Formularwerte ohne Schreibzugriff. Unbekannte Felder bleiben leer, fehlerhafte Eingaben zur Korrektur sichtbar. Gespeicherte Optionen bleiben kompatibel.
- Unbekannte Disbalance bleibt leer und wird beim Speichern anderer Einstellungen nicht stillschweigend mit null überschrieben. Die bestehende aufsteigende Stufenprüfung gilt nur für Lüfterprozente.
- Der allgemeine Einstellungsdialog meldet Schreibfehler, statt vermeintlich erfolgreich zu speichern. Ohne bekanntes Anlagenwort kann die Bypass-Installation nicht geändert werden.
- Die Bridge-Whitelist erlaubt nur die neuen Einzelregister-Disbalancebefehle im unterstützten signed Bereich. CRC-Prüfung und Sperren anderer Register bleiben erhalten.

### Update- und Prüfhinweise
- Diese Release wurde ohne Versionswechsel ergänzt. Bereits installierte **2026.11.20** erneut herunterladen/installieren und Home Assistant neu starten. Dynamische Bus-Adressen bleiben ausgeschaltet, bis sie unter **Neu konfigurieren → Schnittstelle: RS-485-Bus** aktiviert werden.
- **Bridge-Skript ebenfalls aktualisieren**, Bridge-Dienst und Home Assistant neu starten; Dashboard-YAML und editierbare Kopien separat aktualisieren. Integrations-/HACS-Updates überschreiben kein UI-Dashboard.
- Bestehende Entity-IDs bleiben stabil. Sommeraktivierungs-Automationen verwenden `switch.novus300_summer_ventilation`; Installation und Temperaturschwellen bleiben in den Optionen.
- **55 busfreie Regressionstests** prüfen Protokoll, Bridge, Coordinator, Entitätsverwaltung und Konfigurations-/Optionsdialoge einschließlich dynamischer Header, CRC-Ablehnung, fragmentierter Daten und Neusynchronisation. Für die Tests wurden weder Lüftungswerte noch Bypass-Stellung verändert.
- Erneute Wahl derselben Panel-Stufe ist in vorhandenen Mitschnitten nicht belegt. Stufenschreiben wartet keine Anlagenbestätigung ab.
- **Direktes Bypass-Öffnen/Schließen bleibt offen.** Register `0x1A` ist eine Rückmeldung, kein belegter Stellbefehl. Sommeraktivierung erzwingt keine Klappenstellung. Bus-Rückmeldung ist keine Hardwarebestätigung; physische Klappenbewegung wurde nicht getestet.

## 2026.11.19

### Highlights
- **Schreibbare Anlagenparameter im Einstellungsdialog:** neue Dialoge „Anlagenparameter“ (Automatik-Modus, Frostschutz, min. Zuluft, Nachheizung, Defroster, EWT-Klappe) und „Bypass und Sommerlüftung“ (Bypass vorhanden, Sommerlüftung, Schwellen, Hysterese). Temperaturen mit einer Nachkommastelle.
- **Vorschaltdialog bei fehlenden Anlagenwerten:** fehlen Werte, nennt ein Menü sie und bietet „Anlage neu starten“ (nur auf Wunsch), „Erneut prüfen“ und „Trotzdem öffnen“. Werte, die nur das Bedienteil sendet, werden mit Menüpfad und Anleitung aufgelistet.
- **Dashboard einfacher installieren:** Die Grafik liefert die Integration selbst aus (kein Kopieren nach `config/www/` mehr), dazu eine ausführliche Anleitung: [docs/DASHBOARD.de.md](docs/DASHBOARD.de.md).

### Neu
- Der Dialog „Erweitert“ zeigt nur noch die noch nicht zugeordneten Register; aufgelöste stehen in den neuen Dialogen.
- Diagnosedaten (`diagnostics.py`) und Übersetzungen für fr/es/it/nl (neue Dialoge vorerst englisch).
- Temperatursensoren mit eigenen Icons und fester Reihenfolge.
- **Fehlercodes:** alle Codes aus dem Handbuch (Sensoren, Lüfter, Bypass, Bus/Kommunikation) werden benannt; der Meldungssensor hat ein Attribut `hint` mit Ursache und Maßnahme.
- **Neuer Dialog „Schwellen“:** Hysteresen (Frostschutz Zuluft, Nachheizung, EWT-Klappe), Kühlschwelle Sole-Defroster und EWT-Klappen-Schwellen sind schreibbar; die Sensor-Kennlinie wird nur gelesen. „Erweitert“ zeigt Namen und Einheiten aus der Registerliste von novus2mqtt.
- Fix: Der Startwerte-Dump wird vollständig ausgewertet (Bypass/Sommerlüftung, Nachheizung, Klappe, Frostschutzmodus nach einem Anlagenneustart).
- **Bypass-Schalter** ist standardmäßig deaktiviert (bei vorhandenem Bypass aktivieren); neues Attribut bypass_present aus dem Anlagenflag, Schreiben wird mit passender Meldung abgelehnt.
- **Neuer Button „Alle Werte neu anfordern“** (Diagnose): sendet die Dump-Anforderung (0x83), die Anlage sendet alle Register erneut, z. B. um fehlende Werte ohne Neustart zu füllen. Das Bedienteil wird kurz gestört. Die Bridge muss dafür aktualisiert werden.
- **Dashboard-Ansicht „Sensoren“:** eigenes Anlagenschema (`novus300-schema.svg`) mit den Temperaturen und dem Bypass-Zustand an den Sensorstellen.
- **Serielle Bridge (`tools/`):** Whitelist für die Parameter- und Auswahlregister erweitert (auf dem Bridge-Rechner aktualisieren).

### Geändert
- `dashboards/novus300.yaml` verwendet `/novus300bus/novus300-airflow.svg`. Die SVG liegt jetzt in `custom_components/novus300bus/www/`. Die Integration hängt nun von `http` ab.

### Hinweise
- Das Schreiben der Parameter in die Anlage ist noch wenig getestet. Nach einem Update Home Assistant neu starten und die Bridge aktualisieren.

## 2026.11.18

### Highlights
- **Stufenlose Lüftersteuerung über den Bus:** `fan.novus300` arbeitet jetzt mit Regler und Prozentwert direkt über RS-485, ohne 0-10-V-Hardware (Tinkerforge). Im Automatikmodus wird der tatsächliche Steuerwert in Prozent angezeigt.
- **Anlage ein-/ausschalten** (`switch.novus300_power`) sowie Bypass- und Betriebsstatus.
- **Fertiges Dashboard** nur aus Standard-Karten: Luftstrom-Grafik, hervorgehobene Modus-Tasten, farbige Kacheln für Stoßlüftung / Meldung / Filter, Verlauf der Statuswechsel. Screenshots in der README.
- **Klare Modusanzeige:** Die Auswahl bleibt auf „Automatik“, solange ein Prozentwert gesetzt ist; Stufen behalten ihre ursprünglichen Prozentwerte (optional echte Stufen anzeigen).
- **Meldungen und Statuswechsel** der Anlage mit Verlauf, dazu erweiterte Dokumentation, Automatisierungsbeispiele und vollständige Entitätenliste.

### Neu
- **`switch.novus300_power` („Betriebsstatus“)** schaltet die Anlage über den Bus ein und aus (Panel-Frames für Register 0x07) und zeigt den Betriebsstatus mit Icon und Attribut `run_state`. Das Einschalten nimmt die Anlage erst etwa 30 Sekunden nach dem Ausschalten an.
- **`switch.novus300_bypass` („Bypass geöffnet“)**: Bypass-Zustand, nur lesbar (Öffnen/Schließen ist noch nicht bekannt), Attribute `air_path` und `raw_value`.
- **Statuswechsel in `sensor.novus300_message`:** jeder Wechsel des Betriebsstatus (z. B. „Anlage fährt hoch“) oder des Luftwegs (z. B. „Bypass in Bewegung“) steht im Attribut `status_events` und ; nur Übergänge („Anlage startet“, „Bypass in Bewegung“, unbekannte Werte) werden solange sie andauern als Meldung angezeigt, vor der eigenen Meldung der Anlage. Stabile Zustände zeigen die Schalter.
- `fan.novus300` hat die Attribute `bus_setpoint` und im Modus Abwesend `away_minutes_per_hour`.
- `switch.novus300_power` zeigt zusätzlich die Seriennummern von Bedienteil, Lüfter-Slave und Defroster sowie die aktuellen Einstellungen (`config_*`) als Attribute.
- **Fan (Bus-Modus):** Der Zustand ist jetzt der Prozentwert (oder `aus`) wie bei 0-10 V; Regler und Prozentanzeige statt Ein/Aus.
- **Fan (Bus-Modus):** Im Automatikmodus ist der Prozentwert das von der Anlage gemessene 0-10-V-Signal (`bus_setpoint`, bei 0 der letzte bekannte Wert) statt 0 %/aus.
- **Lüfterstufen:** Überschreibt der Lüfter-Prozentwert vorübergehend Stufe 1/3, zeigt die Modus-Auswahl standardmäßig `Automatik` (neue Option für die echte Stufe); die Wahl einer Stufe stellt deren ursprünglichen Prozentwert wieder her. Die Optionen zeigen jetzt den ursprünglichen Stufenwert statt des temporären.
- **Dashboard:** fertiges `dashboards/novus300.yaml` nur aus Standard-Karten von Home Assistant (keine HACS-Karten): Luftstrom-Grafik mit klickbaren Temperaturen, Modus-Tasten mit hervorgehobener aktiver Stufe (Tile-Feature `select-options`), Lüfter-Regler, Kacheln für Stoßlüftung / Bypass / Betriebsstatus, farbig hervorgehobene Kacheln, die nur bei Bedarf erscheinen (Boost aktiv = blau, Meldung vorhanden = rot, Filter-Restlaufzeit 0 = rot), Wartungskarte, Attribut-Details und Liste der Statuswechsel. Screenshots: [docs/images/dashboard.png](docs/images/dashboard.png).
- **Option „Stufen statt Automatik anzeigen, wenn der Lüfter per Prozent gesteuert wird“** (`show_fan_levels`, standardmäßig aus): aus = die Modus-Auswahl bleibt auf `Automatik`, solange ein Lüfter-Prozentwert aktiv ist; an = sie zeigt Stufe 1/3 wie die Anlage.
- **Dokumentation:** vollständige Liste aller Entitäten und Attribute in [docs/ENTITIES.de.md](docs/ENTITIES.de.md).
- **Serielle Bridge (`tools/`):** die Power-Frames (Aus/Ein) sind jetzt freigegeben.

### Behoben
- Der Wechsel von einer Stufe auf Automatik lässt die Anlage nicht mehr auf 0 %; es wird der letzte Automatik-Prozentwert verwendet.
- `fan.turn_on` schlug mit Fehler fehl (auch mit 0-10 V); 0 % / `turn_off` wählen jetzt den Modus Abwesend.

### Geändert
- **Entitätsnamen sind jetzt übersetzbar:** Englisch ist die Standardsprache (z. B. „Boost ventilation“, „Operating state“, „Supply air temperature“), Deutsch bleibt für deutsche Installationen erhalten. Die Entity-IDs ändern sich nicht. [docs/ENTITIES.md](docs/ENTITIES.md) nennt die englischen Namen, [docs/ENTITIES.de.md](docs/ENTITIES.de.md) die deutschen.
- `sensor.novus300_message` ist jetzt eine Diagnose-Entität.
- `fan.novus300`, `select.novus300_ventilation_mode` und `button.novus300_boost` und `button.novus300_filter_reset` sind nicht verfügbar, solange die Anlage aus ist.
- Stufen-Prozentwerte im Optionsdialog beginnen bei 17 % (es muss gelten: 17 % ≤ Stufe 1 < Stufe 2 < Stufe 3 ≤ 100 %). `fan.novus300` hebt Soll-Werte von 1–16 % auf 17 % an, auch mit 0-10 V (der HA-Schieberegler selbst lässt sich nicht einschränken). 0 % (und Ausschalten) wählt den Modus Abwesend; der Fan zeigt dann 0 % / aus.

### Dokumentation
- Inhaltsverzeichnis, überarbeitete Einleitung (die Integration liest nicht mehr nur), Screenshots, Automatisierungsbeispiele und ausführliche Beschreibung jedes Feldes im Optionsdialog.

## 2026.11.17

### Neu
- **`fan.novus300` ist immer verfügbar** und zeigt den Prozentwert der aktiven Stufe (z. B. Stufe 2). Setzen eines Prozentwerts: mit 0-10 V wird Automatik gewählt und der Wert per Tinkerforge geschrieben; ohne 0-10 V steuert die Entität die Anlage über den Bus.
- **Lüfter ohne 0-10 V:** die Bus-Steuerung funktioniert so. Ein Soll unter Stufe 2 wählt Stufe 1 und setzt deren Prozentwert vorübergehend auf das Soll, über Stufe 2 entsprechend Stufe 3; der ursprüngliche Prozentwert von Stufe 1/3 wird (dauerhaft) gemerkt und beim Verlassen der Stufe zurückgeschrieben.
- **Geräteinfo:** Modell Novus 300 (FOCUS250), Busversion 1.7.1; Bedienteil, Lüfter-Slave und Defroster als Untergeräte „Paul Novus 300 …“ mit Softwareversion (ETA0036E29A, SWZ0025B26A, ST00064E24A), gelesen aus der Start-Meldung der Anlage; bekannte Werte dienen als Vorgabe.
- **`sensor.novus300_message`:** aktuelle Meldung der Anlage (z. B. „Filter wechseln“, Code 0x41 in Register 0x09) mit Icon; Attribute `previous_message`, `previous_message_2`, `previous_message_3` enthalten die letzten drei Meldungen der Anlage als lesbaren Text (Zeit, Code, Meldung, übersetztes Detail); `occurred_at` zeigt, wann die letzte Meldung auftrat (HAs eigenes „Letzte Aktualisierung“ lässt sich nicht setzen); Meldungs-Icon (Register 0x0A–0x0C, 0x88–0x8D, von der Anlage beim Start gesendet und von der Integration gespeichert); `observed` listet die von Home Assistant gesehenen Wechsel.
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
