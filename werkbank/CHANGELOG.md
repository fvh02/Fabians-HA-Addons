# Changelog

## 1.1.0

- **build123d statt FreeCAD:** Claude schreibt die Teile jetzt mit build123d (Python-CAD auf demselben
  OpenCASCADE-Kern). Die Skripte werden kürzer und robuster („alle oberen Kanten runden“ in einer Zeile),
  und **Schrift geht jetzt** – Beschriftungen und Gravuren.
- Das Image ist deutlich kleiner (etwa 1 GB statt 3 GB) und braucht weniger Speicher.

## 1.0.0

- Erste Version: Claude konstruiert Teile als parametrisches FreeCAD-Skript; das Add-on rechnet sie
  (FreeCAD 1.1, ohne Oberfläche), prüft sie auf Druckbarkeit und rendert Vorschaubilder.
- Per iMessage (Fabians-HA-Assistent, Befehl `werkbank`) oder im Dashboard mit Chat, 3D-Ansicht,
  Parameter-Reglern, Versionen und Download als STEP/STL.
- Maße aus Fotos: ein Blatt (A4, A5, A3, A6, Letter) oder eine Scheckkarte als Referenz, das Foto wird
  entzerrt, der Gegenstand vermessen; im Dashboard per Antippen weitere Maße abnehmen.
- Drucken über Fabians-HA-3D-Druck: Vorschau, Druckzeit und Filament per iMessage, gedruckt wird erst
  nach deinem „Ja“ (oder „Jetzt drucken“ im Dashboard).
