# Fabians-HA-Werkbank

Du beschreibst ein Teil, Claude konstruiert es (Python-CAD mit **build123d**), du bekommst ein Bild davon aufs Handy,
und nach deinem „Ja“ druckt dein Bambu Lab P1S es aus.

> Du: „Ich brauch einen Halter für meine Kopfhörer unter der Schreibtischplatte, Platte 25 mm dick“
> Assistent: konstruiert, prüft die Vorschau und schickt dir das Bild mit Maßen
> Du: „Mach den Haken 1 cm länger“ → neue Version, neues Bild
> Du: „Drucken“ → Bild, „1 h 40 min, 38 g PLA. Soll ich drucken?“
> Du: „Ja“ → der Druck startet

## Zwei Wege

- **Per iMessage** über Fabians-HA-Assistent (ab 0.19.1). Der Assistent schreibt das CAD-Skript selbst,
  sieht sich die Vorschau an, bevor er sie dir schickt, und kennt das Gespräch.
- **Im Dashboard** (Seitenleiste **Werkbank**): Chat mit Claude, drehbare 3D-Ansicht, Versionen, Parameter
  per Schieberegler, Maße und Fotos, Download als STEP (zum Weiterbearbeiten z. B. in FreeCAD oder Fusion am PC) oder STL.

Beide Wege arbeiten mit denselben Projekten. Was du per iMessage angefangen hast, kannst du im Dashboard
weiterbearbeiten und umgekehrt.

## Maße aus Fotos

1. Leg den Gegenstand **auf** oder **neben** ein Blatt Papier (A4, A5, A3, A6, Letter) oder eine Scheckkarte.
   Am besten auf einem dunklen Untergrund, damit sich das Blatt gut abhebt.
2. Fotografiere **senkrecht von oben**. Das Blatt muss ganz zu sehen sein.
3. Schick das Foto dem Assistenten („Hier das Mainboard auf A4“) oder lade es im Dashboard unter **📏 Maße** hoch.

Das Add-on findet das Blatt, entzerrt das Foto auf die Ebene des Blatts und legt ein Millimeterraster darüber
(gelb alle 50 mm). Länge und Breite des Gegenstands werden automatisch gemessen. Im Dashboard tippst du zwei
Punkte an, um weitere Abstände zu messen (Lochabstände, Anschlüsse …), und übernimmst sie als Maß. Der
Assistent liest weitere Maße am Raster ab.

Genauigkeit: Mit einem A4-Blatt etwa 1 %, mit einer Scheckkarte etwa 3 %. Das gilt für flache Gegenstände.
Bei hohen wirkt die Oberseite etwas größer. Für Teile, die genau passen müssen, nachmessen oder erst ein kleines
Probestück drucken. Wird das Blatt nicht gefunden, tippst du im Dashboard die vier Ecken selbst an.

## Drucken

- **Drucken** (im Dashboard oder „Druck das“ per iMessage) übergibt das Teil an **Fabians-HA-3D-Druck**. Dort
  wird es geslict, und du bekommst per iMessage das Bild mit Druckzeit und Filament.
- Gedruckt wird erst nach deinem **„Ja“** (per iMessage) oder **„Jetzt drucken“** im Dashboard. Eine offene
  Druckfrage verfällt nach 3 Stunden.
- Mehrere Teile werden gemeinsam auf eine Platte gelegt. Teile über 256 mm werden nicht gedruckt. Claude soll
  sie dann in Teile mit Verbindungen aufteilen.

Dafür muss **Fabians-HA-3D-Druck** installiert und eingerichtet sein (nur auf amd64).

## Was Claude konstruieren kann (und was nicht)

Gut: Halter, Boxen, Deckel, Gehäuse, Abdeckungen, Adapter, Ständer, Kabelführungen, Wandhalterungen,
Ersatzteile, Namensschilder, also technische Teile aus Grundformen mit Löchern, Rundungen, Fasen und Schrift.

Schwierig: organische Formen (Figuren, ergonomische Griffe). Alles wird parametrisch gebaut: Die wichtigen Maße
sind Parameter, die du ohne Claude ändern kannst.

## Technik und Sicherheit

- Die Teile werden mit [build123d](https://github.com/gumyr/build123d) (Python, OpenCASCADE-Kern) gebaut. Jedes
  Skript wird vorher geprüft (keine Dateien, kein Netzwerk, keine fremden Module) und läuft in einem eigenen
  Prozess als unprivilegierter Benutzer, mit Zeit- (3 Minuten) und Speicherlimit. Es wird immer nur ein Modell
  gleichzeitig berechnet; ein Durchlauf dauert einige Sekunden.
- Prüfungen nach dem Bau: geschlossener Körper, gültige Geometrie, Größe gegen den P1S-Bauraum, sehr dünne
  Teile. Warnungen stehen im Bild und im Dashboard.
- Jede Änderung ist eine eigene Version (Skript, STEP, STL, Vorschau) in `/data/projekte`. Sie sind Teil deiner
  Backups.
- Das Image ist etwa 1 GB groß. Ein einfaches Teil braucht beim Berechnen kurz einige hundert MB RAM.
- Claude im Dashboard läuft über Fabians-HA-Master (ab 1.2.8) mit der Anmeldung des Assistenten.
- Die 3D-Ansicht nutzt [three.js](https://threejs.org) (MIT), direkt im Add-on mitgeliefert.
