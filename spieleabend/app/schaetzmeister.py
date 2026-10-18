"""Schätzmeister: an estimation question, everyone types a number – the closest guesses score."""

import random
import re

from common import RuleError
from party import PartyGame

# (question, answer, unit, note) – answers are commonly cited values, rounded where it says "etwa".
WELT = [
    ("Wie hoch ist der Mount Everest?", 8849, "m", ""),
    ("Wie hoch ist die Zugspitze?", 2962, "m", ""),
    ("Wie hoch ist der Kilimandscharo?", 5895, "m", ""),
    ("Wie hoch ist der Eiffelturm mit Antennen?", 330, "m", ""),
    ("Wie hoch ist der Kölner Dom?", 157, "m", ""),
    ("Wie hoch ist das Burj Khalifa in Dubai?", 828, "m", ""),
    ("Wie viele Stockwerke hat das Burj Khalifa?", 163, "", ""),
    ("Wie hoch ist das Brandenburger Tor?", 26, "m", ""),
    ("Wie lang ist der Rhein?", 1233, "km", ""),
    ("Wie lang ist der Panamakanal?", 82, "km", "etwa"),
    ("Wie weit ist der Mond im Mittel von der Erde entfernt?", 384400, "km", ""),
    ("Wie viele Kilometer misst der Erdumfang am Äquator?", 40075, "km", ""),
    ("Wie groß ist der Durchmesser der Erde?", 12742, "km", "im Mittel"),
    ("Wie tief ist die tiefste Stelle des Marianengrabens?", 10994, "m", "etwa"),
    ("Wie lang ist die Chinesische Mauer mit allen Abschnitten?", 21196, "km", "laut Vermessung 2012"),
    ("Wie groß ist Deutschland?", 357600, "km²", "etwa"),
    ("Wie groß ist der Bodensee?", 536, "km²", ""),
    ("Wie weit ist es von Berlin nach München – Luftlinie?", 504, "km", "etwa"),
    ("Wie viele Kilometer Autobahn gibt es in Deutschland?", 13200, "km", "etwa"),
    ("Wie lang ist ein Fußballfeld bei einer WM?", 105, "m", ""),
    ("Wie lang ist ein Marathon?", 42195, "m", ""),
    ("Wie schnell ist das Licht?", 299792, "km/s", ""),
    ("Wie viele Sekunden braucht das Sonnenlicht bis zur Erde?", 499, "s", "etwa 8 Minuten 19 Sekunden"),
    ("Wie viele Tage braucht der Mond für eine Runde um die Erde?", 27.3, "Tage", "siderisch"),
    ("Wie alt ist das Universum?", 13.8, "Mrd. Jahre", ""),
    ("Wie viel Prozent der Erdoberfläche sind mit Wasser bedeckt?", 71, "%", ""),
    ("Wie viele Länder sind Mitglied der Vereinten Nationen?", 193, "", ""),
    ("Wie viele Sprachen gibt es auf der Welt?", 7000, "", "etwa"),
    ("Wie viele Menschen leben auf der Erde?", 8.1, "Mrd.", "etwa, 2024"),
    ("Wie viele Menschen leben in Deutschland?", 84, "Mio.", "etwa"),
    ("Wie viele Menschen leben in Berlin?", 3.8, "Mio.", "etwa"),
]

GESCHICHTE = [
    ("In welchem Jahr fiel die Berliner Mauer?", 1989, "", ""),
    ("In welchem Jahr wurde die Bundesrepublik Deutschland gegründet?", 1949, "", ""),
    ("In welchem Jahr landeten die ersten Menschen auf dem Mond?", 1969, "", ""),
    ("In welchem Jahr sank die Titanic?", 1912, "", ""),
    ("In welchem Jahr fand die erste Fußball-WM statt?", 1930, "", ""),
    ("In welchem Jahr wurde das Euro-Bargeld eingeführt?", 2002, "", ""),
    ("In welchem Jahr wurde Google gegründet?", 1998, "", ""),
    ("In welchem Jahr wurde das erste iPhone vorgestellt?", 2007, "", ""),
    ("In welchem Jahr erschien das erste Harry-Potter-Buch?", 1997, "", ""),
    ("In welchem Jahr wurde Coca-Cola erfunden?", 1886, "", ""),
    ("In welchem Jahr wurde Albert Einstein geboren?", 1879, "", ""),
    ("Um welches Jahr druckte Gutenberg mit beweglichen Lettern?", 1450, "", "etwa"),
    ("Wie alt wurde Johann Wolfgang von Goethe?", 82, "Jahre", ""),
]

ALLTAG = [
    ("Wie viele Knochen hat ein erwachsener Mensch?", 206, "", ""),
    ("Wie viele Zähne hat ein Erwachsener mit Weisheitszähnen?", 32, "", ""),
    ("Wie viele Liter Blut hat ein erwachsener Mensch?", 5, "Liter", "etwa"),
    ("Wie viele Haare wachsen auf einem menschlichen Kopf?", 100000, "", "etwa"),
    ("Wie viele Herzen hat ein Oktopus?", 3, "", ""),
    ("Wie viele Tasten hat ein Klavier?", 88, "", ""),
    ("Wie viele Sinfonien hat Beethoven komponiert?", 9, "", ""),
    ("Wie viele Felder hat ein Schachbrett?", 64, "", ""),
    ("Wie viele Karten hat ein Skatblatt?", 32, "", ""),
    ("Wie viele Augen hat ein normaler Spielwürfel zusammen?", 21, "", ""),
    ("Wie viele Sterne sind auf der Europaflagge?", 12, "", ""),
    ("Wie viele Streifen hat die Flagge der USA?", 13, "", ""),
    ("Wie viele Minuten hat eine Woche?", 10080, "", ""),
    ("Wie viele Sekunden hat ein Tag?", 86400, "", ""),
    ("Bei wie viel Grad Fahrenheit kocht Wasser?", 212, "°F", ""),
    ("Wie viele Kalorien haben 100 g Butter?", 740, "kcal", "etwa"),
    ("Wie viele Tore fielen beim WM-Halbfinale Brasilien gegen Deutschland 2014?", 8, "", "7:1"),
    ("Wie viele Stufen führen im Kölner Dom auf die Aussichtsplattform?", 533, "", ""),
    ("Wie viele Monde hat der Mars?", 2, "", ""),
    ("Wie viele Minuten dauert ein Handballspiel ohne Verlängerung?", 60, "min", ""),
]

# Metal construction (Metallbau apprenticeship): materials, workshop, welding, standards. Table values.
METALL = [
    ("Bei wie viel Grad schmilzt reines Eisen?", 1538, "°C", ""),
    ("Bei wie viel Grad schmilzt Aluminium?", 660, "°C", ""),
    ("Bei wie viel Grad schmilzt Kupfer?", 1085, "°C", ""),
    ("Bei wie viel Grad schmilzt Zink?", 420, "°C", "etwa"),
    ("Wie heiß ist das Zinkbad beim Feuerverzinken?", 450, "°C", "etwa"),
    ("Ab wie viel Grad Arbeitstemperatur spricht man von Hartlöten statt Weichlöten?", 450, "°C", ""),
    ("Wie heiß wird eine Acetylen-Sauerstoff-Flamme an der heißesten Stelle?", 3200, "°C", "etwa"),
    ("Bei wie viel Grad zeigt Stahl beim Anlassen die Anlassfarbe Strohgelb?", 220, "°C", "etwa"),
    ("Wie viel Kilogramm wiegt ein Kubikmeter Stahl?", 7850, "kg", ""),
    ("Welche Dichte hat Aluminium?", 2.7, "g/cm³", ""),
    ("Welche Dichte hat Kupfer?", 8.96, "g/cm³", ""),
    ("Wie viel wiegt eine Stahlblechtafel 2000 × 1000 × 2 mm?", 31.4, "kg", "2 m × 1 m × 0,002 m × 7850 kg/m³"),
    ("Wie viel wiegt ein Flachstahl 50 × 10 mm mit 6 m Länge?", 23.55, "kg", "0,05 m × 0,01 m × 6 m × 7850 kg/m³"),
    ("Wie viel wiegt ein Rundstahl mit 20 mm Durchmesser und 1 m Länge?", 2.47, "kg", "etwa"),
    ("Wie viel wiegt 1 m Träger HEB 200?", 61.3, "kg", ""),
    ("Wie viel wiegt 1 m Träger IPE 200?", 22.4, "kg", ""),
    ("Wie groß ist der E-Modul von Stahl?", 210000, "N/mm²", ""),
    ("Wie groß ist der E-Modul von Aluminium?", 70000, "N/mm²", "etwa"),
    ("Welche Mindeststreckgrenze hat ein S355?", 355, "N/mm²", "bei Dicken bis 16 mm"),
    ("Welche Mindestzugfestigkeit hat eine Schraube der Festigkeitsklasse 8.8?", 800, "N/mm²", "Nennwert"),
    ("Welche Streckgrenze hat eine Schraube der Festigkeitsklasse 8.8?", 640, "N/mm²", "0,8 × 800"),
    ("Wie viel Prozent Kohlenstoff enthält ein C45?", 0.45, "%", ""),
    ("Ab wie viel Prozent Kohlenstoff spricht man von Gusseisen statt Stahl?", 2.06, "%", "nach dem Eisen-Kohlenstoff-Diagramm, teils auch 2,1 %"),
    ("Wie viel Prozent Chrom braucht ein Stahl mindestens, um als nichtrostend zu gelten?", 10.5, "%", ""),
    ("Wie viel Prozent Nickel enthält ein V2A-Stahl (1.4301) etwa?", 8, "%", "8 bis 10,5 %, Chrom etwa 18 %"),
    ("Wie viel Prozent CO₂ enthält das Mischgas M21 „Corgon 18“?", 18, "%", "Rest Argon"),
    ("Mit wie viel bar wird eine volle Argon-Flasche üblicherweise gefüllt?", 200, "bar", "es gibt auch 300-bar-Flaschen"),
    ("Wie viele Millimeter dehnt sich ein 10 m langer Stahlträger bei 50 °C Erwärmung aus?", 6, "mm", "0,012 mm pro Meter und Grad"),
    ("Wie viele Millimeter dehnt sich ein 10 m langes Aluprofil bei 50 °C Erwärmung aus?", 11.5, "mm", "etwa 0,023 mm pro Meter und Grad"),
    ("Welchen Spitzenwinkel hat ein normaler HSS-Spiralbohrer?", 118, "°", ""),
    ("Welchen Flankenwinkel hat ein metrisches Gewinde?", 60, "°", ""),
    ("Welche Steigung hat ein M10-Regelgewinde?", 1.5, "mm", ""),
    ("Welche Steigung hat ein M12-Regelgewinde?", 1.75, "mm", ""),
    ("Welchen Kernlochbohrer nimmt man für ein M8-Gewinde?", 6.8, "mm", ""),
    ("Welchen Kernlochbohrer nimmt man für ein M12-Gewinde?", 10.2, "mm", ""),
    ("Welche Schlüsselweite hat eine M10-Sechskantschraube nach ISO?", 16, "mm", "nach alter DIN 17 mm"),
    ("Welche Drehzahl ergibt sich für einen 10-mm-Bohrer bei 25 m/min Schnittgeschwindigkeit?", 796, "1/min", "n = v × 1000 / (π × d)"),
    ("Welche Stromstärke ergibt die Faustformel „Durchmesser × 40“ für eine 3,2-mm-Stabelektrode?", 128, "A", ""),
    ("Welches a-Maß ergibt die Faustformel a ≈ 0,7 × t für eine Kehlnaht an 10-mm-Blech?", 7, "mm", ""),
    ("Wie lang ist der Umfang eines Rohres mit 100 mm Außendurchmesser?", 314, "mm", "π × 100"),
    ("Wie groß ist die Allgemeintoleranz ISO 2768-m für ein Maß von 50 mm?", 0.3, "± mm", "Bereich über 30 bis 120 mm"),
    ("Wie viele Zentimeter dürfen Öffnungen in einem Geländer höchstens messen, damit kein Kinderkopf durchpasst?", 12, "cm", ""),
    ("Wie hoch muss ein Geländer bei bis zu 12 m Absturzhöhe nach den meisten Landesbauordnungen mindestens sein?", 90, "cm", "darüber meist 110 cm"),
    ("Wie viele Zentimeter ergibt die Schrittmaßregel 2 × Steigung + 1 × Auftritt?", 63, "cm", "59 bis 65 cm gelten als bequem"),
    ("Wie hoch darf eine Stufe einer notwendigen Treppe im Einfamilienhaus höchstens sein?", 20, "cm", "DIN 18065"),
    ("Wie viele Jahre dauert die Ausbildung zum Metallbauer regulär?", 3.5, "Jahre", ""),
]

# Category id (the settings send numbers) → name and questions. 0 mixes the general ones; specialist
# categories such as Metallbau are only asked when chosen.
CATEGORIES = {
    0: ("Allgemeinwissen gemischt", WELT + GESCHICHTE + ALLTAG),
    1: ("Erde, Länder & Weltall", WELT),
    2: ("Geschichte & Jahreszahlen", GESCHICHTE),
    3: ("Mensch & Alltag", ALLTAG),
    4: ("Metallbau (Ausbildung)", METALL),
}
QUESTIONS = CATEGORIES[0][1]


def parse_number(text: str) -> float | None:
    """German or English notation: "384.400", "8,1", "8.1", "1 000"."""
    raw = text.strip().replace(" ", "").replace("\u202f", "").replace("'", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", raw):
        raw = raw.replace(".", "")  # thousands separators
    try:
        return float(raw)
    except ValueError:
        return None


class Game(PartyGame):
    KIND = "schaetzmeister"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (8, 5, 10, 15)
    TIMES = (45, 30, 60, 0)
    INPUT_PHASES = ("guess",)

    def __init__(self, code: str):
        super().__init__(code)
        self.question = None
        self.ranking: list[dict] = []
        self.category = 0

    def configure_more(self, settings: dict) -> None:
        category = settings.get("category")
        self.category = int(category) if category is not None and int(category) in CATEGORIES else 0

    def settings_view(self) -> dict:
        return {**super().settings_view(), "category": self.category}

    def setup_round(self) -> None:
        questions = CATEGORIES[self.category][1]
        pool = [q for q in questions if q[0] not in self.used] or questions
        self.question = random.choice(pool)
        self.used.add(self.question[0])
        self.ranking = []
        self.begin("guess")

    def play(self, player, msg: dict) -> None:
        if msg.get("t") != "guess":
            raise RuleError("Unbekannte Aktion")
        value = parse_number(str(msg.get("value", "")))
        if value is None:
            raise RuleError("Bitte eine Zahl eingeben")
        if not (-1e12 < value < 1e12):
            raise RuleError("Diese Zahl ist zu groß")
        player.answer = value
        if self.done("answer"):
            self.advance()

    def advance(self) -> None:
        answer = self.question[1]
        guesses = [p for p in self.gamers if isinstance(p.answer, float)]
        guesses.sort(key=lambda p: abs(p.answer - answer))
        # 3 / 2 / 1 points for the three closest (equal distance = equal points), +2 for a bullseye (within 1 %).
        rank, last, ranking = 0, None, []
        for i, p in enumerate(guesses):
            diff = abs(p.answer - answer)
            if diff != last:
                rank, last = i, diff
            points = max(0, 3 - rank)
            exact = diff <= abs(answer) * 0.01
            p.gained = points + (2 if exact else 0)
            if exact:
                self.highlights = getattr(self, "highlights", []) + [(p.name, "volltreffer")]
            p.score += p.gained
            ranking.append({"id": p.id, "value": p.answer, "rank": rank + 1, "points": p.gained, "exact": exact})
        self.ranking = ranking
        self.begin("reveal", timed=False)
        if ranking:
            best = self.player(ranking[0]["id"])
            self.note(f"{best.name} lag am nächsten dran")

    def extra_view(self, me) -> dict:
        q, answer, unit, note = self.question or ("", 0, "", "")
        reveal = self.phase == "reveal"
        return {
            "question": q, "unit": unit, "category": CATEGORIES[self.category][0],
            "answer": answer if reveal else None, "note": note if reveal else "",
            "ranking": self.ranking if reveal else [],
            "my_answer": me.answer if me and isinstance(me.answer, float) else None,
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
