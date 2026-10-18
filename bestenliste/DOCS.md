# Fabians-HA-Bestenliste

Rangliste und Achievements für den **Spieleabend**. Jede beendete Partie landet automatisch hier.

## So funktioniert's

- **Rangliste des Monats:** Für jede Partie gibt es 1 Punkt fürs Mitspielen und 1 Punkt für jeden,
  der hinter dir landet. Siege, Partien, Siegquote und Schlucke (Trinkspiele) stehen daneben.
- **Neustart am 1. jedes Monats:** Die Rangliste beginnt bei null. Die besten drei des alten Monats
  kommen in die **Ruhmeshalle**, der Sieger bekommt das Achievement „Spieler des Monats“. Alte
  Monate kannst du oben im Auswahlfeld weiter ansehen.
- **Beste pro Spiel:** Wer in welchem Spiel diesen Monat am häufigsten gewonnen hat.
- **Achievements** (31 Stück) bleiben für immer, z. B. 🔥 3 Siege hintereinander, 🎯 Volltreffer
  im Schätzmeister, 🕵️ 3-mal als Imposter gewonnen, 🦉 Partie nach Mitternacht, 🏃 5 Partien an
  einem Abend. Ein Klick auf einen Namen zeigt alle Achievements mit Fortschritt.
- Neue Achievements und ein neuer Spitzenreiter erscheinen am Ende der Partie direkt im Spiel.

**Punkte und Achievements sammelt nur, wer im Spieleabend angemeldet ist** (Startseite →
„🔑 Anmelden“). Gäste spielen mit, stehen in den Partien als „Gast“ und bekommen nichts. Es zählen
nur Partien mit **mindestens zwei Menschen** (Computer-Spieler zählen nicht mit, wer mittendrin
geht, auch nicht). Gezählt wird am Konto – ein Namenswechsel ändert nichts.

## Wo die Seite ist

- In Home Assistant in der Seitenleiste (**Bestenliste**).
- Im Spieleabend oben auf der Startseite: **🏆 Bestenliste** – so sehen auch Freunde ohne Home
  Assistant die Liste (nur ansehen).
- Im Heimnetz unter `http://<home-assistant-ip>:8091`. Aus dem Internet nur mit dem
  **Zugangscode** – demselben wie beim Spieleabend (**Fabians-HA-Master** → Zugangscodes → Spieleabend).

## Korrekturen

Nur über Home Assistant (Seitenleiste) gibt es im Reiter **Partien** zusätzlich **löschen** – eine
Partie aus der Wertung nehmen (z. B. eine Testrunde). Löscht jemand sein Konto im Spieleabend,
verschwindet es auch hier.

## Einrichtung

Installieren und starten – fertig. Spieleabend (ab 3.3.0) und Bestenliste müssen aus demselben
Repository stammen; sie finden sich dann von selbst. Ist die Bestenliste mal nicht erreichbar,
merkt sich der Spieleabend die Ergebnisse und schickt sie später nach.

## Konfiguration

| Option        | Beschreibung                                                        |
| ------------- | ------------------------------------------------------------------- |
| `theme`       | `dark` oder `light`.                                                 |

Der Zugangscode für Aufrufe aus dem Internet kommt aus dem **Fabians-HA-Master** (Spieleabend-Code).
Ohne Code ist die Bestenliste aus dem Internet gesperrt.
