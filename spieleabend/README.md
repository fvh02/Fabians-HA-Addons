# Fabians-HA-Spieleabend

**Spieleabend** – 27 Spiele für Home Assistant: Karten-, Zeichen-, Wort-, Quiz-, Party- und Trinkspiele.
Alle laufen im Browser, jeder spielt am eigenen Handy. Viele Spiele haben einen **📺 Fernseher-Modus**: Ein Gerät
(z. B. der Fernseher oder ein Tablet) wird zum großen Bildschirm für alle.

<img src="../bilder/spieleabend/start.jpg" width="720" alt="Startseite mit Suche und Filtern">

Auf der Startseite gibt es eine Suche und Filter für Spieleranzahl, Art, Dauer und Fernseher-Modus.

## Installation

[![Repository zu Home Assistant hinzufügen](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ffvh02%2FFabians-HA-Addons)

Oder manuell: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories** und
`https://github.com/fvh02/Fabians-HA-Addons` hinzufügen. Dann **Fabians-HA-Master** und **Fabians-HA-Spieleabend** installieren
(für Ranglisten und Achievements zusätzlich **Fabians-HA-Bestenliste**).

## 🏆 Bestenliste

Das Add-on **Fabians-HA-Bestenliste**, macht aus jeder Partie angemeldeter Spieler
(Konto mit E-Mail-Bestätigung direkt im Spieleabend) Punkte für
die **Rangliste des Monats** (Neustart am 1.), vergibt **31 Achievements** und sammelt die
Monatssieger in einer **Ruhmeshalle** – mit eigener Seite in Home Assistant und über den Knopf
„🏆 Bestenliste“ direkt im Spieleabend. Details: [`bestenliste/DOCS.md`](../bestenliste/DOCS.md).

## Die Spiele

Die Bilder stammen aus simulierten Runden (Alex, Lena, Jonas und Mia, dazu ein Fernseher).

### Kartenspiele

#### Stapeljagd
*2–6 Spieler · 20–40 Min.*

Baut gemeinsam Stapel von 1 bis 12 – wer seinen eigenen Stapel zuerst los ist, gewinnt. Joker passen überall.

<p><img src="../bilder/spieleabend/stapeljagd.jpg" width="220" alt="stapeljagd"></p>

#### Tiefpunkt
*2–8 Spieler · ca. 30 Min.*

Jeder hat ein Raster aus 12 verdeckten Karten. Aufdecken, tauschen, Spalten abräumen – am Ende gewinnt, wer die wenigsten Punkte hat.

<p><img src="../bilder/spieleabend/tiefpunkt.jpg" width="220" alt="tiefpunkt"></p>

#### Farbrausch
*2–10 Spieler · 15–30 Min.*

Passende Farbe oder Zahl ablegen, die anderen mit +2 und +4 ärgern – und „Letzte Karte!“ nicht vergessen.

<p><img src="../bilder/spieleabend/farbrausch.jpg" width="220" alt="farbrausch"></p>

#### Schwimmen (31)
*2–8 Spieler · 15–30 Min. · 📺*

Drei Karten auf der Hand, drei in der Mitte: tauschen, schieben oder klopfen. Wer am Ende einer Runde die schlechteste Hand hat, verliert ein Leben – auch mit Computer-Spielern.

<p><img src="../bilder/spieleabend/schwimmen-1.jpg" width="220" alt="schwimmen-1"> <img src="../bilder/spieleabend/schwimmen-2.jpg" width="220" alt="schwimmen-2"> <img src="../bilder/spieleabend/schwimmen-tv.jpg" width="440" alt="schwimmen-tv"></p>

### Zeichnen

#### Kritzelpost
*3–10 Spieler · 10–20 Min.*

Stille Post mit Stift: Einer schreibt einen Satz, der Nächste zeichnet ihn, der Übernächste rät – am Ende wird das ganze Album gezeigt.

<p><img src="../bilder/spieleabend/kritzelpost-1.jpg" width="220" alt="kritzelpost-1"> <img src="../bilder/spieleabend/kritzelpost-2.jpg" width="220" alt="kritzelpost-2"></p>

#### Schnellmaler
*2–12 Spieler · 15–25 Min. · 📺*

Einer zeichnet am Handy, alle anderen raten. Mit dem Fernseher als großem Bildschirm.

<p><img src="../bilder/spieleabend/schnellmaler.jpg" width="220" alt="schnellmaler"> <img src="../bilder/spieleabend/schnellmaler-tv.jpg" width="440" alt="schnellmaler-tv"></p>

#### Blind gezeichnet
*3–12 Spieler · 10–20 Min. · 📺*

Jeder zeichnet seinen Begriff, ohne die eigenen Striche zu sehen – danach raten alle, was das sein soll. Am Ende gibt es eine Galerie.

<p><img src="../bilder/spieleabend/blindmaler-1.jpg" width="220" alt="blindmaler-1"> <img src="../bilder/spieleabend/blindmaler-2.jpg" width="220" alt="blindmaler-2"> <img src="../bilder/spieleabend/blindmaler-tv.jpg" width="440" alt="blindmaler-tv"></p>

### Wörter

#### Wortgitter
*1 Spieler · 3–5 Min.*

Fünf Buchstaben, sechs Versuche – Wort des Tages oder endlos.

<p><img src="../bilder/spieleabend/wortgitter.jpg" width="220" alt="wortgitter"></p>

#### Galgenraten
*1–8 Spieler · 10–20 Min.*

Einer denkt sich ein Wort aus, alle anderen raten Buchstabe für Buchstabe, bevor der Galgen fertig ist.

<p><img src="../bilder/spieleabend/galgenraten.jpg" width="220" alt="galgenraten"></p>

#### Codewörter
*4–16 Spieler · 15–30 Min. · 📺*

Team Rot gegen Team Blau. Nur der Hinweisgeber kennt die Farben der 25 Karten und gibt ein Wort mit einer Zahl – aber bloß nicht den Attentäter aufdecken!

<p><img src="../bilder/spieleabend/codewoerter-1.jpg" width="220" alt="codewoerter-1"> <img src="../bilder/spieleabend/codewoerter-2.jpg" width="220" alt="codewoerter-2"> <img src="../bilder/spieleabend/codewoerter-tv.jpg" width="440" alt="codewoerter-tv"></p>

#### Stadt-Land-Fluss
*2–16 Spieler · 10–25 Min. · 📺*

Der Klassiker mit „Stopp!“-Knopf. Danach werden die Antworten verglichen, zweifelhafte können per Abstimmung gestrichen werden.

<p><img src="../bilder/spieleabend/stadtlandfluss-1.jpg" width="220" alt="stadtlandfluss-1"> <img src="../bilder/spieleabend/stadtlandfluss-2.jpg" width="220" alt="stadtlandfluss-2"> <img src="../bilder/spieleabend/stadtlandfluss-tv.jpg" width="440" alt="stadtlandfluss-tv"></p>

### Quiz & Party

#### Schätzmeister
*2–16 Spieler · 10–20 Min. · 📺*

Wie tief ist der Marianengraben? Alle tippen eine Zahl – wer am nächsten dran ist, holt die Punkte. Mit Kategorien, z. B. Geschichte oder 🔩 Metallbau (Ausbildung).

<p><img src="../bilder/spieleabend/schaetzmeister.jpg" width="220" alt="schaetzmeister"> <img src="../bilder/spieleabend/schaetzmeister-tv.jpg" width="440" alt="schaetzmeister-tv"></p>

#### Wer würde eher …?
*3–16 Spieler · 10–20 Min. · 📺*

Eine Frage, alle stimmen geheim für jemanden aus der Runde – dann die große Auflösung.

<p><img src="../bilder/spieleabend/werwuerde-1.jpg" width="220" alt="werwuerde-1"> <img src="../bilder/spieleabend/werwuerde-2.jpg" width="220" alt="werwuerde-2"> <img src="../bilder/spieleabend/werwuerde-tv.jpg" width="440" alt="werwuerde-tv"></p>

#### Lügenbaron
*3–12 Spieler · 15–25 Min. · 📺*

Ein wahrer, verrückter Fakt mit Lücke. Alle erfinden eine glaubwürdige Lüge, dann muss jeder die Wahrheit finden. Punkte gibt es für Treffer und fürs Reinlegen.

<p><img src="../bilder/spieleabend/luegenbaron-1.jpg" width="220" alt="luegenbaron-1"> <img src="../bilder/spieleabend/luegenbaron-2.jpg" width="220" alt="luegenbaron-2"> <img src="../bilder/spieleabend/luegenbaron-tv.jpg" width="440" alt="luegenbaron-tv"></p>

#### Punchline
*3–12 Spieler · 15–25 Min. · 📺*

Alle ergänzen denselben Satz so lustig wie möglich – danach wird anonym die beste Pointe gewählt.

<p><img src="../bilder/spieleabend/punchline-1.jpg" width="220" alt="punchline-1"> <img src="../bilder/spieleabend/punchline-2.jpg" width="220" alt="punchline-2"> <img src="../bilder/spieleabend/punchline-tv.jpg" width="440" alt="punchline-tv"></p>

#### Imposter
*3–16 Spieler · ca. 5 Min. pro Runde*

Alle kennen das geheime Wort – nur einer nicht. Reihum ein Hinweiswort, dann abstimmen.

<p><img src="../bilder/spieleabend/imposter.jpg" width="220" alt="imposter"></p>

#### Buzzer-Quiz
*2–16 Spieler · 10–20 Min. · 📺*

Wer zuerst buzzert, darf antworten: richtig +3, falsch −2. Mit Kategorien, z. B. 🔩 Metallbau (Ausbildung).

<p><img src="../bilder/spieleabend/buzzer-1.jpg" width="220" alt="buzzer-1"> <img src="../bilder/spieleabend/buzzer-2.jpg" width="220" alt="buzzer-2"> <img src="../bilder/spieleabend/buzzer-tv.jpg" width="440" alt="buzzer-tv"></p>

#### Sortierfix
*2–16 Spieler · 10–20 Min. · 📺*

Fünf Dinge in die richtige Reihenfolge bringen – Jahreszahlen, Höhen, Einwohner oder Schmelzpunkte.

<p><img src="../bilder/spieleabend/sortierfix-1.jpg" width="220" alt="sortierfix-1"> <img src="../bilder/spieleabend/sortierfix-2.jpg" width="220" alt="sortierfix-2"> <img src="../bilder/spieleabend/sortierfix-tv.jpg" width="440" alt="sortierfix-tv"></p>

#### Filmoji
*1 Spieler · 5–15 Min.*

Welcher Film steckt hinter den Emojis? 165 Filme, Tipps kosten Punkte, nach drei Herzen ist Schluss.

<p><img src="../bilder/spieleabend/filmoji-1.jpg" width="220" alt="filmoji-1"> <img src="../bilder/spieleabend/filmoji-2.jpg" width="220" alt="filmoji-2"></p>

#### Spion
*3–16 Spieler · 20–45 Min. · 📺*

Alle kennen den geheimen Ort und ihre Rolle – nur der Spion nicht. Fragt euch aus und entlarvt ihn, bevor er den Ort errät.

<p><img src="../bilder/spieleabend/spion-1.jpg" width="220" alt="spion-1"> <img src="../bilder/spieleabend/spion-2.jpg" width="220" alt="spion-2"> <img src="../bilder/spieleabend/spion-tv.jpg" width="440" alt="spion-tv"></p>

#### Werwolf
*5–18 Spieler · 20–40 Min. · 📺*

Die Handys sind der Spielleiter: Nachts jagen die Werwölfe, Seherin und Hexe helfen dem Dorf, tagsüber wird abgestimmt.

<p><img src="../bilder/spieleabend/werwolf-1.jpg" width="220" alt="werwolf-1"> <img src="../bilder/spieleabend/werwolf-2.jpg" width="220" alt="werwolf-2"> <img src="../bilder/spieleabend/werwolf-tv.jpg" width="440" alt="werwolf-tv"></p>

### Trinkspiele 🍻

> Trinkspiele sind ab 18. Alles klappt genauso mit Wasser, Saft oder Limo – trinkt verantwortungsvoll, niemand muss.

#### Ich hab noch nie …
*2–16 Spieler · 10–20 Min. · 📺*

Ein Satz, alle antworten geheim – wer es schon gemacht hat, trinkt. Wahlweise mit frecheren Sätzen.

<p><img src="../bilder/spieleabend/nochnie-1.jpg" width="220" alt="nochnie-1"> <img src="../bilder/spieleabend/nochnie-2.jpg" width="220" alt="nochnie-2"> <img src="../bilder/spieleabend/nochnie-tv.jpg" width="440" alt="nochnie-tv"></p>

#### Wahrheit oder Trinken
*2–16 Spieler · 15–30 Min. · 📺*

Reihum bekommt jemand eine Frage: ehrlich antworten – oder trinken.

<p><img src="../bilder/spieleabend/wahrheit-1.jpg" width="220" alt="wahrheit-1"> <img src="../bilder/spieleabend/wahrheit-2.jpg" width="220" alt="wahrheit-2"></p>

#### Trinklotto
*2–16 Spieler · ca. 10 Min. · 📺*

Jeder bekommt geheim eine Farbe, eine Zahl und ein Tier. „Alle mit gerader Zahl trinken 3!“ – das Handy zeigt sofort, wen es trifft.

<p><img src="../bilder/spieleabend/trinklotto.jpg" width="220" alt="trinklotto"> <img src="../bilder/spieleabend/trinklotto-tv.jpg" width="440" alt="trinklotto-tv"></p>

#### Pyramide
*2–9 Spieler · 10–15 Min. · 📺*

Vier Karten auf der Hand, die Pyramide wird Karte für Karte aufgedeckt: Wer den gleichen Wert hat, trinkt oder verteilt – oben mehr als unten.

<p><img src="../bilder/spieleabend/pyramide.jpg" width="220" alt="pyramide"></p>

#### Pferderennen
*2–16 Spieler · ca. 5 Min. pro Rennen · 📺*

Schlucke auf ein Ass setzen, die Karten treiben die Pferde an. Verlierer trinken, Sieger verteilen das Doppelte.

<p><img src="../bilder/spieleabend/pferderennen-1.jpg" width="220" alt="pferderennen-1"> <img src="../bilder/spieleabend/pferderennen-2.jpg" width="220" alt="pferderennen-2"> <img src="../bilder/spieleabend/pferderennen-tv.jpg" width="440" alt="pferderennen-tv"></p>

#### Ring of Fire
*2–16 Spieler · 20–30 Min. · 📺*

Reihum eine Karte ziehen – jede hat eine Regel. Wer den vierten König zieht, leert den Becher.

<p><img src="../bilder/spieleabend/ringoffire.jpg" width="220" alt="ringoffire"> <img src="../bilder/spieleabend/ringoffire-tv.jpg" width="440" alt="ringoffire-tv"></p>

## Mehr

📺 = mit Fernseher-Modus. Details, Regeln und Optionen stehen in [`DOCS.md`](DOCS.md).
Wie man den Spieleabend über eine eigene Domain erreichbar macht (Cloudflare-Tunnel), steht ebenfalls dort.
