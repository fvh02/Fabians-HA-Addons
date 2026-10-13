# Fabians-HA-Assistent

Dein Assistent per iMessage und E-Mail (früher „Inkbox Claude Gateway“). Dieses Add-on lässt den Inkbox-Gateway dauerhaft auf deinem Home Assistant
laufen. Kommt eine E-Mail oder iMessage für deine Inkbox-Identität an, startet
der Gateway eine Claude-Code-Sitzung, die im selben Chat antwortet.

Basis: [inkbox-ai/claude-code-plugin](https://github.com/inkbox-ai/claude-code-plugin),
fest auf einen Commit gepinnt (siehe `Dockerfile`).

Voraussetzung: Home Assistant **OS** oder **Supervised** auf `amd64` oder `aarch64`.

## Installation

1. *Einstellungen → Add-ons → Add-on Store* → oben rechts **⋮ → Repositories**.
2. `https://github.com/fvh02/Fabians-HA-Addons` hinzufügen und schließen.
3. Zuerst **Fabians-HA-Master** installieren und starten, dann **Fabians-HA-Assistent**.

## Einrichtung

**Alle Schlüssel trägst du nur noch im Fabians-HA-Master ein** (Seitenleiste → Master):
Inkbox-API-Key, Inkbox-Identität, Claude-Token oder Anthropic-API-Key, Apple-ID und
App-Passwort, eBay-Keys und deine Handynummer. Der Assistent holt sie sich beim Start
selbst ab. Änderst du dort etwas, startet der Master den Assistenten automatisch neu.

Hier im Tab **Konfiguration** stehen nur noch Einstellungen:

| Feld | Bedeutung |
|---|---|
| Antwortsprache | Sprache, in der Claude antwortet (Standard: Deutsch). Schreibst du in einer anderen Sprache oder schickst eine Datei in einer anderen Sprache, antwortet Claude in dieser. „Automatisch“ = keine Vorgabe. |
| claude.ai-Anmeldung verwenden | Siehe [claude.ai-Connectoren](#claudeai-connectoren). |
| Kalender für KI-Termine | Standard `Added by AI Agent`. Alle Termine, die Claude anlegt, landen dort. |
| Sprachnachrichten | Whisper-Modell für Sprachnachrichten, Standard `small`. `aus` schaltet es ab. |
| Arbeitsordner | Standard `/share/claude-workspace`. |
| Voice AI | Nur wenn die Identität eine Telefonnummer hat. |
| Claude-Modell | Optional, leer = Standard. |
| Add-ons verwalten | Siehe [Add-ons verwalten](#add-ons-verwalten). |

Dann im Tab **Info** „Beim Booten starten“ und „Watchdog“ aktivieren und **Starten**.
Solange der Master nicht läuft, wartet der Assistent und schreibt das ins Protokoll.

**Umzug vom alten Inkbox Claude Gateway:** Im Master auf „Schlüssel aus den alten Add-ons
übernehmen“ klicken, dann das **alte Gateway stoppen** und erst danach den Assistenten
starten – zwei Gateways mit derselben Identität nehmen sich gegenseitig die Nachrichten
weg. Eine importierte claude.ai-Anmeldung musst du einmal neu importieren (siehe unten).

## Apple-Kalender

Claude kann Termine in deinem Apple-Kalender (iCloud) anlegen, anzeigen und
löschen, z. B. per Nachricht „Trag mir morgen um 15 Uhr Zahnarzt ein“.

1. Auf [account.apple.com](https://account.apple.com) anmelden →
   **Anmeldung und Sicherheit → App-spezifische Passwörter** → neues Passwort
   erzeugen (Name z. B. „Home Assistant“). Dafür muss die
   Zwei-Faktor-Authentifizierung aktiv sein.
2. Im **Fabians-HA-Master** unter **Apple-Kalender** eintragen:
   - **Apple-ID:** die E-Mail-Adresse deiner Apple-ID
   - **App-Passwort:** das eben erzeugte Passwort (`xxxx-xxxx-xxxx-xxxx`),
     **nicht** dein normales Apple-Passwort
3. Hier im Assistenten unter **Konfiguration** bei **Kalender für KI-Termine** den Namen des
   Kalenders eintragen, in den alles kommt, was Claude anlegt (Standard `Added by AI Agent`).
   Den Kalender vorher in der Kalender-App anlegen, genau mit diesem Namen.
4. Im Protokoll steht `[assistent] Apple-Kalender: aktiv (neue Termine in: Added by AI Agent)`.

Termine aus allen Kalendern kann Claude lesen und auf Nachfrage löschen. Neue
Termine landen immer im KI-Kalender, so erkennst du sie an dessen Farbe.

Das Kalender-Werkzeug darf Claude ohne Rückfrage benutzen. Alle anderen
Befehle fragen weiterhin per Nachricht nach. Zum Abschalten die beiden Felder
im Master löschen. Das App-Passwort kannst du jederzeit auf account.apple.com widerrufen.

## Downloads

Claude kann **Fabians-HA-Downloader** steuern: per Nachricht den Status abfragen („Wie weit
sind meine Downloads?“) oder einen Link schicken, der dann heruntergeladen wird.

Einrichtung: keine. Ist der Downloader installiert, verbindet der Master beide automatisch.
Im Protokoll steht `[assistent] Downloader: aktiv (über Fabians-HA-Master)`. Installierst du
ihn später, den Assistenten einmal neu starten.

Das `downloader`-Werkzeug darf Claude ohne Rückfrage benutzen. Links fügt Claude nur
hinzu, wenn du sie selbst schickst, nicht aus E-Mails oder weitergeleiteten Nachrichten.
Benachrichtigungen bei fertigen Downloads verschickt der Downloader über den Master.

## Add-ons verwalten

Claude kann per Nachricht deine Home-Assistant-Add-ons verwalten, z. B.:

- „Welche Add-ons haben ein Update?“ / „Aktualisiere alle Add-ons“
- „Füge das Repository https://github.com/… hinzu“ – Claude sagt dir danach, welche Add-ons es anbietet
- „Installiere den Video-Downloader und starte ihn“
- „Entferne das Repository …“ (geht nur, wenn keine Add-ons daraus mehr installiert sind)

Anschauen darf Claude ohne Rückfrage. **Jede Änderung** (Repository hinzufügen/entfernen,
installieren, aktualisieren, deinstallieren, starten/stoppen) fragt dich vorher per Nachricht
(„1 = einmal erlauben, 2 = für diese Unterhaltung erlauben, 3 = ablehnen“). Claude handelt nur
auf deine eigene Nachricht hin, nie wegen einer E-Mail oder Webseite.

Dafür hat der Assistent Zugriff auf den Home-Assistant-Supervisor (Rolle „manager“). Home
Assistant zeigt deshalb eine niedrigere Sicherheitsbewertung an. Abschalten: Option
**Add-ons verwalten** aus.

Den Assistenten selbst aktualisierst du am besten in Home Assistant: ein Update startet ihn neu
und würde Claude mitten in der Antwort unterbrechen. Den **Master** fasst Claude nie an und
liest dort auch keine Schlüssel.

## eBay-Suche und Preisalarm

Claude sucht für dich auf eBay.de das günstigste Angebot, z. B.:

- „Such mir ein iPhone 15 128 GB, max. 450 €“
- „Gibt's die Sony WH-1000XM5 gebraucht unter 200 €?“
- „Sag mir Bescheid, wenn eine PS5 Slim unter 350 € auftaucht“ (Preisalarm)

Claude schickt dir die drei besten Angebote mit Gesamtpreis inkl. Versand, Zustand,
Verkäuferbewertung und Link. Zubehör, defekte Geräte und schlecht bewertete Verkäufer
filtert es vorher heraus. Auffällig billige Angebote markiert es als Warnung.
**Kaufen tust du selbst** über den Link. Claude kauft nie, bietet nie und fragt nie nach
Zahlungs- oder Anmeldedaten.

Einrichtung (einmalig, kostenlos):

1. Auf [developer.ebay.com](https://developer.ebay.com) mit deinem eBay-Konto ein
   Entwicklerkonto anlegen (Join). Die Freischaltung kann ein bis zwei Werktage dauern.
2. Unter **Application Keys** einen Namen eingeben und das **Production**-Keyset erstellen.
3. Falls eBay nach der „Marketplace Account Deletion Notification“ fragt:
   **Exempted** wählen („I do not persist eBay data“) und bestätigen.
4. Im **Fabians-HA-Master** unter **eBay** eintragen:
   - **Client-ID** = *App ID (Client ID)* aus dem Production-Keyset
   - **Client-Secret** = *Cert ID (Client Secret)*
   - **Postleitzahl** (für genaue Versandkosten, optional)
   Preisalarme gehen an die Handynummer, die im Master unter iMessage steht.
5. Speichern – der Master startet den Assistenten neu. Im Protokoll steht `[assistent] eBay: aktiv`.

Preisalarme prüft der Assistent alle 30 Minuten. Neue passende Angebote kommen per iMessage,
jedes nur einmal. „Welche Preisalarme habe ich?“ und „Lösch den PS5-Alarm“ gehen auch.

## 3D-Druck

Mit **Fabians-HA-3D-Druck** sucht Claude Modelle auf Printables, schickt dir Bilder, slict für
deinen Bambu Lab P1S und druckt nach deinem „Ja“. Status, Kamerabild, Pause und Stopp gehen
auch per Nachricht. Die Druckerdaten trägst du im Master ein; die Verbindung macht der Master.

## Krypto-Trader

Mit **Fabians-HA-Krypto-Trader** kannst du per Nachricht fragen, wie es läuft („Wie steht der
Krypto-Trader?“), dir Entscheidungen erklären lassen und das Trading stoppen („Trading stopp“,
„Not-Aus“). Weitermachen und Zusatz-Entscheidungen fragt Claude vorher bei dir nach.

**Claude-Brücke:** Der Trader nutzt für seine Entscheidungen die Claude-Anmeldung des
Assistenten, damit du keinen zweiten Token brauchst. Dafür läuft im Assistenten ein kleiner
Dienst (Port 8093, nur im internen Add-on-Netz), der reine Fragen ohne Werkzeuge außer Websuche
an Claude weitergibt. Nur der Master darf ihn aufrufen; den Schlüssel dafür teilen sich nur
Master und Assistent.

## claude.ai-Connectoren

Mit dem OAuth-Token aus `claude setup-token` kann Claude nur antworten. Deine
auf claude.ai hinzugefügten Connectoren (z. B. Notion, Spotify) lädt Claude Code
nur mit einer **vollen claude.ai-Anmeldung**. Die erstellst du einmal auf einem
PC und gibst sie an das Add-on weiter:

1. **Samba share** installieren und starten (falls noch nicht geschehen).
2. Auf deinem PC Claude Code starten (`claude`), dort `/login` eingeben, dein
   Claude-Konto wählen und im Browser bestätigen. Danach `/exit`.
3. Die Anmeldedatei in die Home-Assistant-Freigabe kopieren und vom PC
   entfernen. Windows PowerShell:
   ```powershell
   New-Item -ItemType Directory -Force \\homeassistant.local\share\claude-login | Out-Null
   Move-Item "$env:USERPROFILE\.claude\.credentials.json" \\homeassistant.local\share\claude-login\ -Force
   ```
   Linux: `~/.claude/.credentials.json` nach `share/claude-login/` verschieben.
   macOS speichert die Anmeldung im Schlüsselbund, dort klappt das nicht.
4. Add-on neu starten. Im Protokoll steht
   `[assistent] claude.ai-Anmeldung importiert.` und
   `Claude: claude.ai-Anmeldung (Connectoren verfügbar)`. Die Datei in der
   Freigabe wird dabei gelöscht.

Wichtig:
- Die Datei vom PC **verschieben**, nicht kopieren, und dort **nicht** `/logout`
  ausführen. Zwei Geräte mit derselben Anmeldung würden sich gegenseitig
  abmelden, und `/logout` widerruft sie. Willst du Claude Code am PC weiter
  nutzen, melde dich dort danach einfach neu mit `/login` an.
- Connector-Aufrufe fragen wie andere Werkzeuge zuerst per Nachricht nach.
  Mit `2`/`always` erlaubst du einen Connector für die laufende Unterhaltung.
- Zurück zum OAuth-Token: **claude.ai-Anmeldung verwenden** ausschalten und neu
  starten. Das löscht die Anmeldung im Add-on.

## Sprachnachrichten

Schickst du per iMessage eine Sprachnachricht, wird sie direkt auf deinem Home
Assistant mit Whisper in Text umgewandelt. Claude behandelt den Text so, als
hättest du ihn getippt, z. B. „Trag mir Freitag 18 Uhr Kino ein“. Die Audios
verlassen dein Gerät nicht.

- Beim ersten Start lädt das Add-on das Modell herunter. Das Protokoll zeigt
  danach `[whisper] {"ok": true, ...}`.
- Modelle: `tiny`/`base` sind schnell, aber ungenauer. `small` ist ein guter
  Kompromiss (ca. 500 MB, ~1 GB RAM). `medium`/`turbo` sind am genauesten, brauchen
  aber deutlich mehr RAM und Zeit.
- Die Modelle werden nicht in Home-Assistant-Backups gesichert und bei Bedarf
  neu geladen.

## Prüfen

Im Tab **Protokoll** sollte stehen:

- ein JSON-Block mit `"status": "configured"`
- die Ausgabe von `inkbox-claude doctor` mit ✓ bei `INKBOX_API_KEY`,
  `INKBOX_IDENTITY`, `INKBOX_SIGNING_KEY` und `Claude readiness`
- danach die Logs des laufenden Gateways

Dann eine iMessage oder E-Mail an deine Identität schicken. Die Antwort kommt im
selben Chat. `/health` im Chat liefert einen Statusbericht.

## Wissenswertes

- **Signing-Key:** Beim ersten Start erzeugt das Add-on einen neuen
  Webhook-Signing-Key für die Identität. Ein anderer Gateway für dieselbe
  Identität empfängt danach nichts mehr. Spätere Neustarts verwenden den
  gespeicherten Key weiter.
- **Daten** liegen im privaten Add-on-Speicher (`/data`) und bleiben bei
  Neustarts und Updates erhalten. Sie sind Teil deiner Home-Assistant-Backups.
- **Freigaben:** Will Claude Befehle ausführen oder Dateien ändern, schickt dir
  der Gateway eine kurze Zusammenfassung. Antworte mit `1`/`yes`,
  `2`/`always` oder `3`/`no`.
- **Antwortsprache ändern:** Im Tab Konfiguration auswählen, speichern und den
  Assistenten neu starten. Mit `/new` im Chat startest du danach eine frische
  Unterhaltung.
- **„Claude: NOT authenticated“ bei `/health`** ist mit OAuth-Token ein
  Fehlalarm: Diese Anzeige kennt nur API-Key und Login-Datei. Maßgeblich ist
  „Claude readiness ✓“ im Protokoll beim Start.
- **Nachrichten direkt nach dem Start:** Was ankommt, bevor im Protokoll
  `[bridge] ready` steht, erreicht den Gateway nicht. Dann einfach neu senden.
- **Identität wechseln:** Im Master ändern. Der Assistent startet neu und erzeugt
  automatisch einen neuen Signing-Key.
- **Fehler „Bootstrap fehlgeschlagen“:** Meist ein falscher Inkbox-API-Key oder
  ein Key ohne Zugriff auf die angegebene Identität. Details stehen im JSON
  darüber.
