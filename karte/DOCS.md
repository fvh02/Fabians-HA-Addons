# Fabians-HA-Karte

Deine Karte der Restaurants, Cafés und Bars, in denen du warst – mit Speisekarte, was du bestellt
hast, Fotos, deiner Bewertung und dem, was das Internet über den Ort weiß.

## So kommt etwas auf die Karte

Du schreibst einfach dem **Fabians-HA-Assistenten**, z. B.:

- Foto der **Speisekarte** + „Hab die Pizza Diavola und eine Cola genommen“
- Foto vom **Essen** oder vom **Beleg**
- „Bin im Café Extrablatt, trag das ein“

Der Assistent liest Name, Adresse, Gerichte und Preise von der Karte und deine Bestellung aus und
schickt alles hierher. Den Ort nimmt er von deinem **Live-Standort aus „Wo ist?“** (Find My): Die
Karte bittet Apple jedes Mal um eine frische Position deines iPhones und wartet bis zu 25 Sekunden darauf.
Warst du woanders oder trägst du es später ein, sag ihm wo – oder schick einen Standort.

Die Karte

1. sucht das Restaurant in **OpenStreetMap** in 150 m Umkreis und nimmt das, dessen Name zur
   Speisekarte passt (sonst das nächste – dann fragt der Assistent kurz nach, ob es stimmt),
2. speichert Speisekarte, Bestellung, Summe und Fotos (verkleinert),
3. lässt Claude das Restaurant **online recherchieren** – Öffnungszeiten, Telefon, Website,
   Bewertung, Preisniveau, Online-Speisekarte – und **gleicht ab**: Wo Speisekarte, OpenStreetMap
   und Internet nicht übereinstimmen (anderer Name oder andere Adresse, andere Telefonnummer, deutlich
   andere Preise, dauerhaft geschlossen), steht das als **Abweichung** auf der Karte. Das Ergebnis
   kommt nach etwa einer Minute per iMessage.

## Die Seite

In der Seitenleiste unter **Karte**: alle Orte auf der Karte und als Liste, Suche nach Name, Küche
oder Gericht. Ein Ort zeigt Infos, Abweichungen, deine Besuche mit Bestellung und Sternen (antippen
zum Bewerten), Fotos und die Speisekarte vom Foto. **Neu abgleichen** startet die Online-Recherche
noch einmal.

## „Hat das gerade offen?“

Der Assistent fragt die Karte auch nach Öffnungszeiten: Sie sucht Läden, Lokale und Ämter mit dem
Namen in 5 km Umkreis um deinen Standort (oder um einen genannten Ort) und wertet die Öffnungszeiten
aus OpenStreetMap aus. Feiertage kennt sie nicht; stehen keine Zeiten in OpenStreetMap, schaut der
Assistent im Internet nach.

## Einrichtung

- **Fabians-HA-Master** und **Fabians-HA-Assistent** müssen laufen (der Abgleich nutzt Claude über
  den Assistenten, die Meldungen gehen über den Master).
- **Standort aus „Wo ist?“ (empfohlen, am genauesten):** In Home Assistant unter *Einstellungen →
  Geräte & Dienste → Integration hinzufügen* die **iCloud**-Integration einrichten: Apple-ID und dein
  normales Apple-Passwort (kein App-Passwort – „Wo ist?“ geht nur so), dann den Bestätigungscode vom
  iPhone eingeben. Danach gibt es z. B. `device_tracker.fabians_iphone`. Die Karte nimmt automatisch
  ein iPhone aus „Wo ist?“; bei mehreren Geräten unter **Konfiguration** bei *Gerät für den Standort*
  das richtige eintragen. Deine Apple-ID im **Fabians-HA-Master** (Apple-Kalender → Apple-ID) sagt der
  Karte, welches Konto sie nach einer frischen Position fragt.
- Ohne iCloud-Integration nimmt die Karte den Standort aus der **Home-Assistant-App** auf dem Handy
  (weniger aktuell).

Die Karte ist nur über Home Assistant und für den Assistenten erreichbar. Fotos und Daten liegen im
Add-on (in Home-Assistant-Backups enthalten). Kartenbilder kommen von OpenStreetMap.
