# Changelog

## 3.1.0

- Umgezogen nach **Fabians-HA-Addons** und umbenannt in **Fabians-HA-Spieleabend**.
- Der Zugangscode für Mitspieler kommt aus **Fabians-HA-Master** (eigener Code, getrennt vom
  Downloader-Code).

## 3.0.1

- Beispielname im Namensfeld und Namen in den README-Bildern neutralisiert.

## 3.0.0

- **Vier neue Partyspiele:** Schätzmeister, Wer würde eher …?, Lügenbaron und Punchline – alle
  mit 📺 Fernseher-Modus (ein Gerät wird zum großen Bildschirm).
- **Sechs Trinkspiele:** Ich hab noch nie …, Wahrheit oder Trinken, Trinklotto (geheime Farbe,
  Zahl und Tier – „Alle mit Blau trinken!“), Pyramide, Pferderennen und Ring of Fire.
- **Suche und Filter** auf der Startseite: Spieler, Art, Dauer, Fernseher-Modus und offene Runden
  als Auswahlmenüs; der Browser merkt sich die Filter.
- Spiele, die keine Kartenspiele sind (Kritzelpost, Schnellmaler, Wortgitter, Galgenraten und die
  neuen Spiele), haben eigene Illustrationen statt Spielkarten.
- README mit Bildern aus simulierten Runden.

## 2.6.0

- Neues Spiel **Galgenraten** (1–8 Spieler): eigenes Wort ausdenken oder Zufallswort mit
  Kategorie, abwechselnd Buchstaben raten, Galgen wird Stück für Stück gezeichnet,
  Computer-Spieler, Zeitlimit pro Zug.
- Neues Spiel **Imposter** (3–16 Spieler): geheime Rollenkarte zum Umdrehen, ausgeloste
  Reihenfolge für die Hinweisrunde, Abstimmung am Handy, letzte Chance für den Imposter,
  Punkte über mehrere Runden. Rund 350 Wörter in 16 Kategorien.

## 2.5.0

- Neues Spiel **Wortgitter** für eine Person: das Wort mit 5 Buchstaben in 6 Versuchen erraten,
  mit Wort des Tages und Endlos-Modus, Statistik, Serien, Teilen und Bildschirmtastatur.
  Rund 900 Lösungswörter, knapp 7.000 erlaubte Wörter.
- Behoben: Die unsichtbare Hinweis-Einblendung blockierte Klicks am unteren Bildschirmrand.

## 2.4.0

- Neues Spiel **Schnellmaler** (2–12 Spieler): Einer zeichnet, alle anderen raten am Handy.
  Ein Gerät kann sich im Warteraum per **📺 Host** zum großen Bildschirm machen (z. B. der
  Fernseher): Es zeigt die Zeichnung live, die Wortlücken, Timer, Punkte und Tipps.
  Wortwahl aus drei Begriffen, Buchstaben-Hinweise, „knapp daneben“, Punkte nach Tempo.

## 2.3.0

- Neues Kartenspiel **Farbrausch** (2–10 Spieler): passende Farbe oder Zahl ablegen, mit
  Aussetzen, Richtungswechsel, +2, Farbwahl und +4, „Letzte Karte!“ rufen und andere erwischen.
  Wahlweise eine Runde oder bis 200/500 Punkte, optional Plus-Karten stapeln, mit
  Computer-Spielern und Animationen.

## 2.2.1

- Sicherung: Ist kein Zugangscode gesetzt, werden Aufrufe über Cloudflare (Tunnel/Domain)
  abgewiesen. Das Heimnetz und Home Assistant bleiben ohne Code nutzbar.

## 2.2.0

- **Als App installierbar** (Home-Bildschirm auf iPhone und Android): Vollbild, App-Icon,
  Rücksicht auf Notch und Home-Leiste, Hinweis zum Installieren auf der Startseite.
- **Zugangscode** (Option `access_code`) für Mitspieler außerhalb von Home Assistant – nötig,
  wenn die Spiele aus dem Internet erreichbar sind. Anleitung für Cloudflare Tunnel in der Doku.
- **Einladen**-Knopf im Warteraum: teilt einen Link, der den Spielcode schon ausfüllt.
- Schutz für den Betrieb im Internet: Grenzen für Spielräume, Verbindungen und Nachrichten,
  Sperre nach zu vielen falschen Codes.

## 2.1.0

- Neues Spiel **Kritzelpost** (3–10 Spieler): Stille Post mit Stift. Sätze schreiben,
  zeichnen, erraten und am Ende alle Alben gemeinsam aufdecken. Mit Zeichenfläche
  (14 Farben, 4 Stärken, Radierer, Rückgängig), Timer in drei Tempi oder ohne Zeitlimit,
  Computer-Spielern und nachgemalten Zeichnungen beim Aufdecken.

## 2.0.0

- Aus „Stapeljagd“ wird „Spieleabend“: eine Startseite zur Auswahl des Spiels.
- Neues Spiel **Tiefpunkt** (2–8 Spieler) im gleichen Design, mit Computer-Spielern,
  Rundenwertung und Animationen beim Aufdecken, Tauschen und Abräumen von Spalten.
- Neuer Slug: das alte Add-on „Stapeljagd“ bitte deinstallieren.

## 1.2.0

- Neuer Name: Stapeljagd (vorher unter anderem Namen). Die Sonderkarte heißt jetzt Joker.
  Das Add-on hat einen neuen Slug; das alte Add-on bitte deinstallieren.

## 1.1.0

- Neues Design: Glassmorphism über einem bewegten Farbhintergrund, moderne Karten mit
  Verläufen und Glanz.
- Animationen: aufgedeckte Stapelkarten drehen sich um, gespielte Karten fliegen auf die
  Bauflächen, neue Handkarten werden ausgeteilt, fertige Stapel leuchten auf, Konfetti beim Sieg.

## 1.0.0

- Erste Version: Stapeljagd für 2–6 Spieler mit Lobby, Spielcodes, Computer-Spielern und
  Live-Updates; spielbar über die Seitenleiste und im Heimnetz auf Port 8098.
