# Changelog

## 1.3.0

- **Urlaub löschen:** Wer den Urlaub erstellt hat, kann ihn unter „⚙️ Urlaub bearbeiten“ für alle
  löschen – mit Unterkünften, Abstimmungen, Kasse und den Fotos der Kassenzettel.

## 1.2.0

- **Mit Apple oder Google anmelden:** Die erste Anmeldung legt das Konto an. Mit Konto sind deine
  Urlaube auf jedem Gerät da – ohne Code. Urlaube, denen du vorher auf diesem Gerät beigetreten bist,
  werden beim Anmelden übernommen. Abmelden und Konto löschen gehen auf der Startseite.
- Ohne Konto geht alles weiter wie bisher mit Code und Name.
- Die Zugangsdaten kommen aus dem **Fabians-HA-Master** (ab 1.2.5, Gruppe „Anmeldung (Urlaub)“).
  Anmelden geht nur über die Internet-Adresse (Cloudflare Tunnel, https).
- Der Kassenbon öffnet sich jetzt direkt in der App statt in einem neuen Tab.

## 1.1.0

- **🗳️ Abstimmen:** neuer Tab mit Umfragen – fertige Fragen (Ziel, Art des Urlaubs, Anreise,
  Unterkunft, Termin, Budget) oder eigene, mit einer oder mehreren Stimmen pro Person. Alle können
  Antworten vorschlagen, das Ergebnis zeigt, wer wofür ist. Der Favorit beim Ziel lässt sich als
  Urlaubsziel übernehmen.
- Das Ziel darf beim Erstellen leer bleiben; dann startet automatisch „Wo geht's hin?“.
- Behoben: „Von“ und „Bis“ liefen auf dem iPhone ineinander. „Bis“ kann außerdem nicht mehr vor „Von“ liegen.
- Behoben: Ort und Datum im Kopf liefen unter den Code-Knopf.

## 1.0.0

- In **Fabians-HA-Addons** als **Fabians-HA-Urlaub**: der Anthropic-API-Key kommt aus
  **Fabians-HA-Master**, Port 8100 (8099 hat der Downloader).
- Erste Version: Urlaub erstellen und per Code beitreten, Kategorien pro Person (Alkohol, Bier,
  Wein, Schnaps, Fleisch, Tabak + eigene), Unterkünfte per Link mit Umgebung und Claude-Vergleich
  (beste 3), Geheimtipps aus OpenStreetMap/Wikipedia, Kassenzettel-Erkennung mit automatischer
  Aufteilung und Ausgleichszahlungen.
