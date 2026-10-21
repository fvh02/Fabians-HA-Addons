# Fabians-HA-Urlaub

Plant euren Urlaub gemeinsam – jeder am eigenen Handy.

## So geht's

1. **Urlaub erstellen:** Name, Ziel und Reisezeit eingeben. Du bekommst einen 6-stelligen **Code**.
   Steht das Ziel noch nicht fest, lass es leer – dann startet gleich die Abstimmung „Wo geht's hin?“.
2. **Freunde einladen:** „📨 Einladung teilen“ schickt Code und Link in den Gruppenchat. Die anderen
   tragen nur ihren Namen ein und sind dabei.
3. **👥 Leute:** Jeder tippt an, was er trinkt und isst – 🍺 Bier, 🥃 Vodka & Schnaps, 🍷 Alkohol,
   🥩 Fleisch usw. (✓ ja / durchgestrichen nein / ? offen). „Kein Alkohol“ schließt automatisch Bier,
   Wein und Schnaps aus. Eigene Kategorien (z. B. Cocktails, Energydrinks, Vegan) lassen sich anlegen.
4. **🏠 Unterkunft:** Airbnb-Links (oder Booking & Co.) einfügen. Das Add-on liest Titel, Bild,
   Gäste, Betten, Bewertung und Lage aus und schaut nach, was in der Nähe ist (Zentrum, Strand,
   Supermarkt, Lokale, Bus). Mit dem Gesamtpreis wird der Preis pro Person und Nacht berechnet.
   **„✨ Beste 3 vorschlagen“** lässt Claude Lage, Komfort und Preis bewerten und die drei besten
   empfehlen. Jeder kann mit 💚 abstimmen.
5. **📍 Spots:** Sucht coole Orte in der Nähe – auch unbekannte Geheimtipps (💎): Buchten,
   Aussichtspunkte, Wasserfälle, Ruinen, kleine Bars … Die Orte kommen aus OpenStreetMap und
   Wikipedia, Claude wählt aus und beschreibt sie. Wünsche („Schnorcheln, Sonnenuntergang“) helfen.
6. **🗳️ Abstimmen:** Fertige Fragen mit einem Tipp starten – „Wo geht's hin?“, „Was für ein Urlaub?“
   (Campen, Städtetrip, Strand, Wandern, Roadtrip …), „Wie kommen wir hin?“, „Wie wollen wir wohnen?“,
   „Wann passt es euch?“, Budget – oder eine eigene Frage stellen. Alle können Antworten vorschlagen;
   man sieht, wer wofür gestimmt hat. Wer die Abstimmung gestartet hat (oder den Urlaub erstellt hat),
   kann sie beenden. Beim Ziel übernimmt „📍 Als Ziel übernehmen“ den Favoriten als Urlaubsziel.
7. **🧾 Kasse:** Kassenzettel fotografieren – Claude liest jeden Artikel, erkennt Bier, Schnaps,
   Fleisch usw. und teilt automatisch auf: Bier zahlen nur die Biertrinker, Brot und Wasser alle.
   Jeden Artikel kann man antippen und ändern (Kategorie, Preis, wer mitzahlt). Ausgaben ohne Bon
   (Tanken, Fähre) lassen sich von Hand eintragen. Unten steht, wer wem wie viel überweisen muss.

## Anmelden mit Apple oder Google (optional)

Ohne Konto funktioniert alles mit Code und Name. Mit Konto hat jeder seine Urlaube auf jedem Gerät –
Handy, Tablet, Laptop – ohne den Code noch einmal einzugeben. Die erste Anmeldung legt das Konto an.

Die Anmeldung braucht die **Internet-Adresse** des Urlaubsplaners (z. B. `https://urlaub.deine-domain.de`,
siehe [TUNNEL.md](../TUNNEL.md)); im Heimnetz und in Home Assistant gibt es die Knöpfe nicht. Die
Zugangsdaten gehören in den **Fabians-HA-Master** unter **Anmeldung (Urlaub)** – nicht in dieses Add-on.

**Google** (kostenlos):
1. [console.cloud.google.com](https://console.cloud.google.com) → Projekt anlegen → **APIs & Dienste →
   OAuth-Zustimmungsbildschirm**: Typ „Extern“, App-Name „Urlaubsplaner“, veröffentlichen.
2. **Anmeldedaten → Anmeldedaten erstellen → OAuth-Client-ID**, Typ **Webanwendung**.
3. Autorisierte Weiterleitungs-URI: `https://urlaub.deine-domain.de/auth/google/callback`.
4. Client-ID und Client-Secret im Master eintragen.

**Apple** (braucht das Apple Developer Program, 99 €/Jahr):
1. [developer.apple.com](https://developer.apple.com/account) → **Identifiers → App IDs**: neue App-ID mit
   „Sign in with Apple“.
2. **Identifiers → Services IDs**: neue Services-ID (z. B. `de.deinname.urlaub`), „Sign in with Apple“
   einschalten → Configure: Primary App ID von oben, Domain `urlaub.deine-domain.de`, Return-URL
   `https://urlaub.deine-domain.de/auth/apple/callback`.
3. **Keys**: neuen Schlüssel mit „Sign in with Apple“ anlegen, die **.p8-Datei** herunterladen (geht nur einmal).
4. Im Master eintragen: Services-ID, Team-ID (oben rechts im Developer-Konto), Key-ID und den Inhalt der .p8-Datei.

Der Master startet den Urlaubsplaner danach neu; die Knöpfe erscheinen auf der Startseite.

## Einrichtung

- **Anthropic-API-Key** (console.anthropic.com → API Keys) im **Fabians-HA-Master** unter
  **Claude → Anthropic-API-Key** eintragen – der Master startet den Urlaubsplaner neu. Ohne
  Key funktionieren Planung, Abstimmungen und Kasse trotzdem – nur Kassenzettel-Erkennung,
  Unterkunft-Vergleich und Spot-Vorschläge nicht.
- **Modell** (Einstellungen dieses Add-ons): Standard ist `claude-opus-5-5` (beste Erkennung). Etwa halb so teuer:
  `claude-sonnet-5-5`.
- Ungefähre Kosten mit dem Standardmodell: ein Kassenzettel 3–6 Cent, ein Unterkunft-Vergleich
  3–8 Cent, eine Spot-Suche 8–15 Cent.

## Für Mitreisende ohne Home Assistant

Im Heimnetz `http://<home-assistant-ip>:8100` öffnen (Port im Reiter **Netzwerk** änderbar).
Unterwegs geht es über einen Cloudflare-Tunnel wie beim Spieleabend. Ohne Code und Beitritt
sieht niemand einen Urlaub.

## Gut zu wissen

- Airbnb blockiert manchmal automatische Abrufe. Dann einfach unter „Angaben ergänzen“ Titel,
  Preis, Betten und Adresse eintragen – die Lage wird über die Adresse bestimmt.
- Kassenzettel-Fotos werden im Add-on gespeichert (in Home-Assistant-Backups enthalten) und
  zum Auslesen an Claude geschickt.
- Spot-Vorschläge vor Ort kurz prüfen (Öffnungszeiten, Zugang).
