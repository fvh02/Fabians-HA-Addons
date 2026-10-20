# Fabians-HA-Himmel

Was heute Nacht über deinem Zuhause am Himmel zu sehen ist – und ob die Wolken mitspielen.

## Was es kann

- **ISS-Überflüge** der nächsten 10 Tage, die du sehen kannst (die ISS leuchtet nur in der Dämmerung,
  wenn es bei dir dunkel ist und sie selbst noch Sonne hat): Uhrzeit, aus welcher Richtung, wie hoch,
  wie lange. Die Bahn wird aus den aktuellen Bahndaten von CelesTrak selbst berechnet.
- **Mond:** Phase und Helligkeit heute, die nächsten Voll- und Neumonde.
- **Klare Nächte:** Bewölkung in den dunklen Stunden der nächsten drei Nächte (Open-Meteo).
- **Sternschnuppen:** die großen Ströme der nächsten 90 Tage mit Rate und wie hell der Mond dann stört.
- **Finsternisse** bis 2030 mit dem, was davon in Mitteleuropa zu sehen ist.

## Meldungen per iMessage (über Fabians-HA-Master)

- **Abendmeldung** (Vorgabe 17 Uhr): was heute Nacht lohnt – nur wenn es etwas gibt *und* die
  Bewölkung unter deiner Grenze liegt (Finsternisse kommen immer).
- **ISS-Erinnerung** etwa 10 Minuten vor einem gut sichtbaren Überflug (Vorgabe: mindestens 30° hoch,
  höchstens 50 % Wolken, zwischen 6 und 23 Uhr).

Alles in der **Konfiguration** einstellbar. Der Standort ist der deines Home Assistant (Einstellungen →
System → Allgemein).

Der Assistent kennt den Himmels-Kalender: „Kann ich heute die ISS sehen?“, „Wann ist Vollmond?“.

## Gut zu wissen

- Zeiten der Überflüge stimmen auf wenige Sekunden; je weiter in der Zukunft, desto ungenauer (die
  Bahndaten werden zweimal am Tag erneuert).
- Die Daten der Sternschnuppen-Maxima sind die üblichen Termine (±1 Tag).
