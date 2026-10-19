# Fabians-HA-Karte

Deine Karte der Restaurants, Cafés und Bars, in denen du warst – mit Speisekarte, was du bestellt
hast, Fotos, deiner Bewertung und dem, was das Internet über den Ort weiß.

## So kommt etwas auf die Karte

Du schreibst einfach dem **Fabians-HA-Assistenten**, z. B.:

- Foto der **Speisekarte** + „Hab die Pizza Diavola und eine Cola genommen“
- Foto vom **Essen** oder vom **Beleg**
- „Bin im Café Extrablatt, trag das ein“

Der Assistent liest Name, Adresse, Gerichte und Preise von der Karte und deine Bestellung aus und
schickt alles hierher. Den Ort nimmt er von deinem **aktuellen Standort** (Home-Assistant-App auf dem
Handy). Warst du woanders oder trägst du es später ein, sag ihm wo – oder schick einen Standort.

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

## Einrichtung

- **Fabians-HA-Master** und **Fabians-HA-Assistent** müssen laufen (der Abgleich nutzt Claude über
  den Assistenten, die Meldungen gehen über den Master).
- Für den Standort braucht es die **Home-Assistant-App** auf dem Handy mit erlaubtem Standort.
  Gibt es mehrere Personen, unter **Konfiguration** bei *Person für den Standort* z. B.
  `person.fabian` eintragen.

Die Karte ist nur über Home Assistant und für den Assistenten erreichbar. Fotos und Daten liegen im
Add-on (in Home-Assistant-Backups enthalten). Kartenbilder kommen von OpenStreetMap.
