"""Words for Codewörter: common, family-friendly German nouns (many with more than one meaning).

No word is the beginning or end of another one (no "Haus" next to "Baumhaus"), so hints stay fair.
"""

WORDS: list[str] = """
Bank Schloss Birne Strauß Kiefer Leiter Tor Ball Hahn Mutter Schimmel Zug Bauer Läufer Turm Dame König Krone Stern
Mond Sonne Feder Flügel Gericht Golf Kran Maus Fliege Krebs Kapelle Westen Ton Note Schlange Blatt Absatz Decke Gang
Hut Pass Bogen Schild Steuer Tau Weide Wurzel Stift Raupe Linse Riegel Rock Mine Kiwi Jaguar Fuchs Löwe Schnecke Nagel
Kamm Feld Taste Pflaster Platz Tafel Bremse Kater Schuppe Star Kegel Zylinder Boxer Löffel Glocke Ente Ritter Schalter
Brücke Erde Welle Quelle Wolke Nebel Blitz Donner Wind Feuer Rauch Insel Wüste Vulkan Höhle Stein Sand Schnee Regen
Komet Planet Gletscher Moos Pilz Kaktus Palme Eiche Tanne Dorn Wald Wiese Berg Fluss Meer Strand Rose Tulpe Gras Hund
Katze Pferd Kuh Schwein Schaf Ziege Huhn Gans Wolf Bär Hase Igel Eule Adler Rabe Spatz Möwe Pinguin Tiger Elefant
Giraffe Zebra Gorilla Krokodil Frosch Kröte Spinne Biene Wespe Ameise Mücke Käfer Hai Delfin Krake Qualle Muschel
Robbe Otter Biber Hirsch Reh Elch Kamel Lama Panda Koala Känguru Papagei Flamingo Pfau Storch Schwan Drache Einhorn
Apfel Banane Kirsche Zitrone Orange Traube Melone Erdbeere Nuss Kartoffel Tomate Gurke Zwiebel Möhre Kohl Salat Brot
Kuchen Keks Honig Zucker Salz Pfeffer Butter Käse Milch Sahne Nudel Suppe Pizza Wurst Schinken Pommes Schokolade
Bonbon Kaugummi Marmelade Senf Waffel Brezel Popcorn Tee Kaffee Saft Wasser Tisch Stuhl Bett Sofa Schrank Lampe
Spiegel Uhr Tür Fenster Treppe Teppich Vorhang Kissen Kerze Vase Tasse Teller Gabel Messer Topf Pfanne Flasche Glas
Eimer Besen Schere Nadel Faden Knopf Schlüssel Kette Ring Brille Mütze Schuh Stiefel Socke Hose Kleid Jacke Mantel
Hemd Gürtel Krawatte Tasche Koffer Rucksack Schirm Bürste Seife Wecker Telefon Radio Fernseher Computer Kamera
Batterie Kabel Stecker Magnet Hammer Schraube Zange Säge Seil Netz Korb Kiste Paket Brief Karte Buch Heft Farbe Papier
Zeitung Bild Rahmen Puppe Teddy Würfel Puzzle Murmel Pfeife Trommel Gitarre Geige Klavier Flöte Trompete Harfe Schule
Kirche Burg Straße Tunnel Bahnhof Hafen Markt Laden Kino Theater Zirkus Zoo Museum Bibliothek Hotel Garten Park
Stadion Dorf Stadt Keller Dach Küche Garage Mauer Zaun Kamin Brunnen Pyramide Iglu Zelt Hütte Palast Labor Fabrik
Mühle Post Auto Bus Fahrrad Roller Schiff Boot Rakete Hubschrauber Bagger Taxi Kutsche Schlitten Anker Segel Reifen
Ampel Prinzessin Pirat Hexe Zauberer Riese Zwerg Engel Gespenst Roboter Detektiv Polizist Arzt Koch Bäcker Fischer
Jäger Lehrer Pilot Astronaut Clown Kapitän Cowboy Ninja Spion Vampir Mumie Monster Held Kaiser Richter Maler Sänger
Tänzer Gärtner Kopf Auge Nase Mund Ohr Zahn Zunge Hals Hand Finger Bein Knie Herz Haar Bart Rücken Bauch Daumen
Schulter Lippe Stirn Musik Traum Glück Geheimnis Rätsel Schatz Gold Silber Diamant Perle Münze Geld Kreuz Pfeil
Schwert Rüstung Helm Kanone Falle Code Laser Satellit Mikroskop Lupe Atom Geschenk Geburtstag Hochzeit Urlaub Ferien
Reise Spiel Sport Tanz Lied Film Bühne Maske Kostüm Fahne Wappen Thron Ticket Stempel Siegel Wolle Leder Seide Holz
Eisen Stahl Kupfer Kristall Linie Kreis Punkt Zahl Welt Norden Süden Winter Sommer Frühling Herbst Nacht Woche Berlin
Paris London Afrika Amerika Antarktis Alpen Venedig Hollywood Ägypten Japan China Indien Mexiko Olympia Jupiter Venus
Galaxie Mikrofon Orchester Konzert Karneval Weihnachten Silvester Picknick Wanderung Tresor Krimi Märchen Sage Bande
Schlag Schatten Spur Wippe Schaukel Rutsche Trampolin Pullover Schürze Kittel Kapuze Kleber Tinte Kreide Lineal Zirkel
Atlas Kalender Thermometer Waage Spritze Pille Verband Krücke Wiege Schnuller Rassel
""".split()

# Keep the order but drop accidental duplicates.
WORDS = list(dict.fromkeys(WORDS))
