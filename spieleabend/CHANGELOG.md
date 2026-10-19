# Changelog

## 3.6.1

- **Deutlich schneller mit vielen Spielern:** Jedes Handy bekommt seine Updates jetzt über eine
  eigene Warteschlange. Vorher wartete der Spieleabend bei jeder Aktion nacheinander auf jedes
  Handy – ein einziges Gerät mit schlechtem Empfang bremste alle (im Test: 20 Striche bei
  Schnellmaler mit einem langsamen Handy 38 Sekunden statt sofort). Hängt ein Handy hinterher,
  bekommt es direkt den neuesten Stand statt aller Zwischenschritte; unveränderte Ansichten werden
  nicht doppelt geschickt.
- Seiten werden nur noch einmal vorbereitet, Skripte und Styles bleiben bis zum nächsten Update im
  Browser gespeichert (vorher bei jedem Seitenaufruf neu beim Server angefragt).
- Anmelden und Registrieren halten die laufenden Spiele nicht mehr kurz an.
- Leichteres Design: Der Hintergrund bewegt sich nicht mehr und die Glas-Unschärfe ist geringer –
  das hat Handys, Tablets und Fernseher bei jedem Bild neu rechnen lassen. Bei „Bewegung
  reduzieren“ in den Systemeinstellungen gibt es keine Animationen mehr.

## 3.6.0

- Alle Neuerungen aus 3.2.0 bis 3.6.0 (unten): neun neue Spiele, Filmoji, Konten und Bestenliste,
  kein Scrollen mehr, Beitreten per Code auf der Startseite.
- Die E-Mail-Einstellungen für Bestätigungscodes (SMTP) kommen wie der Zugangscode aus
  **Fabians-HA-Master** – das Add-on selbst hat nur noch das Farbschema als Option.
- **Kein Scrollen mehr:** Lobby, Warteraum und jede Phase aller Spiele passen auf einen
  Handy-Bildschirm (getestet auf 360×640 und 375×667, mit 4 und 8 Spielern) und auf den Fernseher.
  Nur die Spieleliste auf der Startseite scrollt. Lange Listen (z. B. 16 Spieler, Album bei
  Kritzelpost, Ortsliste bei Spion) scrollen notfalls innerhalb ihres Feldes.
- Stapeljagd: weniger Abstand über und unter dem Ziehstapel und den vier Stapeln.
- **Beitreten per Code auf der Startseite** („🎟️ Spiel beitreten“): Der Code findet sein Spiel
  von selbst. Codes sind jetzt über alle Spiele hinweg eindeutig.
- Lobby der Spiele: kein Code-Feld mehr, dafür bis zu drei offene Spiele zum Beitreten.
  Einladungslinks treten direkt bei, wenn der Name schon bekannt ist.
- Kleinere Verbesserungen unterwegs, u. a. Ring of Fire (Regeln als eigenes Fenster),
  Pyramide (wer trinkt, steht direkt in der Punkteliste), Stadt-Land-Fluss (Auswertung
  Kategorie für Kategorie), Codewörter (Teams direkt in der Spielerliste).

## 3.5.2

- Schwimmen: Auf schmalen Handys ragte die Spielerleiste oben links aus dem Bild (der erste Name
  war abgeschnitten). Sie beginnt jetzt am linken Rand und lässt sich seitlich wischen.

## 3.5.1

- Startseite: Beim Filtern verloren einige Spielbilder Schatten und Farbverläufe (z. B. bei
  „Ich hab noch nie …“). Jede Abbildung hat jetzt eigene Kennungen.
- Blind gezeichnet: Nach Spielende stand hinter dem Ergebnis „Niemand hat etwas gezeichnet!“.
- README: Bilder zu allen neuen Spielen und neue Startseiten-Bilder.

## 3.5.0

- **Filmoji** ersetzt Emoji-Rätsel: nur Filme (165 Stück, von Disney bis Der Pate) und als Spiel
  für eine Person wie Wortgitter. Drei Versuche pro Film, Tipps (Jahr, Anfangsbuchstaben),
  drei Herzen, Serien-Bonus und Rekord. Die Lösungen bleiben auf dem Server.

## 3.4.0

- **9 neue Spiele** – jetzt 27:
  - 🧠 **Buzzer-Quiz**: Wer zuerst buzzert, darf antworten (auch mit Metallbau-Fragen).
  - 🧠 **Sortierfix**: Fünf Dinge in die richtige Reihenfolge bringen.
  - 🧠 **Emoji-Rätsel**: Filme, Sprichwörter, Märchen und mehr in Emojis erraten.
  - 🔤 **Codewörter**: Zwei Teams, ein Hinweisgeber pro Team, ein geheimer Schlüssel.
  - 🔤 **Stadt-Land-Fluss**: Mit „Stopp!“-Knopf und Abstimmung über zweifelhafte Antworten.
  - 🎉 **Spion**: Alle kennen den Ort – nur der Spion nicht.
  - 🎉 **Werwolf**: Die Handys sind der Spielleiter (Seherin, Hexe, Jäger, Amor).
  - ✏️ **Blind gezeichnet**: Zeichnen, ohne die eigenen Striche zu sehen.
  - 🃏 **Schwimmen (31)**: Der Kartenklassiker, auch mit Computer-Spielern.
- Alle neuen Spiele zählen für die Bestenliste (ab Bestenliste 1.2.0).
- Punkteliste: Minuspunkte werden als „−2“ statt „+-2“ angezeigt.

## 3.3.4

- **Nie mehr hängen nach einer Frage:** Nach der Auflösung bekommen jetzt **alle** den Knopf
  „Nächste Runde“ – jedes Handy und auch das Fernseher-Gerät (z. B. ein Tablet). Wer zuerst
  drückt, startet die nächste Runde.
- Das Fernseher-Gerät kann außerdem „Nicht mehr warten“ und „Spiel beenden“ drücken.
- Die Versionsnummer unten auf den Seiten ist wieder entfernt (sie steht weiter im Protokoll).

## 3.3.3

- Ganz unten auf jeder Seite steht jetzt die laufende Version (z. B. „Spieleabend 3.3.3“).
  So lässt sich auf jedem Gerät prüfen, ob ein Update angekommen ist.
- Skripte und Styles werden bei jedem Laden mit dem Server abgeglichen: Nach einem Update
  nutzt der Browser sofort die neuen Dateien statt einer zwischengespeicherten alten Version.

## 3.3.2

- **Gastgeber am Fernseher:** Hat der Gastgeber sein eigenes Gerät auf „📺 Host“ gestellt, bekommt
  dieser Bildschirm jetzt auch „Nächste Runde“, „Nicht mehr warten“ und „Spiel beenden“.
  Bisher blieb das Spiel dort nach der ersten Frage stehen.

## 3.3.1

- **Party- und Quizspiele bleiben nicht mehr nach einer Frage hängen:** War der Gastgeber zugleich
  der Fernseher (📺 Host), gab es nirgends den Knopf „Nächste Runde“. Jetzt dürfen dann alle
  Mitspieler weiterschalten. Dasselbe gilt, wenn der Gastgeber gegangen ist – und wenn er
  20 Sekunden nach der Auflösung nicht weitermacht (z. B. Handy gesperrt).
- Verlässt der Gastgeber die Runde, geht die Rolle an einen Mitspieler statt an den Fernseher.

## 3.3.0

- **Konten:** Neue Seite **Konto** (Startseite oben „🔑 Anmelden“) mit Registrieren,
  Anmelden, Abmelden, Passwort ändern und Konto löschen. Bei der Registrierung kommt ein
  6-stelliger Bestätigungscode per E-Mail; „Passwort vergessen“ setzt das Passwort ebenfalls per
  Code aus der E-Mail zurück (30 Minuten gültig, höchstens 5 Versuche).
- **Nur angemeldet zählt:** Punkte und Achievements in der Bestenliste sammeln nur angemeldete
  Spieler; sie spielen automatisch unter ihrem Kontonamen. Gäste spielen weiter ohne Konto mit,
  dürfen aber keinen Namen eines Kontos benutzen.
- Der Zugangscode der Seite bleibt davor bestehen.
- Neue Optionen für den E-Mail-Versand (SMTP). Ohne sie stehen die Codes im Protokoll.

## 3.2.0

- **Bestenliste:** Beendete Partien gehen an das neue Add-on **Spieleabend-Bestenliste**
  (Rangliste pro Monat, Achievements, Ruhmeshalle). Neue Achievements und ein neuer
  Spitzenreiter erscheinen am Ende der Partie im Spiel. Auf der Startseite gibt es den Knopf
  **🏆 Bestenliste**. Ohne das Add-on ändert sich nichts.

## 3.1.0

- Umgezogen nach **Fabians-HA-Addons** und umbenannt in **Fabians-HA-Spieleabend**.
- Der Zugangscode für Mitspieler kommt aus **Fabians-HA-Master** (eigener Code, getrennt vom
  Downloader-Code).
- **Schätzmeister mit Kategorien:** Allgemeinwissen gemischt, Erde, Länder & Weltall,
  Geschichte & Jahreszahlen, Mensch & Alltag und neu **Metallbau (Ausbildung)** mit 46 Fragen
  zu Werkstoffen, Gewinden, Schweißen, Profilgewichten, Toleranzen sowie Treppen und Geländern.

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
