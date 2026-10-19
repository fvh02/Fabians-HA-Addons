"""Buzzer-Quiz: the host screen shows a question, everyone has a buzzer on the phone.

Whoever buzzes first (arrival order at the server) answers: only that player sees the four options.
Right = points, wrong = minus points and locked out for this question; the next buzzer may try.
Buzzes that arrive while someone is answering queue up in arrival order.
"""

import random
import time

from buzzer_daten import CATEGORIES
from common import RuleError
from party import PartyGame

RIGHT, WRONG = 3, -2          # points for a right / wrong answer
ANSWER_SECONDS = 12           # time the buzzing player has to pick an option
MIN_RESUME = 5                # seconds of buzz time left at least after a wrong answer


class Game(PartyGame):
    KIND = "buzzer"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (10, 5, 15, 20)
    TIMES = (20, 15, 30, 0)       # buzz time per question
    INPUT_PHASES = ("buzz", "answer")

    def __init__(self, code: str):
        super().__init__(code)
        self.category = 0
        self.question = None
        self.options: list[str] = []
        self.right = 0
        self.buzzer: str | None = None       # who is answering right now
        self.queue: list[str] = []          # who buzzed while someone was answering
        self.locked: set[str] = set()       # answered wrong (or left) – no more buzzing this question
        self.attempts: list[dict] = []      # {id, pick, ok, ms}
        self.buzz_left = 0.0
        self.asked_at = 0.0
        self.buzz_times: dict[str, int] = {}  # ms after the question appeared

    def configure_more(self, settings: dict) -> None:
        category = settings.get("category")
        self.category = int(category) if category is not None and int(category) in CATEGORIES else 0

    def settings_view(self) -> dict:
        return {**super().settings_view(), "category": self.category}

    # -- rounds --------------------------------------------------------------
    def setup_round(self) -> None:
        questions = CATEGORIES[self.category][1]
        pool = [q for q in questions if q[0] not in self.used] or questions
        self.question = random.choice(pool)
        self.used.add(self.question[0])
        self.options = list(self.question[1:5])
        random.shuffle(self.options)
        self.right = self.options.index(self.question[1])
        self.buzzer, self.queue, self.locked, self.attempts = None, [], set(), []
        self.buzz_times = {}
        self.asked_at = time.time()
        self.begin("buzz")

    def eligible(self, player) -> bool:
        return not player.screen and not player.is_bot and player.id not in self.locked

    def wrong_picks(self) -> set[int]:
        return {a["pick"] for a in self.attempts if a["pick"] is not None and not a["ok"]}

    def open_answer(self, player) -> None:
        if self.phase == "buzz":
            self.buzz_left = max(0.0, self.phase_end - time.time()) if self.phase_end else 0.0
        self.buzzer = player.id
        self.phase = "answer"
        self.phase_end = time.time() + ANSWER_SECONDS

    def next_turn(self) -> None:
        """After a wrong answer: the next in the queue answers, else everyone may buzz again."""
        self.buzzer = None
        if len(self.wrong_picks()) >= len(self.options) - 1:
            self.reveal()
            return
        while self.queue:
            nxt = self.player(self.queue.pop(0))
            if nxt and self.eligible(nxt):
                self.open_answer(nxt)
                return
        if not any(self.eligible(p) for p in self.gamers):
            self.reveal()
            return
        self.phase = "buzz"
        self.phase_end = time.time() + max(self.buzz_left, MIN_RESUME) if self.seconds else 0.0

    def reveal(self) -> None:
        self.buzzer = None
        self.queue = []
        self.begin("reveal", timed=False)
        winner = next((a for a in self.attempts if a["ok"]), None)
        if winner:
            self.note(f"{self.player(winner['id']).name} wusste es: {self.options[self.right]}")
        else:
            self.note(f"Niemand wusste es: {self.options[self.right]}")

    def advance(self) -> None:
        """Host skip in the buzz phase: nobody wants to buzz – show the answer."""
        if self.phase == "buzz":
            self.reveal()

    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        if self.phase == "buzz":
            self.reveal()
        elif self.phase == "answer":
            self.judge(self.player(self.buzzer), None)

    def judge(self, player, pick) -> None:
        """The buzzing player picked an option (None = time is up / left the game)."""
        if player is None:
            self.next_turn()
            return
        ok = pick == self.right
        left = pick is None and player.is_bot
        points = RIGHT if ok else (0 if left else WRONG)
        player.score += points
        player.gained += points
        self.attempts.append({"id": player.id, "pick": pick, "ok": ok, "points": points,
                              "ms": self.buzz_times.get(player.id)})
        if ok:
            self.reveal()
            return
        self.locked.add(player.id)
        self.next_turn()

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool):
        if msg.get("t") == "skip" and self.phase == "answer":
            return None      # the one answering has their own clock
        return super().act(player_id, msg, is_host)

    def play(self, player, msg: dict) -> None:
        kind = msg.get("t")
        if kind == "buzz":
            if player.id in self.locked:
                raise RuleError("Du bist für diese Frage gesperrt")
            if player.id == self.buzzer or player.id in self.queue:
                return
            self.buzz_times[player.id] = int((time.time() - self.asked_at) * 1000)
            if self.phase == "buzz":
                self.open_answer(player)
            else:
                self.queue.append(player.id)
            return
        if kind == "answer":
            if self.phase != "answer" or player.id != self.buzzer:
                raise RuleError("Du bist gerade nicht dran")
            try:
                pick = int(msg.get("pick"))
            except (TypeError, ValueError):
                raise RuleError("Ungültige Antwort") from None
            if not 0 <= pick < len(self.options) or pick in self.wrong_picks():
                raise RuleError("Ungültige Antwort")
            self.judge(player, pick)
            return
        raise RuleError("Unbekannte Aktion")

    # -- players who left ----------------------------------------------------
    def pending_bots(self) -> list:
        if self.state != "playing":
            return []
        if self.phase == "answer":
            current = self.player(self.buzzer)
            return [current] if current is None or current.is_bot else []
        if self.phase == "buzz" and not any(self.eligible(p) for p in self.gamers):
            return self.gamers[:1]        # only computer seats left: one of them closes the question
        return []

    def bot_step(self, bot) -> None:
        if self.phase == "answer":
            self.judge(self.player(self.buzzer), None)
        elif self.phase == "buzz":
            self.reveal()

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        # The shared ranking shows "+gained" – keep that for gains; the page shows losses itself ("delta").
        for entry in view["players"]:
            entry["delta"] = entry["gained"]
            entry["gained"] = max(0, entry["gained"])
        return view

    def extra_view(self, me) -> dict:
        q = self.question or ("", "", "", "", "", "")
        reveal = self.phase == "reveal"
        mine = bool(me and me.id == self.buzzer and self.phase == "answer")
        return {
            "question": q[0], "category": CATEGORIES[self.category][0],
            "options": self.options if (mine or reveal) else None,
            "right": self.right if reveal else None,
            "note": q[5] if reveal else "",
            "buzzer": self.buzzer, "queue": list(self.queue), "locked": sorted(self.locked),
            "wrong": sorted(self.wrong_picks()),
            # The options of wrong answers are public (the next player may not pick them again).
            "attempts": [{**a, "text": self.options[a["pick"]] if a["pick"] is not None else None} for a in self.attempts],
            "points": {"right": RIGHT, "wrong": WRONG},
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
