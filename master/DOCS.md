# Fabians-HA-Master

Das Haupt-Add-on: **alle Schlüssel und Tokens an einem Ort** – und die Brücke zwischen den
anderen Fabians-HA-Add-ons. Die anderen Add-ons haben keine Felder für Schlüssel mehr; sie holen
sich beim Start beim Master genau das, was sie brauchen.

## Einrichtung

1. **Fabians-HA-Master** installieren, „Beim Booten starten“ einschalten und **starten**.
   Er startet beim Hochfahren vor den anderen Add-ons.
2. In der Seitenleiste **Master** öffnen.
3. Hast du noch die alten Add-ons (Inkbox Claude Gateway, Krypto-Trader, 3D-Druck, Downloader,
   Video-Downloader, Spieleabend aus den alten Repositories)? Dann auf **„Schlüssel aus den
   alten Add-ons übernehmen“** klicken – fertig. Sonst die Felder ausfüllen:

| Bereich | Wofür |
|---|---|
| iMessage (Inkbox) | API-Key, Identität und deine Handynummer – für den Assistenten und alle Meldungen der Add-ons |
| Claude | Claude-Token oder Anthropic-API-Key für den Assistenten (nicht nötig mit importierter claude.ai-Anmeldung) |
| Apple-Kalender | Apple-ID und App-Passwort (optional) |
| eBay | Client-ID, Client-Secret, Postleitzahl (optional) |
| 3D-Drucker | IP, Seriennummer, LAN-Zugangscode des Bambu Lab P1S |
| Krypto-Börse | API-Key/Secret – nur für Echtgeld, **nur Handelsrecht, keine Auszahlungen** |
| Zugangscodes | Code für Downloader/Videos aus dem Internet und Code für den Spieleabend |

4. **Speichern.** Der Master startet die laufenden Add-ons, die einen geänderten Schlüssel
   nutzen, selbst neu. Oben siehst du, welche Add-ons verbunden sind und ob noch etwas fehlt.
5. Mit **Test-iMessage senden** und **Claude testen** prüfst du die Verbindung.

## Sicherheit

- Gespeicherte Schlüssel werden **nie wieder angezeigt** (nur „✓ gesetzt“). Ändern oder löschen
  geht jederzeit.
- Die Seite ist nur über Home Assistant erreichbar, nicht im Heimnetz.
- Jedes Add-on bekommt **nur seine eigenen** Schlüssel. Der Master erkennt es an seiner Adresse im
  internen Add-on-Netz; fremde Add-ons und Geräte bekommen nichts. Die Börsen-Keys bekommt nur der
  Krypto-Trader, die Druckerdaten nur der 3D-Druck.
- Ob der Krypto-Trader mit echtem Geld handelt, entscheidest weiterhin nur du in seinen eigenen
  Optionen (`mode` und Echtgeld-Bestätigung) – nicht der Master und nicht Claude.
- Der Assistent darf den Master nicht anfassen und liest keine Schlüssel aus ihm.
- Die Schlüssel liegen im privaten Speicher des Add-ons (`/data`) und sind Teil deiner
  Home-Assistant-Backups – verschlüssele die Backups (Standard in Home Assistant).

## Brücke

- **iMessage:** Downloader, 3D-Druck und Krypto-Trader schicken ihre Meldungen über den Master an
  deine Handynummer – keiner von ihnen braucht den Inkbox-Key.
- **Claude:** Der Krypto-Trader fragt Claude über den Master; der gibt die Frage an den Assistenten
  weiter, der mit seiner Anmeldung antwortet.
- **Assistent → Add-ons:** Der Assistent erreicht Downloader, 3D-Druck und Krypto-Trader über den
  Master. Adressen wie `http://afcf546d-krypto:8094` musst du nirgends mehr eintragen.

## Fehlersuche

- **Ein Add-on wartet „auf Fabians-HA-Master“:** Master installieren und starten.
- **„Nur für Fabians-HA-Add-ons“ im Protokoll:** Das Add-on stammt aus einem anderen Repository
  (z. B. die alten Add-ons). Nur Add-ons aus Fabians-HA-Addons werden bedient.
- **Ein Add-on fehlt in der Liste:** Es ist nicht installiert oder aus einem anderen Repository.
