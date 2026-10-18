"""Stadt-Land-Fluss: a random letter, everyone fills the categories on the phone.

The round ends when the time is up or somebody with all fields filled calls "Stopp!" (then the others
have a few seconds left). In the review every answer can be challenged; a majority of the other
players marks it invalid. Answers that don't start with the letter are invalid automatically.
Scoring per category: unique valid answer 10, the only valid answer 20, a duplicate 5, nothing 0.
"""

import random
import string
import time
import unicodedata

from common import RuleError
from party import PartyGame, clean

# id → label, in the order they are shown. The first six are the classic default.
CATEGORIES = {
    "stadt": "Stadt", "land": "Land", "fluss": "Fluss", "name": "Name", "beruf": "Beruf", "tier": "Tier",
    "marke": "Marke", "essen": "Essen", "promi": "Promi", "pflanze": "Pflanze", "metall": "Metallbau-Begriff",
}
DEFAULT_CATS = ["stadt", "land", "fluss", "name", "beruf", "tier"]
MIN_CATS = 3
RARE = set("QXY")
STOP_SECONDS = 5
MAX_LEN = 30


def norm(text: str) -> str:
    """Compare answers: case-insensitive, umlauts written out, no spaces or punctuation."""
    t = str(text or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if c.isalnum() and not unicodedata.combining(c))


def score_category(answers: dict, letter: str, rejected: set) -> dict:
    """answers: player id → text. Returns player id → (points, status).

    status: empty | letter (wrong first letter) | voted (challenged) | only | unique | dup
    """
    out, valid = {}, {}
    for pid, text in answers.items():
        n = norm(text)
        if not n:
            out[pid] = (0, "empty")
        elif not n.startswith(letter.lower()):
            out[pid] = (0, "letter")
        elif pid in rejected:
            out[pid] = (0, "voted")
        else:
            valid[pid] = n
    counts: dict[str, int] = {}
    for n in valid.values():
        counts[n] = counts.get(n, 0) + 1
    for pid, n in valid.items():
        if len(valid) == 1:
            out[pid] = (20, "only")
        elif counts[n] == 1:
            out[pid] = (10, "unique")
        else:
            out[pid] = (5, "dup")
    return out


class Game(PartyGame):
    KIND = "stadtlandfluss"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (5, 3, 8, 10)
    TIMES = (120, 90, 180, 0)
    INPUT_PHASES = ("write",)

    def __init__(self, code: str):
        super().__init__(code)
        self.cats = list(DEFAULT_CATS)
        self.all_letters = 0          # 1 = Q, X and Y are allowed too
        self.letter = ""
        self.stopper: str | None = None
        self.votes: dict[str, set] = {}     # "pid|cat" → ids of players who called the answer invalid
        self.results: dict[str, dict] = {}  # cat → player id → (points, status)
        self.answers: dict[str, dict] = {}  # cat → player id → text (frozen when the round ends)

    def new_player(self, name: str, is_bot: bool = False):
        player = super().new_player(name, is_bot)
        player.fields, player.base = {}, 0
        return player

    # -- settings ------------------------------------------------------------
    def configure_more(self, settings: dict) -> None:
        letters = settings.get("letters")
        if letters is not None:
            self.all_letters = 1 if int(letters) == 1 else 0
        cats = settings.get("cats")
        if isinstance(cats, list):   # missing → keep the current choice (the selects don't send it)
            chosen = [c for c in CATEGORIES if c in {str(x) for x in cats}]
            if len(chosen) < MIN_CATS:
                raise RuleError(f"Bitte mindestens {MIN_CATS} Kategorien wählen")
            self.cats = chosen

    def settings_view(self) -> dict:
        return {**super().settings_view(), "letters": self.all_letters, "cats": self.cats}

    def start(self) -> None:
        for p in self.players:
            p.base = 0
        super().start()

    # -- rounds --------------------------------------------------------------
    def setup_round(self) -> None:
        letters = [c for c in string.ascii_uppercase if self.all_letters or c not in RARE]
        pool = [c for c in letters if c not in self.used] or letters
        self.letter = random.choice(pool)
        self.used.add(self.letter)
        self.stopper = None
        self.votes = {}
        self.results = {}
        self.answers = {}
        for p in self.players:
            p.fields = {}
            p.base = p.score
        self.begin("write")

    def complete(self, player) -> bool:
        return all(clean(player.fields.get(c), MAX_LEN) for c in self.cats)

    def play(self, player, msg: dict) -> None:
        kind = msg.get("t")
        if kind not in ("fields", "stop"):
            raise RuleError("Unbekannte Aktion")
        fields = msg.get("fields")
        if isinstance(fields, dict):
            player.fields = {c: clean(fields.get(c), MAX_LEN) for c in self.cats if fields.get(c)}
        player.answer = "voll" if self.complete(player) else None
        if kind == "stop":
            if not self.complete(player):
                raise RuleError("Erst alle Felder ausfüllen, dann Stopp rufen")
            if self.stopper:
                return
            self.stopper = player.id
            end = time.time() + STOP_SECONDS
            self.phase_end = min(self.phase_end, end) if self.phase_end else end
            self.note(f"✋ {player.name} ruft Stopp!")

    def advance(self) -> None:
        self.answers = {c: {p.id: p.fields.get(c, "") for p in self.gamers} for c in self.cats}
        self.rescore()
        self.begin("reveal", timed=False)

    def threshold(self, author_id: str) -> int:
        """Challenges needed: a majority of the other people at the table (players who left don't vote)."""
        voters = [p for p in self.gamers if not p.is_bot and p.id != author_id]
        return len(voters) // 2 + 1 if voters else 1

    def rejected(self, cat: str) -> set:
        return {pid for pid in self.answers.get(cat, {})
                if len(self.votes.get(f"{pid}|{cat}", ())) >= self.threshold(pid)}

    def rescore(self) -> None:
        self.results = {c: score_category(self.answers[c], self.letter, self.rejected(c)) for c in self.cats}
        for p in self.gamers:
            p.gained = sum(self.results[c].get(p.id, (0, ""))[0] for c in self.cats)
            p.score = getattr(p, "base", 0) + p.gained

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool):
        kind = msg.get("t")
        player = self.player(player_id)
        if kind == "fields" and self.state == "playing" and self.phase != "write":
            return None     # a late draft after the round ended: nothing to do
        if kind == "challenge" and self.state == "playing" and self.phase == "reveal":
            if not player or player.screen:
                raise RuleError("Der Host-Bildschirm zeigt nur an")
            cat, target = str(msg.get("cat", "")), str(msg.get("id", ""))
            if cat not in self.answers or target not in self.answers[cat]:
                raise RuleError("Diese Antwort gibt es nicht")
            if target == player.id:
                raise RuleError("Deine eigene Antwort kannst du nicht anfechten")
            if not norm(self.answers[cat][target]):
                raise RuleError("Da steht nichts")
            voters = self.votes.setdefault(f"{target}|{cat}", set())
            voters.symmetric_difference_update({player.id})
            self.rescore()
            return None
        return super().act(player_id, msg, is_host)

    def pending_bots(self) -> list:
        # Players who left keep what they had typed; the round ends by time or "Stopp!".
        return []

    # -- view ----------------------------------------------------------------
    def extra_view(self, me) -> dict:
        view = {
            "letter": self.letter,
            "cats": [{"id": c, "label": CATEGORIES[c]} for c in self.cats],
            "stopper": self.stopper,
        }
        if self.phase == "write":
            view["my_fields"] = dict(me.fields) if me and not me.screen else {}
        elif self.phase == "reveal" and self.answers:
            review = []
            for c in self.cats:
                rows = []
                for p in self.gamers:
                    text = self.answers[c].get(p.id, "")
                    points, status = self.results[c].get(p.id, (0, "empty"))
                    voters = self.votes.get(f"{p.id}|{c}", set())
                    rows.append({"id": p.id, "text": text, "points": points, "status": status,
                                 "votes": len(voters), "need": self.threshold(p.id),
                                 "mine": bool(me and me.id in voters)})
                review.append({"id": c, "label": CATEGORIES[c], "rows": rows})
            view["review"] = review
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
