# Dashboard installieren

Das mitgelieferte Dashboard zeigt das Anlagenschema mit allen vier Temperaturen, die Bedienelemente (Modus, Stufe, Stoßlüftung, Power, Bypass), Meldungen, Filterstatus und die Statuswechsel. Es besteht nur aus Standardkarten. Zusätzliche HACS-Frontend-Karten sind nicht nötig.

![Dashboard-Übersicht](images/dashboard.png)

## Voraussetzungen

- Die Integration ist eingerichtet und die Entitäten `sensor.novus300_*`, `select.novus300_ventilation_mode`, `fan.novus300` usw. sind vorhanden (Einstellungen → Geräte & Dienste → Paul Novus 300 → Entitäten).
- Die Grafik `novus300-airflow.svg` wird **von der Integration selbst** unter `/novus300bus/novus300-airflow.svg` ausgeliefert. Sie muss **nicht** mehr nach `config/www/` kopiert werden. Nach einem Update der Integration ist ein Neustart von Home Assistant nötig.

## Variante A: Eigenes Dashboard in der Oberfläche (empfohlen)

1. **Einstellungen → Dashboards → Dashboard hinzufügen** (unten rechts).
2. **Neues Dashboard von Grund auf** wählen, Titel z. B. „Lüftung" eingeben, **Erstellen**.
3. Das neue Dashboard in der Seitenleiste öffnen.
4. Oben rechts auf den **Stift** (Bearbeiten) klicken. Beim ersten Mal „Dashboard selbst verwalten" bestätigen.
5. Oben rechts auf **⋮ → Rohkonfigurationseditor** klicken.
6. **Den gesamten vorhandenen Inhalt löschen** (Strg+A, Entf).
7. Den kompletten Inhalt von [`dashboards/novus300.yaml`](../dashboards/novus300.yaml) einfügen (auf GitHub: Schaltfläche „Copy raw file").
8. **Speichern**, Editor schließen, Bearbeitung beenden (Häkchen).

## Variante B: Als YAML-Datei einbinden

1. Die Datei `novus300.yaml` nach `config/dashboards/novus300.yaml` kopieren (Ordner anlegen, falls nötig).
2. In `configuration.yaml` ergänzen:

   ```yaml
   lovelace:
     dashboards:
       lueftung:
         mode: yaml
         title: Lüftung
         icon: mdi:fan
         show_in_sidebar: true
         filename: dashboards/novus300.yaml
   ```

3. Home Assistant neu starten. Das Dashboard erscheint in der Seitenleiste. Änderungen an der Datei wirken nach dem Neuladen der Browserseite.

## Variante C: Als Ansicht in ein bestehendes Dashboard

Im Rohkonfigurationseditor des bestehenden Dashboards (Schritte 4–5 oben) nur den Block unter `views:` aus `novus300.yaml` (ab `- title: Übersicht`) an die vorhandene `views:`-Liste anhängen. Die Einrückung muss dabei zur bestehenden Liste passen.

## Ansicht „Sensoren“ (Handbuch-Schema)

Die zweite Ansicht legt die Temperaturen über das Anlagenschema aus dem Paul-Handbuch. Die Grafik ist urheberrechtlich geschützt und liegt deshalb nicht im Repository. Einmalig herunterladen und als `/config/www/novus300-sensors.png` ablegen:

```bash
curl -L -o /config/www/novus300-sensors.png \
  https://raw.githubusercontent.com/larda3141/novus2mqtt/main/docs/sensors.png
```

Ohne die Datei bleibt diese Ansicht leer; die Übersicht funktioniert unabhängig davon.

## Prüfen

- Das Schema mit der Grafik und den Temperaturen erscheint. Ist die Grafik leer, im Browser `http://<ha-adresse>:8123/novus300bus/novus300-airflow.svg` öffnen. Es muss ein Bild erscheinen. Andernfalls wurde Home Assistant nach dem Update nicht neu gestartet.
- Karten mit „Entität nicht verfügbar" zeigen auf Entitäten, die es bei dir nicht gibt. Siehe nächster Abschnitt.

## Entitäts-IDs anpassen

Das Dashboard verwendet die Standard-IDs, die die Integration vergibt (`sensor.novus300_supply_air_temperature` usw.). Wurden Entitäten umbenannt oder bei einer älteren Installation anders vergeben, im Rohkonfigurationseditor mit **Suchen und Ersetzen** (im Editor Strg+H, sonst Texteditor vor dem Einfügen) die ID ersetzen. Die tatsächlichen IDs stehen unter Einstellungen → Geräte & Dienste → Paul Novus 300 → Entitäten.

Verwendete Entitäten: `select.novus300_ventilation_mode`, `fan.novus300`, `button.novus300_boost`, `switch.novus300_power`, `switch.novus300_bypass`, `sensor.novus300_message`, `button.novus300_filter_reset` sowie die Temperatur- und Filtersensoren.

## Häufige Probleme

| Problem | Ursache / Lösung |
| --- | --- |
| „Rohkonfigurationseditor" fehlt im Menü | Das Dashboard wird automatisch verwaltet. Im Bearbeiten-Modus zuerst „Dashboard selbst verwalten" bestätigen. |
| Fehler „Konfiguration ungültig" beim Speichern | Alter Inhalt nicht vollständig gelöscht oder falsch eingerückt eingefügt. Editor leeren und erneut einfügen. |
| Grafik fehlt, Rest funktioniert | Home Assistant nach dem Integrations-Update neu starten. Danach Browser-Cache leeren (Strg+F5). |
| Alle Karten „nicht verfügbar" | Integration nicht geladen oder Entitäts-IDs abweichend (siehe oben). |
| Alte Anleitung: Datei in `config/www/` kopiert | Nicht mehr nötig. Die Kopie in `www/` kann gelöscht werden. |
