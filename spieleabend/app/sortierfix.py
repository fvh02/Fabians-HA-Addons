"""Sortierfix: everyone gets the same five items and puts them in the right order (by year, height, …).

Points for every item in the right place, plus a bonus when all of them are right. While sorting, the
phone sends its current order as a draft, so an order counts even if time runs out before "Fertig".
"""

import random

from common import RuleError
from party import PartyGame, Player
from sortierfix_daten import CATEGORIES

ITEMS = 5
PER_ITEM, BONUS = 1, 3


def label(item, unit: str) -> str:
    if len(item) > 2:
        return item[2]
    value = item[1]
    text = f"{value:,.4f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
    if isinstance(value, int) and 1000 <= value <= 2100 and not unit:
        text = str(value)               # a year
    text = text.replace(",", "§").replace(".", ",").replace("§", ".")
    if not unit:
        return text
    return f"{text}{unit}" if unit.startswith("° ") else f"{text} {unit}"


class Game(PartyGame):
    KIND = "sortierfix"
    MIN_PLAYERS, MAX_PLAYERS = 2, 16
    ROUNDS = (8, 5, 10, 12)
    TIMES = (60, 45, 90, 0)
    INPUT_PHASES = ("sort",)

    def __init__(self, code: str):
        super().__init__(code)
        self.category = 0
        self.set = None
        self.items: list[tuple] = []      # the five items in the order everyone starts with
        self.solution: list[int] = []     # indices into items, in the right order
        self.results: list[dict] = []

    def new_player(self, name: str, is_bot: bool = False) -> Player:
        player = super().new_player(name, is_bot)
        player.draft = None
        return player

    def configure_more(self, settings: dict) -> None:
        category = settings.get("category")
        self.category = int(category) if category is not None and int(category) in CATEGORIES else 0

    def settings_view(self) -> dict:
        return {**super().settings_view(), "category": self.category}

    # -- rounds --------------------------------------------------------------
    def setup_round(self) -> None:
        sets = CATEGORIES[self.category][1]
        pool = [s for s in sets if s[0] + s[1] + str(s[5][0]) not in self.used] or sets
        self.set = random.choice(pool)
        self.used.add(self.set[0] + self.set[1] + str(self.set[5][0]))
        self.items = random.sample(self.set[5], ITEMS)
        desc = self.set[3]
        self.solution = sorted(range(ITEMS), key=lambda i: self.items[i][1], reverse=desc)
        while self.solution == list(range(ITEMS)):     # never start in the right order
            random.shuffle(self.items)
            self.solution = sorted(range(ITEMS), key=lambda i: self.items[i][1], reverse=desc)
        for p in self.players:
            p.draft = None
        self.results = []
        self.begin("sort")

    @staticmethod
    def parse_order(raw) -> list[int]:
        if not isinstance(raw, list) or sorted(raw) != list(range(ITEMS)) or not all(isinstance(i, int) for i in raw):
            raise RuleError("Ungültige Reihenfolge")
        return list(raw)

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool):
        if msg.get("t") == "draft":
            # The current order while sorting: remembered quietly, no update for everyone.
            player = self.player(player_id)
            if player and not player.screen and self.state == "playing" and self.phase == "sort" and player.answer is None:
                player.draft = self.parse_order(msg.get("order"))
            return {"t": "sf_draft"}
        return super().act(player_id, msg, is_host)

    def play(self, player, msg: dict) -> None:
        kind = msg.get("t")
        if kind == "order":
            player.answer = player.draft = self.parse_order(msg.get("order"))
            if self.done("answer"):
                self.advance()
            return
        if kind == "edit":
            player.answer = None
            return
        raise RuleError("Unbekannte Aktion")

    def advance(self) -> None:
        results = []
        for p in self.gamers:
            order = p.answer if isinstance(p.answer, list) else p.draft if isinstance(p.draft, list) else None
            if order is None:
                results.append({"id": p.id, "order": None, "hits": [], "points": 0, "late": False})
                continue
            hits = [order[i] == self.solution[i] for i in range(ITEMS)]
            p.gained = PER_ITEM * sum(hits) + (BONUS if all(hits) else 0)
            p.score += p.gained
            results.append({"id": p.id, "order": order, "hits": hits, "points": p.gained,
                            "late": not isinstance(p.answer, list)})
        results.sort(key=lambda r: -r["points"])
        self.results = results
        self.begin("reveal", timed=False)
        perfect = [self.player(r["id"]).name for r in results if r["hits"] and all(r["hits"])]
        if perfect:
            self.note(f"Alles richtig: {', '.join(perfect)}")

    # -- view ----------------------------------------------------------------
    def extra_view(self, me) -> dict:
        question, top, bottom, _desc, unit, _items = self.set or ("", "", "", False, "", [])
        reveal = self.phase == "reveal"
        return {
            "question": question, "top": top, "bottom": bottom, "category": CATEGORIES[self.category][0],
            "items": [{"name": it[0], "value": label(it, unit) if reveal else None} for it in self.items],
            "solution": self.solution if reveal else None,
            "results": self.results if reveal else [],
            "my_order": me.answer if me and isinstance(me.answer, list) else None,
            "my_draft": me.draft if me and isinstance(getattr(me, "draft", None), list) else None,
            "points": {"item": PER_ITEM, "bonus": BONUS},
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
