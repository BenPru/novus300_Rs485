# Neue Hardware mit Integrations-Diagnosedaten melden

[English](DIAGNOSTICS.md)

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
