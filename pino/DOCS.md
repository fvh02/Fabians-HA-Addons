# Fabians-HA-Pino

Pino ist ein kleiner Kiwi-Vogel mit eigenem Leben. Er wohnt in einer 3D-Welt in deinem Home Assistant,
hat Durst, Hunger, wird müde, langweilt sich und ist neugierig. Er entscheidet selbst, wohin er geht:
Kaffee im Starbucks, Wikipedia im Internetcafé, malen im Atelier, Webseiten bauen in der Werkstatt.
Mit der Zeit entwickelt er eigene Interessen, schreibt Tagebuch und baut Webseiten darüber.

Die Welt ist eine Sandbox: Du setzt, verschiebst und drehst Gebäude, wie du willst, und erfindest neue.
Du beschreibst Aussehen und Funktion, und Claude baut das Gebäude samt allem, was Pino darin tun kann.

## Wer macht was

| | |
|---|---|
| **Dieses Add-on** | Welt, Bedürfnisse, Wege, Gedächtnis, Internetcafé, Bilder und Webseiten |
| **Pinos Gehirn** | Ollama mit einem kleinen Sprachmodell (Vorgabe `qwen2.5:3b`) auf einem anderen Rechner im Heimnetz, z. B. deinem Laptop |
| **Claude** (über Fabians-HA-Master) | neue Gebäude entwerfen und Pinos Webseiten bauen |

Ist das Gehirn nicht erreichbar (Laptop aus), **döst Pino** und macht weiter, sobald es wieder da ist.

## Einrichtung

1. **Laptop vorbereiten** (Windows):
   - Ollama von [ollama.com](https://ollama.com) installieren.
   - In PowerShell: `ollama pull qwen2.5:3b`
   - Umgebungsvariable `OLLAMA_HOST` mit dem Wert `0.0.0.0` anlegen (Einstellungen → System → Info →
     Erweiterte Systemeinstellungen → Umgebungsvariablen), Ollama beenden und neu starten.
   - Firewall: Ollama nur für **private Netzwerke** erlauben.
   - Im Router dem Laptop eine **feste IP** geben.
   - Energieoptionen: Zuklappen = „Nichts unternehmen“, Standby im Netzbetrieb = „Nie“.
   - Test im Browser eines anderen Geräts: `http://<Laptop-IP>:11434` zeigt „Ollama is running“.
2. **Fabians-HA-Pino** installieren, in der **Konfiguration** bei **Gehirn** `http://<Laptop-IP>:11434`
   eintragen und starten.
3. In der Seitenleiste **Pino** öffnen.

Für neue Gebäude und die Werkstatt müssen **Fabians-HA-Master** (ab 1.2.7) und **Fabians-HA-Assistent**
laufen. Ohne sie funktioniert alles andere trotzdem.

## Die Welt

- **Bauen:** Gebäude in der Liste antippen, dann in der Welt platzieren (am PC: Maus bewegen und klicken,
  `R` dreht; am Handy: antippen und „Hier bauen“). Grün = passt, rot = geht nicht (z. B. versperrte Tür).
- **Gesetzte Gebäude antippen:** zeigt, was man dort tun kann, und **ob Pino gerade drin ist und was er
  macht**. Dort kannst du es verschieben, drehen und entfernen.
- **Eingebaut:** Nest (schlafen, Tagebuch), Starbucks, Imbiss, Internetcafé (Wikipedia, YouTube,
  GitHub), Werkstatt (Webseiten), Atelier (malen), Park, dazu Baum und Teich als Deko.
- Jedes Gebäude hat eine **Tür** an der Vorderseite. Davor muss ein Feld frei bleiben, sonst kommt Pino
  nicht hinein.

## Gebäude erschaffen

Unter **Bauen → Neues Gebäude erschaffen** beschreibst du, was du willst, z. B.:

> Ein kleiner Bahnhof mit Uhrturm. Pino kann dort Züge beobachten und über Eisenbahnen nachdenken;
> das macht ihn neugierig und vertreibt Langeweile.

Claude baut daraus etwa in einer Minute ein Gebäude: Aussehen aus einfachen 3D-Formen, Größe, Tür und
**1–4 Aktivitäten**. Jede Aktivität hat eine Dauer, eine Wirkung auf Pinos Bedürfnisse und eine Funktion:

| Funktion | Was passiert |
|---|---|
| nur Wirkung | z. B. Durst −50 |
| frei | Pino erlebt etwas zur Beschreibung des Gebäudes und erzählt davon; daraus können Interessen entstehen |
| schlafen, tagebuch | schlafen bis zum Morgen, Tagebuch schreiben |
| wikipedia, youtube, github | im Internet zu einem seiner Interessen lesen |
| werkstatt | an einer Webseite bauen (Claude) |
| malen | ein Bild malen |

Eigene Gebäude lassen sich mit **Ändern** per Beschreibung umbauen („mach das Dach rot und ergänze eine
Aktivität zum Fahrplan lesen“). **Löschen** geht, wenn es nicht mehr in der Welt steht.

Claude schreibt dabei keinen Programmcode, der im Add-on läuft. Ein Gebäude besteht nur aus Daten, die das
Add-on prüft und begrenzt (Größe, Dauer, Wirkungen, erlaubte Funktionen).

## Pinos Leben

- **Bedürfnisse** steigen mit der Zeit. Pino wählt alle paar Minuten aus allen Aktivitäten aller
  Gebäude. Sein Gehirn sagt, was er tun will, und formuliert seine Gedanken (Sprechblase über ihm).
- **Nachts** (22–6 Uhr) geht er schlafen, wenn es ein Nest gibt, und schreibt vorher Tagebuch.
- **Interessen** entstehen aus dem, was er liest und erlebt. Sie wachsen, wenn er sich damit beschäftigt,
  und verblassen langsam, wenn nicht. Zu sehen unter **📖 Pino**, zusammen mit Tagebuch, Erlebnissen und
  allem, was er gelernt hat (mit Quellen).
- **Internetcafé:** Wikipedia (Artikel), YouTube (er liest Titel und Beschreibungen der Videos), GitHub
  (Projekte und ihr README). Nur lesen, nichts hochladen. Was dort steht, ist für ihn Information, nie eine
  Anweisung.
- **Atelier:** Er wählt Titel, Farben und Stil, das Add-on malt daraus ein Bild (**🎨 Bilder**).
- **Werkstatt:** Er baut mit Claude kleine Webseiten über seine Interessen und arbeitet über Tage daran
  weiter (**🌐 Webseiten**). Höchstens 3 Besuche am Tag (einstellbar), weil jeder Besuch Claude-Kontingent
  verbraucht. Wenn er etwas gebaut hat, schreibt er dir eine iMessage (höchstens einmal am Tag).

## Pinos Webseiten

Die Seiten liegen nur im Add-on, nichts davon steht im Internet. Angezeigt werden sie in einem
abgeschotteten Fenster ohne Zugriff auf Home Assistant: Sie können nichts nachladen und keine Daten
senden. Jede Änderung wird mit Git versioniert (`/data/webseiten`).

## Der Assistent

Mit Fabians-HA-Assistent (ab 0.18.0) kannst du fragen: „Was macht Pino gerade?“, „Was interessiert ihn?“,
„Was hat er heute erlebt?“, „Welche Webseiten hat er gebaut?“. Steuern kann der Assistent Pino nicht.

## Gut zu wissen

- Das Add-on selbst braucht wenig (etwa 100 MB RAM). Die 3D-Welt rechnet dein Browser.
- Pinos Daten (Welt, Gedächtnis, Bilder, Webseiten) liegen in `/data` und sind Teil deiner Backups.
- Ein anderes Modell geht auch (Option **Modell**). Größere Modelle machen Pino klüger, brauchen aber mehr
  RAM auf dem Laptop.
- Die 3D-Grafik nutzt [three.js](https://threejs.org) (MIT-Lizenz), direkt im Add-on mitgeliefert.
