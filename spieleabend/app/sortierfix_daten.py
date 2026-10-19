"""Item sets for Sortierfix.

Each set: (question, top label, bottom label, descending?, unit, items). Items are (name, value) or
(name, value, label shown at the reveal). Values are commonly cited figures; "etwa" values are rounded.
Each round uses five items of a set, so a set with more items plays differently each time.
"""

# Years: earliest first.
GESCHICHTE = [
    ("Welche Erfindung kam zuerst?", "früher", "später", False, "", [
        ("Dampfmaschine von James Watt", 1769), ("Telefon von Bell", 1876), ("Benz Patent-Motorwagen", 1886),
        ("Erster Motorflug der Brüder Wright", 1903), ("Erste Website im World Wide Web", 1991), ("Erstes iPhone", 2007)]),
    ("Was geschah zuerst?", "früher", "später", False, "", [
        ("Kolumbus erreicht Amerika", 1492), ("Luthers 95 Thesen", 1517), ("Französische Revolution", 1789),
        ("Beginn des Ersten Weltkriegs", 1914), ("Erste Mondlandung", 1969), ("Fall der Berliner Mauer", 1989),
        ("Euro-Bargeld wird eingeführt", 2002)]),
    ("Wer wurde zuerst geboren?", "früher", "später", False, "", [
        ("Martin Luther", 1483), ("William Shakespeare", 1564), ("Isaac Newton", 1643),
        ("Johann Wolfgang von Goethe", 1749), ("Napoleon Bonaparte", 1769), ("Marie Curie", 1867), ("Albert Einstein", 1879)]),
    ("Welches Unternehmen wurde zuerst gegründet?", "früher", "später", False, "", [
        ("LEGO", 1932), ("adidas", 1949), ("Microsoft", 1975), ("Apple", 1976),
        ("Amazon", 1994), ("Google", 1998), ("Facebook", 2004)]),
    ("Welche Spielkonsole erschien zuerst?", "früher", "später", False, "", [
        ("Nintendo Famicom / NES", 1983, "1983 (Japan)"), ("Game Boy", 1989), ("PlayStation", 1994), ("Nintendo 64", 1996),
        ("PlayStation 2", 2000), ("Nintendo Wii", 2006), ("Nintendo Switch", 2017)]),
    ("Welcher Film kam zuerst ins Kino?", "früher", "später", False, "", [
        ("Krieg der Sterne", 1977), ("E.T. – Der Außerirdische", 1982), ("Zurück in die Zukunft", 1985),
        ("Jurassic Park", 1993), ("Titanic", 1997), ("Der Herr der Ringe: Die Gefährten", 2001), ("Avatar", 2009)]),
    ("Wer wurde zuerst Bundeskanzler?", "früher", "später", False, "", [
        ("Konrad Adenauer", 1949), ("Ludwig Erhard", 1963), ("Willy Brandt", 1969), ("Helmut Schmidt", 1974),
        ("Helmut Kohl", 1982), ("Gerhard Schröder", 1998), ("Angela Merkel", 2005), ("Olaf Scholz", 2021)]),
    ("Welches Bauwerk wurde zuerst fertig?", "früher", "später", False, "", [
        ("Kölner Dom", 1880), ("Freiheitsstatue", 1886), ("Eiffelturm", 1889), ("Empire State Building", 1931),
        ("Golden Gate Bridge", 1937), ("Sydney Opera House", 1973), ("Burj Khalifa", 2010)]),
    ("Wo fanden die Olympischen Sommerspiele zuerst statt?", "früher", "später", False, "", [
        ("Berlin", 1936), ("München", 1972), ("Moskau", 1980), ("Barcelona", 1992), ("Sydney", 2000),
        ("Peking", 2008), ("London", 2012), ("Rio de Janeiro", 2016), ("Paris", 2024)]),
    ("Was geschah zuerst in der deutschen Geschichte?", "früher", "später", False, "", [
        ("Revolution von 1848/49", 1848), ("Gründung des Deutschen Kaiserreichs", 1871), ("Weimarer Verfassung", 1919),
        ("Gründung der Bundesrepublik", 1949), ("Bau der Berliner Mauer", 1961), ("Wiedervereinigung", 1990)]),
    ("Was geschah zuerst?", "früher", "später", False, "", [
        ("Gründung Roms (nach der Sage)", -753, "753 v. Chr."), ("Ermordung Julius Caesars", -44, "44 v. Chr."),
        ("Ende des Weströmischen Reichs", 476), ("Kaiserkrönung Karls des Großen", 800), ("Magna Carta", 1215),
        ("Eroberung Konstantinopels durch die Osmanen", 1453)]),
    ("Was geschah zuerst in der Raumfahrt?", "früher", "später", False, "", [
        ("Start von Sputnik 1", 1957), ("Juri Gagarin im All", 1961), ("Erste Mondlandung", 1969),
        ("Sigmund Jähn als erster Deutscher im All", 1978), ("Erster Flug eines Space Shuttles", 1981),
        ("Erstes Modul der ISS im All", 1998), ("Rover Curiosity landet auf dem Mars", 2012)]),
    ("Welcher Titel kam zuerst? (Fußball-Männer)", "früher", "später", False, "", [
        ("WM-Titel in Bern", 1954), ("Erster EM-Titel", 1972), ("WM-Titel im eigenen Land", 1974),
        ("EM-Titel in Italien", 1980), ("WM-Titel in Italien", 1990), ("EM-Titel in England", 1996), ("WM-Titel in Brasilien", 2014)]),
]

GEOGRAFIE = [
    ("Welcher Berg ist am höchsten?", "am höchsten", "am niedrigsten", True, "m", [
        ("Mount Everest", 8849), ("K2", 8611), ("Aconcagua", 6961), ("Denali", 6190), ("Kilimandscharo", 5895),
        ("Mont Blanc", 4806), ("Matterhorn", 4478), ("Zugspitze", 2962)]),
    ("Welcher Fluss ist am längsten?", "am längsten", "am kürzesten", True, "km", [
        ("Nil", 6650), ("Wolga", 3530), ("Donau", 2857), ("Rhein", 1233), ("Elbe", 1094), ("Main", 527), ("Themse", 346)]),
    ("Welches Land ist am größten (Fläche)?", "am größten", "am kleinsten", True, "Mio. km²", [
        ("Russland", 17.1), ("Kanada", 9.98), ("Brasilien", 8.5), ("Australien", 7.7), ("Indien", 3.3),
        ("Mexiko", 1.96), ("Deutschland", 0.36)]),
    ("Welches Land hat die meisten Einwohner?", "die meisten", "die wenigsten", True, "Mio.", [
        ("Indien", 1440), ("USA", 340), ("Indonesien", 280), ("Brasilien", 212), ("Japan", 124),
        ("Deutschland", 84), ("Frankreich", 68), ("Spanien", 48)]),
    ("Welche Stadt hat die meisten Einwohner?", "die meisten", "die wenigsten", True, "Mio.", [
        ("Berlin", 3.8), ("Hamburg", 1.9), ("München", 1.5), ("Köln", 1.08), ("Frankfurt am Main", 0.77),
        ("Dortmund", 0.59), ("Kiel", 0.25)]),
    ("Welches Bundesland ist am größten (Fläche)?", "am größten", "am kleinsten", True, "km²", [
        ("Bayern", 70550), ("Niedersachsen", 47710), ("Baden-Württemberg", 35750), ("Nordrhein-Westfalen", 34110),
        ("Brandenburg", 29650), ("Hessen", 21120), ("Saarland", 2570), ("Berlin", 891), ("Bremen", 420)]),
    ("Welcher See ist am größten?", "am größten", "am kleinsten", True, "km²", [
        ("Kaspisches Meer", 371000), ("Oberer See", 82100), ("Victoriasee", 68800), ("Baikalsee", 31500),
        ("Ladogasee", 17700), ("Bodensee", 536), ("Müritz", 117)]),
    ("Welches Bauwerk ist am höchsten?", "am höchsten", "am niedrigsten", True, "m", [
        ("Burj Khalifa", 828), ("Shanghai Tower", 632), ("One World Trade Center", 541), ("Berliner Fernsehturm", 368),
        ("Eiffelturm", 330), ("Kölner Dom", 157), ("Big Ben (Elizabeth Tower)", 96)]),
    ("Welcher Ozean ist am größten?", "am größten", "am kleinsten", True, "Mio. km²", [
        ("Pazifik", 165), ("Atlantik", 106), ("Indischer Ozean", 70), ("Südlicher Ozean", 22), ("Arktischer Ozean", 14)]),
    ("Welcher Kontinent ist am größten?", "am größten", "am kleinsten", True, "Mio. km²", [
        ("Asien", 44.6), ("Afrika", 30.3), ("Nordamerika", 24.7), ("Südamerika", 17.8), ("Antarktika", 14.2),
        ("Europa", 10.2), ("Australien", 7.7)]),
    ("Welche Insel ist am größten?", "am größten", "am kleinsten", True, "km²", [
        ("Grönland", 2166000), ("Neuguinea", 786000), ("Borneo", 743000), ("Madagaskar", 587000),
        ("Großbritannien", 209000), ("Island", 103000), ("Sizilien", 25700), ("Rügen", 926)]),
    ("Welcher deutsche Berg ist am höchsten?", "am höchsten", "am niedrigsten", True, "m", [
        ("Zugspitze", 2962), ("Watzmann", 2713), ("Feldberg (Schwarzwald)", 1493), ("Großer Arber", 1456),
        ("Fichtelberg", 1215), ("Brocken", 1141), ("Wasserkuppe", 950)]),
    ("Welche Stadt liegt am weitesten im Norden?", "Norden", "Süden", True, "° N", [
        ("Flensburg", 54.78), ("Hamburg", 53.55), ("Berlin", 52.52), ("Köln", 50.94), ("Frankfurt am Main", 50.11),
        ("Stuttgart", 48.78), ("München", 48.14), ("Konstanz", 47.66)]),
    ("Welche Hauptstadt liegt am weitesten im Westen?", "Westen", "Osten", False, "° O", [
        ("Lissabon", -9.14, "9,14° W"), ("Madrid", -3.70, "3,70° W"), ("Paris", 2.35), ("Berlin", 13.40),
        ("Wien", 16.37), ("Warschau", 21.01), ("Moskau", 37.62)]),
    ("Welcher Tunnel ist am längsten?", "am längsten", "am kürzesten", True, "km", [
        ("Gotthard-Basistunnel", 57.1), ("Seikan-Tunnel (Japan)", 53.9), ("Eurotunnel", 50.5),
        ("Lötschberg-Basistunnel", 34.6), ("Neuer Elbtunnel (Hamburg)", 3.3)]),
    ("Welches Land ist am größten (Fläche)?", "am größten", "am kleinsten", True, "km²", [
        ("Frankreich (europäischer Teil)", 551700), ("Spanien", 506000), ("Schweden", 450300), ("Deutschland", 357600),
        ("Polen", 312700), ("Österreich", 83900), ("Schweiz", 41300), ("Luxemburg", 2590)]),
    ("Welche Stadt liegt am höchsten?", "am höchsten", "am tiefsten", True, "m ü. M.", [
        ("La Paz", 3640, "etwa 3640 m"), ("Quito", 2850, "etwa 2850 m"), ("Bogotá", 2640, "etwa 2640 m"),
        ("Mexiko-Stadt", 2240, "etwa 2240 m"), ("Madrid", 657, "etwa 650 m"), ("München", 519, "etwa 520 m"), ("Berlin", 34, "etwa 34 m")]),
]

NATUR = [
    ("Welcher Planet ist der Sonne am nächsten?", "am nächsten", "am weitesten weg", False, "Mio. km", [
        ("Merkur", 58), ("Venus", 108), ("Erde", 150), ("Mars", 228), ("Jupiter", 778), ("Saturn", 1434),
        ("Uranus", 2871), ("Neptun", 4495)]),
    ("Welcher Planet ist am größten?", "am größten", "am kleinsten", True, "km Durchmesser", [
        ("Jupiter", 139820), ("Saturn", 116460), ("Uranus", 50724), ("Neptun", 49244), ("Erde", 12742),
        ("Venus", 12104), ("Mars", 6779), ("Merkur", 4879)]),
    ("Wer ist am schnellsten?", "am schnellsten", "am langsamsten", True, "km/h", [
        ("Gepard", 100, "etwa 100 km/h"), ("Löwe", 80, "etwa 80 km/h"), ("Rennpferd", 70, "etwa 70 km/h"),
        ("Grizzlybär", 55, "etwa 55 km/h"), ("Usain Bolt (Spitze)", 44.7, "etwa 44,7 km/h")]),
    ("Welches Tier ist am schwersten?", "am schwersten", "am leichtesten", True, "kg", [
        ("Blauwal", 150000, "bis 150 t"), ("Afrikanischer Elefant", 6000, "etwa 6 t"), ("Breitmaulnashorn", 2300, "etwa 2,3 t"),
        ("Eisbär (Männchen)", 450, "etwa 450 kg"), ("Löwe (Männchen)", 190, "etwa 190 kg"), ("Hauskatze", 4, "etwa 4 kg")]),
    ("Welches Element hat die kleinste Ordnungszahl?", "kleinste", "größte", False, "", [
        ("Wasserstoff", 1), ("Helium", 2), ("Kohlenstoff", 6), ("Sauerstoff", 8), ("Eisen", 26), ("Kupfer", 29),
        ("Silber", 47), ("Gold", 79), ("Uran", 92)]),
    ("Was ist am heißesten?", "am heißesten", "am kältesten", True, "°C", [
        ("Oberfläche der Sonne", 5500, "etwa 5500 °C"), ("Wasser kocht", 100), ("Körpertemperatur des Menschen", 37),
        ("Eis schmilzt", 0), ("Quecksilber erstarrt", -39), ("Flüssiger Stickstoff siedet", -196),
        ("Absoluter Nullpunkt", -273.15)]),
    ("Wer ist am längsten trächtig / schwanger?", "am längsten", "am kürzesten", True, "Tage", [
        ("Afrikanischer Elefant", 660, "etwa 22 Monate"), ("Giraffe", 450, "etwa 15 Monate"), ("Pferd", 335, "etwa 11 Monate"),
        ("Mensch", 280, "etwa 9 Monate"), ("Hausschwein", 115, "etwa 115 Tage"), ("Hund", 63, "etwa 63 Tage"),
        ("Goldhamster", 17, "etwa 16–18 Tage")]),
    ("Welcher Vogel hat die größte Flügelspannweite?", "am größten", "am kleinsten", True, "m", [
        ("Wanderalbatros", 3.5, "bis etwa 3,5 m"), ("Steinadler", 2.2, "bis etwa 2,2 m"), ("Mäusebussard", 1.2, "etwa 1,2 m"),
        ("Amsel", 0.37, "etwa 37 cm"), ("Blaumeise", 0.19, "etwa 19 cm")]),
    ("Was ist am nächsten an der Erde?", "am nächsten", "am weitesten weg", False, "km", [
        ("Internationale Raumstation ISS", 400, "etwa 400 km"), ("Geostationäre Satelliten", 35786, "35.786 km"),
        ("Mond", 384400, "384.400 km"), ("Sonne", 149.6e6, "149,6 Mio. km"), ("Proxima Centauri", 4.0e13, "4,2 Lichtjahre"),
        ("Andromedagalaxie", 2.4e19, "2,5 Mio. Lichtjahre")]),
    ("Welches Mineral ist am härtesten? (Mohs-Skala)", "am härtesten", "am weichsten", True, "Mohs", [
        ("Diamant", 10), ("Korund", 9), ("Topas", 8), ("Quarz", 7), ("Orthoklas", 6), ("Apatit", 5),
        ("Fluorit", 4), ("Calcit", 3), ("Gips", 2), ("Talk", 1)]),
    ("Wer hat die meisten Beine?", "die meisten", "die wenigsten", True, "Beine", [
        ("Hummer", 10), ("Spinne", 8), ("Ameise", 6), ("Pferd", 4), ("Strauß", 2)]),
    ("Welches Gas hat den größten Anteil an der Luft?", "am meisten", "am wenigsten", True, "%", [
        ("Stickstoff", 78.08), ("Sauerstoff", 20.95), ("Argon", 0.93), ("Kohlendioxid", 0.042), ("Neon", 0.0018)]),
    ("Was ist am schnellsten?", "am schnellsten", "am langsamsten", True, "km/h", [
        ("Concorde (Reiseflug)", 2180, "etwa 2180 km/h"), ("Airbus A380 (Reiseflug)", 900, "etwa 900 km/h"),
        ("ICE 3 im Linienbetrieb", 300, "bis 300 km/h"), ("Radprofi im Zielsprint", 70, "etwa 70 km/h"),
        ("Usain Bolt (Spitze)", 44.7, "etwa 44,7 km/h"), ("Weinbergschnecke", 0.005, "etwa 5 m pro Stunde")]),
]

KULTUR = [
    ("Was hat die meisten Kalorien pro 100 g?", "am meisten", "am wenigsten", True, "kcal", [
        ("Butter", 740, "etwa 740 kcal"), ("Vollmilchschokolade", 535, "etwa 535 kcal"), ("Gouda", 356, "etwa 360 kcal"),
        ("Weißbrot", 250, "etwa 250 kcal"), ("Banane", 90, "etwa 90 kcal"), ("Apfel", 52, "etwa 50 kcal"), ("Gurke", 12, "etwa 12 kcal")]),
    ("Welcher Harry-Potter-Band erschien zuerst?", "früher", "später", False, "", [
        ("Der Stein der Weisen", 1997), ("Die Kammer des Schreckens", 1998), ("Der Gefangene von Askaban", 1999),
        ("Der Feuerkelch", 2000), ("Der Orden des Phönix", 2003), ("Der Halbblutprinz", 2005), ("Die Heiligtümer des Todes", 2007)]),
    ("Welcher Star-Wars-Film kam zuerst ins Kino?", "früher", "später", False, "", [
        ("Krieg der Sterne", 1977), ("Das Imperium schlägt zurück", 1980), ("Die Rückkehr der Jedi-Ritter", 1983),
        ("Episode I – Die dunkle Bedrohung", 1999), ("Episode II – Angriff der Klonkrieger", 2002),
        ("Episode III – Die Rache der Sith", 2005), ("Das Erwachen der Macht", 2015)]),
    ("Was ist am längsten?", "am längsten", "am kürzesten", True, "m", [
        ("Marathon", 42195, "42,195 km"), ("Halbmarathon", 21097.5, "21,0975 km"), ("Stadionrunde", 400),
        ("Fußballfeld (WM)", 105), ("Olympisches Schwimmbecken", 50), ("Basketballfeld", 28), ("Tennisplatz", 23.77)]),
    ("Welcher Ball ist am größten?", "am größten", "am kleinsten", True, "cm Durchmesser", [
        ("Basketball", 24, "etwa 24 cm"), ("Fußball", 22, "etwa 22 cm"), ("Handball (Männer)", 19, "etwa 19 cm"),
        ("Tennisball", 6.7, "etwa 6,7 cm"), ("Golfball", 4.27, "mindestens 4,27 cm"), ("Tischtennisball", 4.0, "4,0 cm")]),
    ("Wo stehen die meisten Spieler eines Teams auf dem Feld?", "die meisten", "die wenigsten", True, "Spieler", [
        ("Rugby (Union)", 15), ("Fußball", 11), ("Baseball", 9), ("Handball", 7), ("Volleyball", 6),
        ("Basketball", 5), ("Beachvolleyball", 2)]),
    ("Welcher Komponist wurde zuerst geboren?", "früher", "später", False, "", [
        ("Antonio Vivaldi", 1678), ("Johann Sebastian Bach", 1685), ("Joseph Haydn", 1732), ("Wolfgang Amadeus Mozart", 1756),
        ("Ludwig van Beethoven", 1770), ("Franz Schubert", 1797), ("Richard Wagner", 1813), ("Johannes Brahms", 1833)]),
    ("Welcher Tag kommt im Jahr zuerst?", "früher", "später", False, "", [
        ("Neujahr", 1, "1. Januar"), ("Heilige Drei Könige", 6, "6. Januar"), ("Valentinstag", 45, "14. Februar"),
        ("Tag der Arbeit", 121, "1. Mai"), ("Tag der Deutschen Einheit", 276, "3. Oktober"),
        ("Halloween / Reformationstag", 304, "31. Oktober"), ("Nikolaus", 340, "6. Dezember"), ("Silvester", 365, "31. Dezember")]),
    ("Welches Bauwerk ist am ältesten?", "am ältesten", "am jüngsten", False, "", [
        ("Cheops-Pyramide", -2560, "um 2560 v. Chr."), ("Kolosseum in Rom", 80, "80 n. Chr."), ("Hagia Sophia", 537),
        ("Kölner Dom (Grundsteinlegung)", 1248), ("Taj Mahal", 1648, "um 1648"), ("Schloss Neuschwanstein (Baubeginn)", 1869),
        ("Eiffelturm", 1889)]),
    ("Welcher Disney-Film kam zuerst ins Kino?", "früher", "später", False, "", [
        ("Schneewittchen und die sieben Zwerge", 1937), ("Cinderella", 1950), ("Das Dschungelbuch", 1967),
        ("Arielle, die Meerjungfrau", 1989), ("Der König der Löwen", 1994), ("Die Eiskönigin", 2013)]),
    ("Welches Spiel erschien zuerst?", "früher", "später", False, "", [
        ("Mensch ärgere Dich nicht", 1914), ("Monopoly", 1935), ("Tetris", 1984), ("Die Siedler von Catan", 1995),
        ("Minecraft (Vollversion)", 2011)]),
    ("Welches Buch erschien zuerst?", "früher", "später", False, "", [
        ("Goethes „Faust I“", 1808), ("„Max und Moritz“", 1865), ("„Der Hobbit“", 1937),
        ("„Die unendliche Geschichte“", 1979), ("„Harry Potter und der Stein der Weisen“", 1997)]),
    ("Welche Euro-Münze ist am schwersten?", "am schwersten", "am leichtesten", True, "g", [
        ("2 Euro", 8.5), ("50 Cent", 7.8), ("1 Euro", 7.5), ("20 Cent", 5.74), ("10 Cent", 4.1),
        ("5 Cent", 3.92), ("2 Cent", 3.06), ("1 Cent", 2.3)]),
]

# Metal construction (Metallbau apprenticeship): table values.
METALL = [
    ("Welches Metall schmilzt bei der höchsten Temperatur?", "am höchsten", "am niedrigsten", True, "°C", [
        ("Wolfram", 3422), ("Eisen", 1538), ("Kupfer", 1085), ("Aluminium", 660), ("Zink", 420), ("Blei", 327), ("Zinn", 232)]),
    ("Welcher Werkstoff hat die größte Dichte?", "am schwersten", "am leichtesten", True, "g/cm³", [
        ("Blei", 11.3), ("Kupfer", 8.96), ("Stahl", 7.85), ("Zink", 7.14), ("Titan", 4.5), ("Aluminium", 2.7), ("Magnesium", 1.74)]),
    ("Welches Profil ist pro Meter am schwersten?", "am schwersten", "am leichtesten", True, "kg/m", [
        ("HEM 200", 103), ("IPE 400", 66.3), ("HEB 200", 61.3), ("HEA 200", 42.3), ("IPE 200", 22.4), ("IPE 100", 8.1)]),
    ("Welcher Werkstoff leitet Wärme am besten?", "am besten", "am schlechtesten", True, "W/(m·K)", [
        ("Silber", 429), ("Kupfer", 401), ("Gold", 318), ("Aluminium (rein)", 237), ("Eisen (rein)", 80),
        ("Edelstahl 1.4301", 15)]),
    ("Was hat die höchste Streckgrenze (Mindestwert)?", "am höchsten", "am niedrigsten", True, "N/mm²", [
        ("Schraube 12.9", 1080), ("Schraube 10.9", 900), ("Schraube 8.8", 640), ("Baustahl S355", 355),
        ("Baustahl S235", 235), ("Aluminium EN AW-6060 T66", 150)]),
]

# Category id (the settings send numbers) → name and sets. 0 mixes the general ones; Metallbau only when chosen.
CATEGORIES = {
    0: ("Alles gemischt", GESCHICHTE + GEOGRAFIE + NATUR + KULTUR),
    1: ("Geschichte & Jahreszahlen", GESCHICHTE),
    2: ("Erde & Länder", GEOGRAFIE),
    3: ("Natur & Technik", NATUR),
    4: ("Kultur, Sport & Alltag", KULTUR),
    5: ("Metallbau (Ausbildung)", METALL),
}
