# Fabians-HA-Jarvis

J.A.R.V.I.S. auf deinem Beamer: ein leuchtendes HUD im Iron-Man-Stil. Du sprichst mit Claude, und Jarvis
antwortet mit Stimme. Er kann alles, was dein Assistent kann: Smart-Home-Geräte schalten, Werkbank, Pino, Drucker,
Gedächtnis, Kalender und alle anderen Add-ons.

> Du (OK-Taste auf der Fernbedienung): „Jarvis, mach das Licht im Wohnzimmer gemütlich“
> Jarvis: „Erledigt, Sir. Wohnzimmer auf 30 Prozent, warmweiß.“

## Was du brauchst

- **Fabians-HA-Master ab 1.2.9** und **Fabians-HA-Assistent ab 0.20.0**. Jarvis denkt mit dem Claude deines Assistenten.
- Einen Android-Beamer (Android TV oder normales Android, auch ohne Play Store) im selben WLAN wie Home Assistant.

## Einrichtung

1. Add-on installieren und starten. Beim ersten Start lädt es Sprachmodelle, das dauert eine Minute.
2. In der Seitenleiste **Jarvis** öffnen. Dort stehen die **Adresse** (z. B. `http://192.168.1.10:8107`) und ein **Kopplungscode**.
3. **App auf den Beamer bringen** (`jarvis.apk`, Link auf der Jarvis-Seite):
   - Im Browser des Beamers die APK-Adresse öffnen, *oder*
   - mit der App **Downloader** (Code-Eingabe einer URL), *oder*
   - per USB-Stick: Datei-Manager → `jarvis.apk` → Installieren.
   Android fragt einmal nach „Installation aus unbekannten Quellen“. Erlaube das.
4. App öffnen, Adresse und Code eingeben → **Koppeln**. Fertig.

Jeder Code gilt nur einmal. Gekoppelte Geräte siehst und entfernst du auf der Jarvis-Seite.

## Bedienen

| Wie | Was |
|---|---|
| **Fernbedienung des Beamers** | **OK** → Jarvis hört zu (Beamer braucht ein Mikrofon, z. B. in der Sprachfernbedienung); nochmal **OK** → senden. **Zurück** unterbricht Jarvis. **Menü** → neu koppeln. |
| **Handy** | Jarvis-Seite → **Fernbedienung**, auch in der Home-Assistant-App. Großer Mikrofon-Knopf, Textfeld, Schnellbefehle. |
| **Sprache** | „Stopp“ unterbricht, „Neues Gespräch“ vergisst den Gesprächsverlauf. Nach 15 Minuten Ruhe beginnt Jarvis ohnehin neu. |

Das Bild läuft immer auf dem Beamer, egal von wo du fragst. Die Antwort kommt aus dem Beamer-Lautsprecher und
auf Wunsch zusätzlich am Handy („Antwort auch hier abspielen“).

**Mikrofon am Handy:** Browser erlauben das Mikrofon nur über HTTPS. Öffnest du die Fernbedienung über
`http://…:8107`, tipp ins Textfeld und nutze die **Diktier-Taste 🎤 deiner Tastatur**. In der Home-Assistant-App
über HTTPS (z. B. Nabu Casa) geht der Mikrofon-Knopf direkt.

## Optionen

| Option | Bedeutung |
|---|---|
| `anrede` | Wie Jarvis dich nennt (Standard „Sir“) |
| `stimme` | Piper-Stimme. `de_DE-thorsten-medium` ist eingebaut; andere werden einmal heruntergeladen. |
| `sprechtempo` | 0.7 = langsamer, 1.3 = schneller |
| `spracherkennung` | Whisper-Modell: `tiny` (schnell), `base` (Standard), `small` (genauer, braucht mehr RAM und Zeit) |

Spracherkennung (faster-whisper) und Stimme (Piper) laufen lokal auf deinem Server. Nur die Unterhaltung selbst
geht an Claude.

## Smart Home

Der Assistent hat dafür das neue Werkzeug `haus`: Räume und Geräte finden, schalten, Licht mit Helligkeit und Farbe,
Thermostate, Rollos, Szenen. Türschlösser, Alarmanlage und Garagentore fasst er nur nach deiner ausdrücklichen
Bestätigung an. Das funktioniert auch per iMessage.

## Sicherheit

- Im Heimnetz ist Jarvis nur mit Kopplungscode erreichbar. Pro 10 Minuten sind höchstens 10 Kopplungsversuche erlaubt.
- Port 8107 **nicht** im Router freigeben. Für unterwegs nutzt du die Home-Assistant-App.
