# Fabians-HA-Downloader

Fügt Links zu Dateien in eine Warteschlange ein und lädt sie nacheinander herunter.

## Bedienung

- Link in das Suchfeld einfügen und **Hinzufügen** klicken (oder Enter drücken).
  Mehrere Links auf einmal (durch Leerzeichen oder Zeilenumbruch getrennt) sind möglich.
- Unter dem Suchfeld erscheint die Warteliste mit Dateiname, Größe und Fortschritt.
- Der **Mülleimer** entfernt einen Eintrag aus der Liste. Ein laufender Download wird dabei
  abgebrochen und die unvollständige Datei gelöscht. Bereits fertige Dateien bleiben erhalten.
- **Erledigte entfernen** räumt fertige und fehlgeschlagene Einträge aus der Liste.

Die Warteliste bleibt über Neustarts des Add-ons erhalten; ein unterbrochener Download
beginnt nach dem Neustart von vorn.

## Konfiguration

```yaml
design: modern
theme: dark
download_dir: /media/downloads
```

| Option         | Beschreibung                                                                          |
| -------------- | ------------------------------------------------------------------------------------- |
| `design`       | `modern`: zentrierte Suchleiste mit Dropdown-Liste. `terminal`: klassischer Terminal-Look, Eingabezeile unten links, Liste darüber. |
| `theme`        | `dark` oder `light`.                                                                   |
| `download_dir` | Zielordner. `/media/...` (im Medien-Browser sichtbar) oder `/share/...`.               |
Schlüssel gibt es hier keine mehr: den **Zugangscode** und die Daten für iMessage trägst du im
**Fabians-HA-Master** ein. Der Downloader holt sie sich beim Start dort ab.

Nach einer Änderung das Add-on neu starten und die Seite neu laden.

## Zugriff

Die Oberfläche ist über die Home-Assistant-Seitenleiste erreichbar und zusätzlich im Heimnetz
unter `http://<home-assistant-ip>:8099` (ohne Anmeldung; den Port kannst du im Reiter
**Netzwerk** ändern oder leeren, um das abzuschalten). Andere Add-ons erreichen den Downloader
auch intern unter `http://<hostname>:8099` (Hostname siehe Reiter **Info**).

**Aus dem Internet** (z. B. per Cloudflare Tunnel unter deiner Domain) fragt der Downloader
nach dem **Zugangscode** (im Master unter „Zugangscode für Gäste“), einmal pro Gerät. Ist kein
Code gesetzt, ist der Zugriff aus dem Internet gesperrt. Heimnetz, Home Assistant und der
Assistent brauchen keinen Code. Anleitung: [Über das Internet erreichbar machen](https://github.com/fvh02/Fabians-HA-Addons/blob/HEAD/TUNNEL.md)

## iMessage über deinen Assistenten

### Benachrichtigungen

Laufen im Master Inkbox-API-Key und deine Handynummer, schickt der Downloader über den Master
eine iMessage, sobald ein Download fertig ist oder fehlschlägt:

> ✅ Download fertig: Ubuntu 24.04 Desktop.iso (500,0 MB)


### Status abfragen und Links hinzufügen

Das übernimmt **Fabians-HA-Assistent** mit seinem `downloader`-Befehl. Er erreicht den
Downloader über den Master – einzurichten ist nichts.

Die Endpunkte:

| Methode  | Pfad                | Zweck                                                         |
| -------- | ------------------- | ------------------------------------------------------------- |
| `GET`    | `/api/status`       | Status inkl. fertigem Text im Feld `summary` für die Antwort. |
| `POST`   | `/api/items`        | Links hinzufügen: `{"url": "https://… https://…"}`             |
| `DELETE` | `/api/items/<id>`   | Eintrag entfernen bzw. laufenden Download abbrechen.          |

Beispiel für `summary`:

```
⬇️ Ubuntu 24.04 Desktop.iso: 42 % von 500,0 MB, 1,2 MB/s
⏳ 2 in der Warteschlange: backup.tar.gz, video.mp4
✅ 3 fertig
```
