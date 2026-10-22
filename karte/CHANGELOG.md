# Changelog

## 1.1.1

- **Behoben:** Anfragen des Masters wurden abgewiesen, wenn sie über IPv6 kamen (Home Assistant hat
  IPv6 im Add-on-Netz eingeschaltet). Das Add-on ist jetzt nur über IPv4 erreichbar.

## 1.1.0

- **„Hat das gerade offen?“:** Läden, Lokale und Ämter in der Nähe (oder in einem Ort) mit ihren
  Öffnungszeiten aus OpenStreetMap – „geöffnet bis 20:00 Uhr“ oder „öffnet morgen um 9:00 Uhr“. Für den
  Assistenten (`karte offen`).

## 1.0.0

- Erste Version: Restaurant-Karte, die der Assistent füllt – Speisekarte, Bestellung, Summe und Fotos
  pro Besuch, Ort über den Standort aus der Home-Assistant-App und OpenStreetMap, Online-Recherche mit
  Abgleich (Öffnungszeiten, Bewertung, Preisniveau, Abweichungen) und Meldung per iMessage.
- **Live-Standort aus „Wo ist?“:** Ist die iCloud-Integration von Home Assistant eingerichtet, nimmt
  die Karte dein iPhone aus „Wo ist?“ und fordert vor jedem Eintrag eine frische Position bei Apple an
  (sonst der Standort aus der Home-Assistant-App).
