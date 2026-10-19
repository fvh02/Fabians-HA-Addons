"""Blind gezeichnet: everyone gets their own term and draws it on the phone – without seeing the
lines. Then the drawings are shown one by one and the others guess what they are meant to be.

Points: a correct guess earns GUESS_POINTS, the artist earns DRAW_POINTS for everyone who
recognised their drawing. One device can be the TV: it shows the drawings big."""

import random
import time

from common import RuleError
from kritzelpost import clean_strokes
from party import PartyGame, clean
from schnellmaler import distance, norm

GRACE = 3            # seconds after the visible drawing timer until missing drawings are taken as empty
GUESS_SECONDS = 25   # time to guess one drawing
OPTIONS = 6          # answers to choose from (in "Auswahl" mode)
GUESS_POINTS, DRAW_POINTS = 3, 2

# Simple things that work with a few lines – but are still hard enough without seeing them.
TERMS = """
Haus Baum Sonne Mond Stern Wolke Regenschirm Blume Pilz Kaktus Apfel Banane Birne Kirsche Erdbeere Ananas Karotte
Pizza Eis Torte Brezel Ei Tasse Flasche Gabel Löffel Messer Topf Glühbirne Kerze Lampe Uhr Wecker Brille Hut Krone
Schuh Socke Hose T-Shirt Handschuh Schal Ring Schlüssel Schloss Tür Fenster Leiter Zaun Brücke Turm Burg Kirche Zelt
Iglu Leuchtturm Auto Bus Zug Fahrrad Flugzeug Hubschrauber Rakete Schiff Segelboot Anker Traktor Ampel Ballon Kinderwagen
Hund Katze Maus Pferd Kuh Schwein Schaf Hase Igel Fuchs Bär Elefant Giraffe Schlange Krokodil Fisch Hai Wal Krake
Schnecke Spinne Biene Schmetterling Frosch Ente Huhn Eule Pinguin Vogel Dino Einhorn Drache Schildkröte Marienkäfer
Gitarre Trommel Klavier Trompete Mikrofon Kopfhörer Fernseher Handy Laptop Kamera Buch Brief Geschenk Ball Würfel
Pokal Medaille Schere Hammer Säge Besen Eimer Gießkanne Schneemann Regenbogen Blitz Vulkan Berg Insel Palme Herz
Smiley Gespenst Roboter Ufo Pirat Clown Zauberer Hexe Ritter König Prinzessin Astronaut Engel Weihnachtsbaum Kürbis
Skateboard Schaukel Rutsche Sandburg Lagerfeuer Angel Badewanne Toilette Zahnbürste Kamm Spiegel Bett Stuhl Tisch Sofa
""".split()
TERMS = list(dict.fromkeys(TERMS))


def same(guess: str, term: str) -> bool:
    """Typed guesses: case, umlauts, articles, plural endings and a small typo don't matter."""
    a = norm(guess)
    if not a:
        return False
    plain = term.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("Ä", "A").replace("Ö", "O").replace("Ü", "U")
    for b in {norm(term), norm(plain)}:
        if a == b or (len(b) >= 4 and a.startswith(b) and len(a) - len(b) <= 2):
            return True
        if len(b) >= 5 and distance(a, b) <= (1 if len(b) < 9 else 2):
            return True
    return False


class Game(PartyGame):
    KIND = "blindmaler"
    MIN_PLAYERS, MAX_PLAYERS = 3, 12
    ROUNDS = (2, 1, 3)
    TIMES = (30, 20, 45, 60)
    INPUT_PHASES = ("draw", "guess")

    def __init__(self, code: str):
        super().__init__(code)
        self.mode = 0                     # 0 = choose from options, 1 = type the answer
        self.terms: dict[str, str] = {}   # player id -> term of this round
        self.drawings: list[dict] = []    # all drawings of the game: {by, name, term, strokes, round, hits}
        self.queue: list[int] = []        # indices into drawings shown this round
        self.shown = 0                    # position in queue
        self.options: list[str] = []
        self.results: list[dict] = []
        self.blank: list[str] = []        # names of players who drew nothing this round

    def configure_more(self, settings: dict) -> None:
        mode = settings.get("mode")
        self.mode = int(mode) if mode is not None and int(mode) in (0, 1) else 0

    def settings_view(self) -> dict:
        return {**super().settings_view(), "mode": self.mode}

    def start(self) -> None:
        self.drawings = []
        super().start()

    # -- rounds --------------------------------------------------------------
    def setup_round(self) -> None:
        pool = [t for t in TERMS if t not in self.used]
        if len(pool) < len(self.gamers):
            pool = list(TERMS)
        terms = random.sample(pool, len(self.gamers))
        self.used.update(terms)
        self.terms = {p.id: t for p, t in zip(self.gamers, terms)}
        self.queue, self.shown, self.options, self.results, self.blank = [], 0, [], [], []
        self.phase = "draw"
        self.phase_end = time.time() + self.seconds + GRACE

    def phase_attr(self) -> str:
        return "answer" if self.phase == "draw" else "pick"

    @property
    def current(self) -> dict | None:
        if self.phase in ("guess", "reveal") and self.shown < len(self.queue):
            return self.drawings[self.queue[self.shown]]
        return None

    def advance(self) -> None:
        if self.phase == "draw":
            self._collect()
        elif self.phase == "guess":
            self._score()

    def _collect(self) -> None:
        """Drawing time is over: keep every drawing, show the ones with lines in random order."""
        start = len(self.drawings)
        for p in self.gamers:
            strokes = p.answer if isinstance(p.answer, list) else []
            self.drawings.append({"by": p.id, "name": p.name.removesuffix(" (Bot)"), "term": self.terms.get(p.id, "?"),
                                  "strokes": strokes, "round": self.round, "hits": 0})
            if not strokes:
                self.blank.append(p.name.removesuffix(" (Bot)"))
        self.queue = [i for i in range(start, len(self.drawings)) if self.drawings[i]["strokes"]]
        random.shuffle(self.queue)
        self.shown = 0
        if self.blank:
            self.note(f"Nichts gezeichnet: {', '.join(self.blank)}")
        if self.queue:
            self._show()
        else:
            self.results = []
            self.phase, self.phase_end = "reveal", 0.0

    def _show(self) -> None:
        drawing = self.current_for(self.shown)
        term = drawing["term"]
        # The other terms of this round make good wrong answers, the rest comes from the word list.
        others = [d["term"] for d in self.drawings if d["round"] == self.round and d["term"] != term]
        random.shuffle(others)
        decoys = others[:OPTIONS - 1]
        extra = [t for t in TERMS if t != term and t not in decoys]
        decoys += random.sample(extra, OPTIONS - 1 - len(decoys))
        self.options = decoys + [term]
        random.shuffle(self.options)
        for p in self.players:
            p.pick = None
            p.gained = 0
        artist = self.player(drawing["by"])
        if artist:
            artist.pick = ""     # the artist doesn't guess
        self.results = []
        self.phase = "guess"
        self.phase_end = time.time() + GUESS_SECONDS

    def current_for(self, position: int) -> dict:
        return self.drawings[self.queue[position]]

    def _score(self) -> None:
        drawing = self.current
        term, artist = drawing["term"], self.player(drawing["by"])
        results = []
        for p in self.gamers:
            if p.id == drawing["by"]:
                continue
            guess = p.pick if isinstance(p.pick, str) else ""
            ok = bool(guess) and (guess == term if self.mode == 0 else same(guess, term))
            if ok:
                p.gained = GUESS_POINTS
                p.score += GUESS_POINTS
                drawing["hits"] += 1
            results.append({"id": p.id, "guess": guess, "ok": ok})
        if artist and drawing["hits"]:
            artist.gained = DRAW_POINTS * drawing["hits"]
            artist.score += artist.gained
        results.sort(key=lambda r: not r["ok"])
        self.results = results
        self.phase, self.phase_end = "reveal", 0.0
        self.note(f"„{term}“ von {drawing['name']}: {drawing['hits']}× erkannt")

    def is_last(self) -> bool:
        return self.round >= self.rounds and self.shown + 1 >= len(self.queue)

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool):
        if msg.get("t") == "next" and self.state == "playing" and self.player(player_id):
            # Everyone (and the TV) may move on once a drawing has been resolved.
            if self.phase != "reveal":
                return None
            if self.shown + 1 < len(self.queue):
                self.shown += 1
                self._show()
            elif self.round < self.rounds:
                self.next_round()
            else:
                self.finish()
            return None
        return super().act(player_id, msg, is_host)

    def play(self, player, msg: dict) -> None:
        kind = msg.get("t")
        if self.phase == "draw":
            if kind != "submit":
                raise RuleError("Unbekannte Aktion")
            if player.answer is not None:
                raise RuleError("Du hast schon abgegeben")
            player.answer = clean_strokes(msg.get("strokes"))
            if self.done("answer"):
                self.advance()
            return
        if kind != "guess":
            raise RuleError("Unbekannte Aktion")
        if self.current and player.id == self.current["by"]:
            raise RuleError("Das ist deine eigene Zeichnung")
        if self.mode == 1 and player.pick is not None:
            raise RuleError("Du hast schon geraten")
        if self.mode == 0:
            value = msg.get("value")
            if value not in self.options:
                raise RuleError("Bitte eine der Antworten wählen")
        else:
            value = clean(msg.get("value"), 40)
            if not value:
                raise RuleError("Bitte etwas eintippen")
        player.pick = value
        if self.done("pick"):
            self.advance()

    # -- view ----------------------------------------------------------------
    @staticmethod
    def _public(d: dict, with_term: bool) -> dict:
        out = {"by": d["by"], "name": d["name"], "strokes": d["strokes"], "round": d["round"], "hits": d["hits"]}
        if with_term:
            out["term"] = d["term"]
        return out

    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        if self.phase == "draw" and view.get("remaining") is not None:
            view["remaining"] = max(0, round(view["remaining"] - GRACE, 1))
        return view

    def extra_view(self, me) -> dict:
        drawing = self.current
        reveal = self.phase == "reveal"
        view = {
            "mode": self.mode,
            "term": self.terms.get(me.id) if me and self.phase == "draw" and self.state == "playing" else None,
            "drawing": self._public(drawing, reveal) if drawing and self.state == "playing" else None,
            "pos": self.shown + 1, "count": len(self.queue),
            "options": self.options if self.phase == "guess" and self.mode == 0 else [],
            "my_pick": me.pick if me and isinstance(me.pick, str) and self.phase == "guess" else None,
            "results": self.results if reveal else [],
            "blank": self.blank,
            "last": self.is_last(),
        }
        if self.phase == "guess" and drawing and me and me.id == drawing["by"]:
            view["my_term"] = drawing["term"]   # the artist sees their own term
        if self.state == "finished":
            view["gallery"] = [self._public(d, True) for d in self.drawings if d["strokes"]]
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
