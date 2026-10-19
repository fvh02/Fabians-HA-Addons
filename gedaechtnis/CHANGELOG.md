# Changelog

## 0.1.0

- In **Fabians-HA-Addons** als **Fabians-HA-Gedächtnis**: Claude kommt über den Master und den
  Assistenten, keine Token- oder Schlüssel-Optionen mehr, Port 8101 (8096 hat der Browser).
- Erste Version: Gedächtnis als Obsidian-Vault mit Personen, Orten, Projekten, Geräten, Vorlieben,
  Organisationen und Themen, dazu ein Tagebuch der Ereignisse.
- Infos von Add-ons und dem Assistenten landen mit Datum und Uhrzeit (mit Sekunden) in einer
  Warteschlange und werden von Claude einsortiert. Die zeitlich neuere Info gewinnt, die ältere
  bleibt im Verlauf der Notiz.
- Nächtliches Aufräumen: Doppelte zusammenführen, lange Notizen verdichten, alte Tage
  zusammenfassen, Profil erneuern. Jede Änderung ist ein Git-Commit.
- Schnittstelle für Add-ons: merken, suchen, Notiz lesen, fertiger Kontext-Text, Profil.
