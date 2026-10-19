# Changelog

## 1.2.1

- Kennt das neue Add-on **Fabians-HA-Karte** (iMessages und Claude-Abgleich über den Master); die
  Apple-ID geht auch an die Karte, damit sie bei „Wo ist?“ einen frischen Standort anfordern kann.

## 1.2.0

- **Inkbox-Fehler verständlich:** Statt nur „Inkbox meldet Fehler 401“ steht jetzt da, was los ist
  und was zu tun ist (z. B. API-Key falsch oder gelöscht, Nummer noch nicht verbunden, Tageslimit).
- Beim Speichern eines neuen Inkbox-API-Keys prüft der Master ihn sofort bei Inkbox.
- API-Keys, Secrets und Tokens werden beim Speichern von Zeilenumbrüchen, Leerzeichen und
  Anführungszeichen aus dem Kopieren befreit – auch bereits gespeicherte.

## 1.1.0

- Neue Add-ons im Repository: **Fabians-HA-Bestenliste**, **Fabians-HA-Browser** und
  **Fabians-HA-Urlaub** und **Fabians-HA-Gedächtnis** – der Master kennt sie und gibt ihnen ihre Schlüssel.
- Neue Felder: **Paketverfolgung** (17TRACK, DHL) und **Stundenplan 1/2 (WebUntis)** für den
  Assistenten, **E-Mail (Spieleabend)** für die Bestätigungscodes der Spieleabend-Konten.
- Der Anthropic-API-Key gilt auch für den Urlaubsplaner, der Spieleabend-Code auch für die
  Bestenliste.
- „Schlüssel übernehmen“ kennt auch die neuen Optionen der alten Add-ons (Paket-Schlüssel,
  Stundenpläne, SMTP, Urlaubsplaner-Key).

## 1.0.0

- Erste Version: alle Schlüssel und Tokens an einem Ort (Seite in der Seitenleiste), ein Klick
  übernimmt die Schlüssel aus den alten Add-ons. Gespeicherte Schlüssel werden nie wieder angezeigt.
- Jedes Add-on bekommt nur seine eigenen Schlüssel; erkannt wird es an seiner Adresse im
  Add-on-Netz. Nach einer Änderung startet der Master die betroffenen Add-ons selbst neu.
- Brücke: iMessages für alle Add-ons, Claude-Fragen (Krypto-Trader) über den Assistenten und
  der Weg vom Assistenten zu Downloader, 3D-Druck und Krypto-Trader – ohne Adressen und Ports.
