# Paul Novus 300 RS-485 Bus

[![Validate with HACS validation](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml/badge.svg)](https://github.com/BenPru/novus300_Rs485/actions/workflows/validate.yml)

Home-Assistant-Integration zum passiven Auslesen einer Paul Novus 300 über
RS-485. Sie stellt Temperaturen, Betriebszustand, Luftweg, Filter- und
Betriebszeiten sowie die am Bedienpanel gewählte Lüftungsstufe bereit.

Optional kann sie einen vorhandenen Tinkerforge Industrial Analog Out V2 für
den 0-10-V-Eingang der Anlage als `fan.novus300` einbinden. Diese Ausgabe wird
ausschließlich im Panel-Modus **Automatik** steuerbar. Die RS-485-Schnittstelle
bleibt stets lesend.

## Voraussetzungen

- Home Assistant mit HACS
- Paul Novus 300 mit zugänglicher RS-485-Service-/Bus-Schnittstelle
- Ein für die Schnittstelle geeigneter RS-485-Adapter oder ein separater
  seriell-zu-TCP-Reader
- Optional für `fan.novus300`: Tinkerforge Master/Bricklet-System mit
  **Industrial Analog Out V2**, Brick Daemon und Netzwerkzugriff

> [!WARNING]
> Arbeiten an der Lüftungsanlage und ihrer Busverkabelung erfolgen auf eigene
> Verantwortung. Anlage spannungsfrei schalten, bevor Leitungen angeschlossen
> oder verändert werden. Anschlussbelegung, zulässige Leitungslänge und
> Abschlusswiderstände immer dem Paul-Handbuch und dem konkreten Anlagentyp
> entnehmen. Diese Integration sendet keine RS-485-Telegramme und darf nicht
> zum Schreiben auf den Bus erweitert werden.

## Installation mit HACS

1. In HACS **Integrationen** öffnen.
2. Über das Drei-Punkte-Menü **Benutzerdefinierte Repositorys** wählen.
3. `https://github.com/BenPru/novus300_Rs485` eintragen und als Kategorie
   **Integration** auswählen.
4. Die Integration herunterladen und Home Assistant neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
   **Paul Novus 300 RS-485 Bus** suchen.

Die Konfiguration erfolgt vollständig über die Oberfläche; YAML für die
RS-485-Integration ist nicht erforderlich.

## RS-485 anschließen und konfigurieren

### Direkter USB-RS-485-Adapter

1. Einen Adapter verwenden, dessen UART **MARK-Parität** bei 9600 Baud
   unterstützt. In Home Assistant immer den stabilen Gerätenamen
   `/dev/serial/by-id/...` verwenden, nicht `/dev/ttyUSB0`.
2. Den Adapter bei ausgeschalteter Anlage an die dafür vorgesehene RS-485-
   Schnittstelle anschließen:
   - `A`/`D+` des Adapters an `A`/`D+` der Anlage,
   - `B`/`D-` des Adapters an `B`/`D-` der Anlage,
   - Signalmasse nur dann verbinden, wenn sie im Paul-Schaltbild vorgesehen
     ist.
3. Keine eigene Busversorgung einspeisen und keine Abschlusswiderstände
   hinzufügen, sofern dies nicht explizit in der Anlagendokumentation verlangt
   wird.
4. In der Integration als serielles Gerät den `/dev/serial/by-id/...`-Pfad,
   **9600** Baud und die Parität **mark** auswählen.

Werden keine Werte empfangen, zuerst A und B gemäß Anlagendokumentation prüfen.
Leitungsfarben sind nicht genormt; A/B nicht anhand der Farbe zuordnen.

### Seriell über TCP

Die RS-485-Schnittstelle kann auch an einem separaten Rechner gelesen und dort
als TCP-Stream bereitgestellt werden. Das trennt die physische
Busanbindung vom Home-Assistant-Host.

- Der serielle Reader verarbeitet auf seiner lokalen UART-Seite 9600 Baud mit
  MARK-Parität.
- In der Integration `socket://<host>:<port>` eintragen, beispielsweise
  `socket://10.0.17.45:9700`.
- Für TCP in der Integration die Parität **none** wählen: Die Parität wurde
  bereits vom seriellen Reader verarbeitet.

Der eingesetzte TCP-Reader muss nur einen Client zulassen oder Zugriffe
serialisieren. Eine zweite parallele Verbindung kann die bestehende
Home-Assistant-Verbindung trennen.

## Optional: Tinkerforge 0-10-V-Lüftersteuerung

Die RS-485-Auslesung funktioniert ohne Tinkerforge. Dieser Abschnitt ist nur
für die zusätzliche Entität `fan.novus300` erforderlich.

### Tinkerforge vorbereiten

1. Den **Industrial Analog Out V2** mit dem Tinkerforge-Stack verbinden und
   dessen UID mit Brick Viewer ermitteln.
2. Brick Daemon auf dem Rechner/Gateway betreiben, der/das den Tinkerforge-
   Stack erreicht. Der Standardport ist `4223`.
3. Vom Home-Assistant-Host die TCP-Verbindung zu `<tinkerforge-host>:4223`
   erlauben.
4. In den Integrationsoptionen **0-10-V-Lüftersteuerung aktivieren** sowie
   Host, Port und UID eintragen.

### 0-10-V-Ausgang anschließen

1. Anlage und Tinkerforge-Hardware vor dem Verdrahten spannungsfrei schalten.
2. Den Ausgang `OUT` des Industrial Analog Out V2 mit dem in der
   Paul-Dokumentation bezeichneten **externen 0-10-V-Steuereingang** verbinden.
3. `GND` des Analogausgangs mit der dazugehörigen Signalmasse des
   Steuereingangs verbinden. Nicht mit RS-485 A/B verbinden.
4. Zulässige Spannungen, Massereferenz und mögliche galvanische Trennung der
   Paul-Anlage vor dem Einschalten anhand der Herstellerunterlagen prüfen.
5. Die Ausgabe zunächst mit 0 % testen und erst danach geringe Werte setzen.

`fan.novus300` liest beim Start die aktuell ausgegebene Spannung. Schreiben
ist nur möglich, wenn das Lüftungspanel auf **Automatik** steht. Bei
Panel-Stufe 1–3, Stoßlüftung, Abwesend oder Standby ist die Entität bewusst
schreibgeschützt.

Die Schaltfläche `button.novus300_boost` steht ebenfalls nur in Automatik zur
Verfügung. Sie setzt den 0-10-V-Ausgang für die konfigurierte Dauer auf den
Wert **Panel-Stoßlüftung** und stellt anschließend den vorherigen Wert wieder
her.

Wenn der konfigurierte Automatik-Helfer vorhanden ist, bietet `fan.novus300`
zusätzlich die Presets **Automatik** und **Manuell**. Sie schalten ausschließlich
diesen Helfer und sind ebenfalls nur bei Panel-Modus Automatik verfügbar.

## Panel-Stufen und Werte

Die Anlage überträgt für feste Panel-Stufen nur den Modus, nicht jedoch deren
zugehörige Prozentwerte. Die Integration ordnet daher folgende einstellbare
Werte zu:

| Panel-Modus | Standardwert | Konfigurationsfeld |
|---|---:|---|
| Lüftungsstufe 1 | 35 % | Panel-Lüftungsstufe 1 |
| Lüftungsstufe 2 | 60 % | Panel-Lüftungsstufe 2 |
| Lüftungsstufe 3 | 90 % | Panel-Lüftungsstufe 3 |
| Stoßlüftung | 75 % | Panel-Stoßlüftung |
| Abwesend | 15 % | Panel-Abwesend |

Die Werte sind Zahlenfelder von 0 bis 100 %. `fan.novus300` verwendet beim
Einschalten die konfigurierte **Panel-Lüftungsstufe 2**; die
Stoßlüftungs-Schaltfläche verwendet **Panel-Stoßlüftung**. Standby hat keine
eigene Prozentzuordnung und zeigt den Rohwert des Busses.

## Angelegte Entitäten

- Temperaturen für Zu-, Außen-, Ab- und Fortluft
- `sensor.novus300_ventilation_mode` für Standby, Automatik, Stufe 1–3,
  Stoßlüftung und Abwesend
- `sensor.novus300_fan_setpoint` für die Lüfteransteuerung
- Betriebsstatus, Luftweg und Bypass
- Gesamt- und Lüfterbetriebszeit sowie Filterintervall und Filterrestlaufzeit,
  sobald die Anlage den vollständigen Register-Dump sendet
- Optional `fan.novus300` und `button.novus300_boost`

Nicht jedes Register wird zyklisch übertragen. Nach einem Neustart von Home
Assistant kann ein Wechsel der Panel-Stufe nötig sein, damit der aktuelle
Modus erneut am Bus erscheint.

## Fehlerdiagnose

| Symptom | Prüfung |
|---|---|
| Keine RS-485-Werte | Stabilen `/dev/serial/by-id/...`-Pfad, 9600 Baud, MARK-Parität sowie A/B-Zuordnung prüfen. |
| TCP-Verbindung bricht ab | Sicherstellen, dass nur ein Client mit dem seriellen TCP-Reader verbunden ist. |
| `fan.novus300` ist nicht steuerbar | Panel auf Automatik stellen; Tinkerforge-Host, Port, UID und Brick Daemon prüfen. |
| Feste Panel-Stufe zeigt falschen Prozentwert | Den zugehörigen Panel-Wert in den Integrationsoptionen anpassen. |
| Filter-/Betriebszeit fehlt | Auf den vollständigen Register-Dump der Anlage warten; dieser wird nicht kontinuierlich gesendet. |

## HACS-Status und Aufnahme

Das Repository ist öffentlich, enthält genau eine Integration unter
`custom_components/novus300bus`, ein gültiges `manifest.json`, eine
Root-`hacs.json` und einen HACS-Validierungsworkflow. Damit kann es bereits
als **benutzerdefiniertes HACS-Repository** installiert werden.

Für eine Aufnahme in den offiziellen HACS-Standardkatalog werden zusätzlich
Brand-Assets benötigt, mindestens
`custom_components/novus300bus/brand/icon.png`. GitHub Releases sind
empfohlen, aber nicht verpflichtend. Nach Ergänzung der Brand-Assets und
einem erfolgreichen HACS-Workflow kann die Aufnahme gemäß
[HACS Publishing Guide](https://www.hacs.xyz/docs/publish/integration/)
beantragt werden.
