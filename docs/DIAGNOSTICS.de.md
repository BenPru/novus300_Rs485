# Neue Hardware mit Integrations-Diagnosedaten melden

[English](DIAGNOSTICS.md)

<a id="xor-beta-20261123b1"></a>
<a id="xor-beta-20261124b1"></a>

## XOR-Beta 2026.11.28b1

Der separate Zweig `beta/xor-read-only` unterstützt das alternative Protokoll
aus den Mitschnitten in Ticket #10. Die Auswahl bezeichnet bestätigte
**Protokollprofile**, keine bereits bekannten Hardware-/Firmwaregenerationen:

- **CRC16 - Referenzanlage (TFT ETA0036E29A):** bisheriges Verhalten einschließlich
  konfigurierter Schreibfunktionen; Standard für bestehende Einträge.
- **XOR - Variante aus Ticket #10 (HW/FW unbekannt, Beta nur lesend):** keine
  Bus-Schreibzugriffe, tägliche Uhrzeitsynchronisation, Registerabfragen,
  Lüfter-/Select-/Switch-Steuerung oder optionale Tinkerforge-Ausgabe.
  Auch direkte Schreib-Serviceaufrufe werden zurückgewiesen.

Angezeigt werden **Gewählte Lüfterstufe (experimentell)**,
`sensor.novus300_xor_fan_stage`, Telegrammzähler, zuletzt geänderte Rohdatenseite
(`Adresse:Seite`, hexadezimal) und eine **experimentelle BCD-Busuhr**. Deren
Zuordnung ist noch nicht am Panel bestätigt; sie wird nie automatisch gestellt.
Diagnosen enthalten zusätzlich Adress-/Typzähler und bis zu 64 letzte Rohseiten.
Die Stufenskala ist **1-7**, nicht die TFT-Moduszuordnung: 4/5/6 bedeuten hier
**nicht** Stoßlüftung/Abwesend/Automatik. Mitschnitte bestätigen Stufen 1/2/3
und Stufe 7 während der Stoßlüftung. Der Nutzer bestätigt alle sieben Stufen
gegen die LEDs; für 4-6 fehlen noch beschriftete Rohaufnahmen. Sensorattribute unterscheiden
`capture_confirmed`, `inferred` und `unmapped` und enthalten den Rohwert.
Andere Werte einschließlich 0 erscheinen **unbekannt**, nicht als vermutetes
Standby. Die gewählte Stufe ist keine gemessene Drehzahl oder Leistung und kein
Nachweis laufender Lüfter. Stufe 7 allein beweist keine aktive Stoßlüftung.
Temperaturen, Bypass und Ausstattung
sind weiterhin nicht zugeordnet.
Unbekannte Firmware und Ersatzkennungen erscheinen nicht als erkannte XOR-Hardware.

**Neu: Betriebsart (experimentell)**, `sensor.novus300_xor_operating_mode`,
liest Seite `04:00`, Datenoffset 13 ab null, ohne das Seitenbyte:

| Rohwert | Zustand | Panelmodus |
|---|---|---|
| 1 | `supply_extract` | Zu- und Abluft |
| 2 | `extract_only` | Nur Abluft |
| 3 | `supply_only` | Nur Zuluft |
| 4 | `boost` | Stoßlüftung |

Das ist Panel-Modusrückmeldung, kein gemessener Luftstrom oder Lüfterlaufnachweis.
Während Stoßlüftung wird keine separate Luftart abgeleitet. Unbekannte Rohwerte
ersetzen den bisherigen Modus durch **unbekannt** und bleiben in Attributen und
Diagnose erhalten. Das Stufenattribut `boost_status` ist `active`, `inactive`
oder `unknown`, abhängig vom Modusfeld statt von der Stufennummer.
Alle sechs manuellen Moduswechsel sind offline reproduziert; das automatische
Ende der Stoßlüftung wurde noch nicht aufgezeichnet.

**Schreiben bleibt gesperrt, ohne Freigabeschalter.** Der aufgezeichnete Wechsel
enthält einen Handshake mit einem 16-Byte-Block, keinen isolierten Stufenbefehl.
Busteilnehmerrollen, sichere Arbitrierung und Erhaltung der anderen Felder
sind nicht geklärt. Einen alten Block über einen generischen TCP-Konverter
abzuspielen wäre auch nach Prüfung der Anzeige keine verifizierte Schreibfunktion.

### Installieren und Profil wählen

1. Home Assistant und bestehende Integrationsdateien sichern.
2. **HACS > Paul Novus 300 RS-485 Bus > Dreipunktmenü > Erneut herunterladen**:
   unter **Andere Version benötigt? / Need a different version?** die Version
   gegebenenfalls Betaversionen einblenden und **2026.11.28b1** wählen.
   Das ist die XOR-Beta, nicht CRC16/TFT-Beta 2026.11.26b1.
   Falls nicht angeboten, die manuelle Variante nutzen.
3. **Home Assistant**, nicht die Lüftung, neu starten. Unter **Einstellungen >
   Geräte & Dienste > Paul Novus 300 RS-485 Bus > Konfigurieren >
   Grundeinstellungen und Anlagenwerte** das **Hardware-/Firmwareprofil XOR**
   wählen und speichern. Die Auswahl gibt es auch bei **Neu konfigurieren >
   Schnittstelle: RS-485-Bus** und der Ersteinrichtung. Ein Profilwechsel
   speichert nur die Auswahl, ignoriert andere Änderungen dieses Formulars
   und lädt die Integration neu; für weitere Änderungen das Formular neu öffnen.
4. Bridge-URL sowie **9600, 8N1**, TCP Server und Transfer Protocol None
   beibehalten. Dynamische Adressen gelten nur für CRC16. Auf einer XOR-Anlage
   nicht CRC16 wählen, um Steuerungen freizuschalten.

**Manuell:** [Beta-Quellcode-ZIP](https://github.com/BenPru/novus300_Rs485/archive/refs/tags/2026.11.28b1.zip)
herunterladen. Bisherigen Ordner `/config/custom_components/novus300bus` an einen
Sicherungsort **außerhalb** von `custom_components` verschieben. Nur
`custom_components/novus300bus` aus dem ZIP nach `/config/custom_components/`
entpacken, dann Schritte 3-4 ausführen. Nicht das ganze Repository kopieren oder
andere Integrationen überschreiben. Rückkehr durch Neuinstallation von
**2026.11.21** beziehungsweise Rückspielen des gesicherten Ordners und HA-Neustart;
bei nötiger Konfigurationswiederherstellung das Backup nutzen.

### Aufzeichnen, ohne Befehle zu senden

Auf der **Geräteseite** unter **Diagnose** einmal **120 Sekunden passiv
aufzeichnen** drücken. Genutzt wird ausschließlich die bestehende
Empfangsverbindung; **keine Befehle**, auch kein Register-Dump.
Mindestens 125 Sekunden warten und dann die Integrationsdiagnose wie unten
beschrieben herunterladen. Eine laufende Aufzeichnung wird nicht überschrieben;
nach dem Download lässt sich eine neue starten.

`passive_recording` enthält UTC-Zeiten, vollständige Byte-Reihenfolge, Bytezahl
und Status (`recording`, `complete`, `truncated`; anfangs `not_started`).
Kleine Lesevorgänge werden in ungefähr 100-ms-Blöcken zusammengefasst;
deren Zeitstempel bezeichnet den ersten Lesevorgang, nicht jedes einzelne Byte.
Grenzen: 120 Sekunden, 1 MiB oder 2400 Blöcke. `complete` mit null Bytes bedeutet
keinen Empfang, **keinen** Kommunikationserfolg. Die Daten bleiben bis zum
Ersetzen/Neuladen im Arbeitsspeicher; vor HA-Neustart oder Reload herunterladen.

Zuerst unverändert aufzeichnen. Für LED-Paneltests die Abläufe unten verwenden.
Genaue Aktionszeiten mit UTC-Abweichung, LED-Anzahl und HA-Stufe notieren;
das LED-Panel hat keine Temperatur- oder Uhranzeige.
Anlagen-, Panel-, Hardware- und Software-/BUS-Version von zugänglichen Infoseiten
oder Typenschildern ablesen; Fotos mit geschwärzten Seriennummern helfen.
Keine geöffneten spannungsführenden Abdeckungen, Frost-/Heizungsänderungen,
Resets, Lüftungsneustarts oder Dumps. **Vor Upload Datenschutz prüfen:** Abschnitt 4.

### Alle sieben LED-Stufen prüfen

Nur am physischen Panel und mit im normalen Betrieb passenden Stufen testen.
Soweit sinnvoll auf Stufe 1 beginnen. Passive Aufzeichnung starten, nach 20 s
Stufe 2, nach 50 s Stufe 3 und nach 80 s wieder die ursprüngliche normale Stufe
wählen. Tatsächliche Tastendrücke, LED-Anzahl und anschließend eingependelte
HA-Anzeige notieren. Nach 125 s Diagnose herunterladen, **bevor** die nächste
Aufzeichnung gestartet wird.

Sofern höhere Stufen im normalen Betrieb passen, separat aufzeichnen:
nach 20 s Stufe 4, nach 40 s Stufe 5, nach 60 s Stufe 6, nach 80 s Stufe 7,
nach 100 s die ursprüngliche normale Stufe wiederherstellen.
Bei mehreren +/-Tastendrücken auch Zwischenstufen notieren. Keine ungewöhnlich
hohen Stufen nur für den Test wählen. Bei falscher HA-Anzeige denselben
Rohmitschnitt anhängen; er enthält die zur Korrektur benötigten Bytes.
Dateien etwa `stages-1-3.json` und `stages-4-7.json` nennen.

Je Aktion: `lokale Uhrzeit mit UTC-Abweichung | Taste/Anzahl Tastendrücke |
LED-Anzahl | HA-Stufe | raw_value | mapping_status`.
Aktive Automationen, Stoßlüftung und mögliche externe Übersteuerung nennen,
aber Automationen oder Verkabelung nicht eigens für die Aufnahme ändern.

### Passive Dumps der anderen LED-Tasten

Das sind **reine Empfangsmitschnitte**, keine aktiven Register-Dump-Anfragen.
Pro Funktion eine separate 120-s-Aufzeichnung, Download nach 125 s.
Anfangsstufe, Modus-LEDs und genaue Aktionszeit notieren. Die physische Taste
etwa nach 20 s betätigen und danach alle LEDs sowie die HA-Stufe beobachten.
Den ursprünglichen Modus nur auf bekanntem normalem Bedienweg zurückstellen;
Zeitpunkt und Bedienung notieren. Im Zweifel die nächste reguläre Nutzung
aufzeichnen, statt einen Test zu erzwingen.

| Taste | Bedeutung laut Novus-Anleitung | Sinnvolle Aufnahme |
|---|---|---|
| + / - | Sieben gewählte Lüfterstufen | Stufentests oben |
| Stoßlüftung | Zeitprogramm auf Stufe 7, Werkseinstellung 15 Minuten | `boost.json`: Aktivierung bei normaler Nutzung; Stoßlüftungs-LED von Stufen-LEDs unterscheiden |
| Zu- und Abluft | Betrieb beider Lüfter | `balanced.json`, gegebenenfalls Rückkehr aus anderem erlaubtem Modus |
| Nur Abluft | Zuluftlüfter abgeschaltet | `extract-only.json`, **nur wenn diese Betriebsart zulässig ist** |
| Nur Zuluft | Abluftlüfter abgeschaltet | `supply-only.json`, **nur wenn zulässig** |
| Filter/Reset | Filterlaufzeitzähler zurücksetzen | `filter-reset.json`, **nur bei tatsächlich fälliger Filterwartung**, nicht eigens zur Diagnose |

**Feuerstättenwarnung:** Laut Anleitung muss der Abluft-Modus beim Betrieb mit
Feuerstätte gesperrt sein. Nicht entsperren, Verriegelungen umgehen oder
Einlüfterbetrieb ohne geklärte Zulässigkeit testen. Keine versteckten
Kombinationen für Feuerstätte, Bypassschwellen oder Disbalance ausprobieren.
Standby, Netzneustart, Frost-/Heizungsänderungen und aktive Dumps sind nicht nötig.
Das reguläre Ende der Stoßlüftung bei Bedarf separat erfassen; die zweiminütige
Aufzeichnung reicht nicht über die werkseitigen 15 Minuten.
Die manuellen Stoßlüftungs-/Luftartaufnahmen vom 26. November müssen nicht
wiederholt werden. Zuerst den neuen Sensor bei normaler Nutzung mit den LEDs
vergleichen. Optional die passive 120-s-Aufnahme kurz vor dem erwarteten
natürlichen Ende starten, LED-Wechselzeit notieren und nach Abschluss
herunterladen. Dauer nicht ändern, nichts zurücksetzen und keine Einlüftertests
eigens dafür wiederholen.

Diagnosedaten einer anderen kompatiblen Lüftungsanlage oder zusätzlicher
Ausstattung (zum Beispiel einer EWT-Klappe) helfen, unbekannte Busregister
zuzuordnen. Eine Meldung bedeutet noch nicht, dass die Hardware unterstützt
wird. Die bestehende Integrationsverbindung genügt: kein zusätzlicher
TCP-Client, keine Änderungen an der Busverkabelung und kein separates
Aufzeichnungsprogramm.

## 1. Hardware beschreiben

Genauen Anlagentyp, Panelmodell und Firmwareversionen notieren, soweit bekannt.
Home-Assistant- und Integrationsversion sowie Verbindungstyp und gegebenenfalls
Bridge-Version ergänzen.

Die **tatsächlich verbaute** Ausstattung auflisten, etwa Bypass, EWT-Klappe,
Defroster, Sole-Defroster und Nachheizung, möglichst mit Typ/Modell.
Davon getrennt angeben, welche Ausstattung Panel und Integration melden.
Installationsflags nicht zum Abgleichen verändern. Fehlende oder unerwartete
Werte und die tatsächlich am Panel angezeigten Werte beschreiben.

## 2. Ausgangszustand und einzelne Aktionen aufnehmen

1. Bei verbundener Integration und eingehenden Daten eine Ausgangsdiagnose wie
   unten beschrieben herunterladen.
2. Datum und genaue lokale Uhrzeit **mit Zeitzone/UTC-Abweichung**, aktuellen
   Modus und ursprünglichen Wert der betrachteten Einstellung notieren.
3. Soweit gefahrlos möglich, das betreffende vorhandene Panelmenü öffnen, ohne
   Änderungen zu speichern. Zeitpunkt und angezeigte Werte notieren und sofort
   Diagnosedaten herunterladen. Manche Werte werden erst beim Speichern oder
   Anlagenstart gesendet; bloßes Öffnen muss sie nicht sichtbar machen.
4. Nur wenn im normalen Betrieb vertretbar, **eine bekannte, unkritische
   Einstellung** am physischen Panel ändern. Aktion, Zeitpunkt sowie Vorher-/
   Nachher-Wert protokollieren und sofort Diagnosedaten herunterladen.
   Panelbedienung klar von HA-Bedienung und Automationen unterscheiden.
5. Geänderte Einstellung auf den Originalwert zurückstellen, am Panel prüfen,
   Zeitpunkt notieren und erneut Diagnosedaten herunterladen. Jede Datei
   eindeutig benennen und der jeweiligen Aktion zuordnen.

Auch eine rein passive Meldung ohne Änderungen ist hilfreich. Frostschutz,
Heizungstypen, Installationsflags und unbekannte Serviceparameter nicht für
eine Aufzeichnung verändern. Die Anlage nicht nur für fehlende Register neu
starten. Zwischen Aktion und Download weder HA neu starten noch die Integration
neu laden.

Beispiel für das Aktionsprotokoll (eigene Daten, Zeiten und Werte einsetzen):

| Zeitpunkt mit UTC-Abweichung | Aktion und Bedienort | Vorher | Nachher | Datei |
|---|---|---|---|---|
| JJJJ-MM-TT 14:01:00+01:00 | Ausgangsdiagnose, keine Änderungen | ... | Unverändert | baseline.json |
| JJJJ-MM-TT 14:02:10+01:00 | EWT-Menü am Panel geöffnet, nicht gespeichert | Panel zeigt ... | Unverändert | ewt-menu.json |

Bei Lüfterstufen **Wechsel auf eine andere Stufe** und **erneutes Drücken der
bereits aktiven Stufe** unterscheiden. Panel-Stufe, HA-Prozentwert,
ursprünglichen Stufen-Prozentwert und aktive Automationen notieren.
Ein wiederholter Buswert allein belegt keinen Tastendruck.

## 3. Integrations-Diagnosedaten herunterladen

In Home Assistant **Einstellungen > Geräte & Dienste > Integrationen** öffnen,
**Paul Novus 300 RS-485 Bus** aufrufen und beim betreffenden Integrationseintrag
im Drei-Punkte-Menü **Diagnosedaten herunterladen** wählen. Je nach
Frontendversion zuerst die Integrationsdetails öffnen, um das Eintragsmenü zu
erreichen.

Die JSON-Datei enthält ausgewertete Werte, den bekannten Parameterblock,
Meldungs-/Statushistorie und `raw_bus_log.chunks`. Das Rohprotokoll bewahrt die
empfangenen Bytes **vor der Auswertung** auf, also auch noch unbekannte Werte.
Jeder Chunk enthält `time` in UTC und die Bytes als Hexadezimaltext in `hex`.

Der Rohpuffer umfasst die letzten **3000 empfangenen Chunks im Arbeitsspeicher**,
keine feste Minutenzahl. Ein Chunk ist ein serieller Leseblock, nicht zwingend
ein vollständiges Telegramm. Alte Chunks werden überschrieben; Neustart oder
Neuladen der Integration leert den Puffer. Deshalb nach jeder Aktion zeitnah
herunterladen. Ein leerer Puffer oder fehlender Wert beweist nicht, dass die
Hardware diesen Wert nicht besitzt.

## 4. Datenschutz vor dem Hochladen prüfen

**Die Integration anonymisiert ihre Diagnosedaten derzeit nicht.** Enthalten
sind Konfiguration/Optionen, interne Adressen oder Hostnamen und
Gerätekennungen. Auch die Rohbytes können Kennungen enthalten. Der
Diagnoserahmen von Home Assistant kann weitere Systeminformationen enthalten.

Vor öffentlichem Hochladen eine **Kopie** jeder Datei prüfen. Zugangsdaten,
Tokens, persönliche Angaben und identifizierende Adressen/Seriennummern überall
entfernen, bei Bedarf auch aus Rohdaten. Zeitstempel, Firmwareversionen und
relevante Registerbytes möglichst erhalten und entfernte Bereiche im Issue
benennen. Wenn sich eine Datei nicht sicher bereinigen lässt, nicht öffentlich
hochladen. Niemals `.storage/auth`, `secrets.yaml` oder ein komplettes
Home-Assistant-Backup anhängen.

## 5. GitHub-Issue anlegen

Das [Issue-Formular „New hardware / diagnostic data“](https://github.com/BenPru/novus300_Rs485/issues/new?template=new-hardware.yml)
öffnen. Deutsch oder Englisch ist möglich.

Hardware/Versionen, tatsächlich verbaute Ausstattung, fehlende oder unbekannte
Werte und das Aktionsprotokoll eintragen. Die geprüften Diagnose-JSON-Dateien
per Drag-and-drop im Diagnosefeld anhängen und den Upload abwarten; alternativ
als ZIP. Nicht Tausende Rohprotokollzeilen in den Text kopieren.

Vorschau und Anhänge vor dem Absenden prüfen. Die Daten ermöglichen Vergleiche
bekannter und unbekannter Register, belegen allein aber weder einen sicheren
Schreibbefehl noch den physischen Absender eines Telegramms.
