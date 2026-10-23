# Changelog

## 0.20.0

- **Smarthome:** Der Assistent liest und schaltet deine Geräte in Home Assistant – Licht (Helligkeit, Farbe),
  Schalter, Heizung, Rollos, Szenen und jeder andere Dienst (Befehl `haus`). Schlösser, Alarmanlagen und Tore
  nur nach deiner Bestätigung.
- **Jarvis:** Fabians-HA-Jarvis spricht über den Master mit dem Assistenten – mit all seinen Werkzeugen.

## 0.19.1

- Werkbank: Teile werden jetzt mit build123d statt FreeCAD konstruiert (Werkbank ab 1.1.0).

## 0.19.0

- **Werkbank:** konstruiert Teile in FreeCAD nach deiner Beschreibung, vermisst Fotos mit A4-Blatt,
  schickt die Vorschau und druckt nach deinem „Ja“ – Befehl `werkbank` (mit Fabians-HA-Werkbank).

## 0.18.0

- **Pino:** fragt, was Pino der Kiwi gerade macht, was ihn interessiert und was er erlebt hat – Befehl `pino`
  (mit Fabians-HA-Pino).

## 0.17.0

- **„Hat das gerade offen?“** – `karte offen NAME`: Öffnungszeiten von Läden, Lokalen und Ämtern in
  deiner Nähe (oder in einem genannten Ort) aus OpenStreetMap, mit „geöffnet bis …“ oder „öffnet um …“.
- **Serien:** fragt den Serien-Kalender („Kommt heute was Neues?“, „Füg … hinzu“) – Befehl `serien`.
- **Himmel:** fragt den Himmels-Kalender („Kann ich heute die ISS sehen?“) – Befehl `himmel`.

## 0.16.0

- **Restaurant-Karte:** Foto der Speisekarte, vom Essen oder vom Beleg schicken („Bin im …“,
  „Hab die Pizza genommen“) – der Assistent liest Restaurant, Gerichte und Bestellung aus und trägt
  den Besuch mit deinem Standort in **Fabians-HA-Karte** ein. Fragen wie „Was hatte ich beim
  Italiener?“ beantwortet er aus der Karte. Neuer Befehl `karte`.

## 0.15.0

- **Gedächtnis:** Mit Fabians-HA-Gedächtnis merkt sich der Assistent Wichtiges über Gespräche
  hinweg, liest zu Beginn dein Profil und schaut vor Antworten über Personen und Themen nach
  (gefunden über den Master, nichts einzutragen).
- **Erinnerungen mit Bedingung:** „Erinner mich, wenn das Paket da ist / es über 20 Grad wird /
  Max schreibt / die Waschmaschine fertig ist“ – einmal oder jedes Mal, geprüft jede Minute.
  Neuer Befehl `erinnern`; der Assistent darf dafür Zustände in Home Assistant lesen.
- **Übersetzer:** Fotos von Speisekarten, Schildern und Briefen oder fremdsprachige Texte werden
  übersetzt und erklärt, Preise ungefähr in Euro umgerechnet.

## 0.14.0

- **Paketverfolgung:** Sendungsnummern, Links, Screenshots oder weitergeleitete
  Versandbestätigungen – der Assistent meldet „in Zustellung“, „zur Abholung bereit“, „zugestellt“
  und Probleme per iMessage. 17TRACK- und DHL-Schlüssel kommen aus **Fabians-HA-Master**.
- **Stundenplan (WebUntis):** bis zu zwei Stundenpläne (im Master), Änderungen wie Ausfall,
  Vertretung oder Raumwechsel kommen per iMessage; Fragen wie „Was hab ich morgen?“ gehen auch.

## 0.13.0

- Umgezogen nach **Fabians-HA-Addons** und umbenannt in **Fabians-HA-Assistent**.
- Alle Schlüssel (Inkbox, Claude, Apple, eBay) kommen aus **Fabians-HA-Master**; die Felder in der
  Konfiguration sind weg. Downloader, 3D-Druck und Krypto-Trader werden über den Master gefunden,
  Adressen einzutragen entfällt. Preisalarme gehen an die Handynummer aus dem Master.
- Die Claude-Brücke nimmt nur noch Anfragen des Masters an; kein Schlüssel mehr in `/share`.
