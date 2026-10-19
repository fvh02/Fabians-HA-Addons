"""Schwimmen (31): collect a high hand of one suit by swapping with the three open cards in the middle.

32-card deck (7 to Ace; Ace 11, pictures 10, numbers face value). A hand is worth the highest sum of
one suit; three of a kind count 30.5, three aces ("Feuer") 33 and end the round at once.
On a turn you swap one card, swap all three, pass ("schieben") or knock (everyone else gets one more
turn). If everyone passes, the middle is replaced once; if everyone passes again the round ends.
The lowest hand loses a life; with no lives left you "swim", the next loss puts you out.
The last player in the game wins. One device can be the TV screen: it shows the table, never hands.
"""

import random
import secrets
import time

from common import RuleError

MIN_PLAYERS, MAX_PLAYERS = 2, 8     # 8 × 3 + 3 + 3 (replaced middle) = 30 of 32 cards
SUITS = ["♣", "♠", "♥", "♦"]
RANKS = ["7", "8", "9", "10", "B", "D", "K", "A"]
VALUES = {"7": 7, "8": 8, "9": 9, "10": 10, "B": 10, "D": 10, "K": 10, "A": 11}
LIVES = (3, 2, 4)
TURN_TIMES = (60, 30, 90, 0)        # seconds per turn for people, 0 = no limit; then the turn is passed
ROUND_END_SECONDS = 40              # the next round starts by itself if nobody presses "Weiter"
FEUER, PASCH = 33.0, 30.5


def new_deck() -> list[tuple[str, str]]:
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def hand_value(cards) -> float:
    """Highest sum of one suit; three of a kind 30.5, three aces ("Feuer") 33."""
    if len(cards) == 3 and len({r for r, _ in cards}) == 1:
        return FEUER if cards[0][0] == "A" else PASCH
    sums: dict[str, int] = {}
    for r, s in cards:
        sums[s] = sums.get(s, 0) + VALUES[r]
    return float(max(sums.values(), default=0))


def is_feuer(cards) -> bool:
    return hand_value(cards) == FEUER


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.screen = False
        self.hand: list[tuple[str, str]] = []
        self.lives = 3
        self.out = False
        self.out_round = 0     # round in which the player went under (for the final ranking)

    @property
    def swimming(self) -> bool:
        return self.lives == 0 and not self.out


class Game:
    KIND = "schwimmen"
    NO_BOTS = False

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"        # lobby | playing | finished
        self.phase = "turn"         # turn | round_end
        self.start_lives = 3
        self.turn_seconds = 60
        self.deck: list[tuple[str, str]] = []
        self.middle: list[tuple[str, str]] = []
        self.round = 0
        self.dealer: str | None = None
        self.turn = 0                # index into self.players
        self.knocker: str | None = None
        self.final_left: set[str] = set()
        self.passes = 0              # passes in a row
        self.replaced = False        # the middle was already replaced this round
        self.moves = 0               # turns played this round (bots knock earlier in long rounds)
        self.turn_end = 0.0
        self.round_end_at = 0.0
        self.result: dict = {}
        self.winner: str | None = None
        self.last: dict = {"seq": 0, "kind": ""}
        self.log: list[str] = []

    # -- shared interface ----------------------------------------------------
    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    def note(self, text: str) -> None:
        self.log.append(text)
        del self.log[:-30]

    @property
    def screen(self):
        return next((p for p in self.players if p.screen), None)

    @property
    def gamers(self) -> list[Player]:
        return [p for p in self.players if not p.screen]

    @property
    def active(self) -> list[Player]:
        return [p for p in self.players if not p.screen and not p.out]

    @property
    def current(self):
        if self.state == "playing" and self.phase == "turn" and self.players:
            return self.players[self.turn]
        return None

    def configure(self, settings: dict) -> None:
        lives = settings.get("lives")
        self.start_lives = int(lives) if lives is not None and int(lives) in LIVES else LIVES[0]
        seconds = settings.get("seconds")
        self.turn_seconds = int(seconds) if seconds is not None and int(seconds) in TURN_TIMES else TURN_TIMES[0]

    def add_player(self, player: Player) -> None:
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.gamers) >= MAX_PLAYERS and not player.screen:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None and not player.is_bot:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        player = self.player(player_id)
        if not player:
            return
        current = self.current
        self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot and not p.screen),
                                next((p.id for p in self.players if not p.is_bot), None))
        if self.state != "playing":
            return
        self.note(f"{player.name} hat das Spiel verlassen")
        self.final_left.discard(player_id)
        if len(self.active) < 2:
            self.finish()
            return
        if self.phase == "turn":
            if current is player:
                self.turn = self.turn % len(self.players)
                if self.players[self.turn].screen or self.players[self.turn].out:
                    self.turn = self.next_index(self.turn)
                self.passes = 0
                self.begin_turn()
            elif current:
                self.turn = self.players.index(current)
            if self.knocker and not self.final_left:
                self.end_round("knock")

    def start(self) -> None:
        if len(self.gamers) < MIN_PLAYERS:
            raise RuleError(f"Mindestens {MIN_PLAYERS} Spieler nötig (der Fernseher zählt nicht)")
        if len(self.gamers) > MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        for p in self.players:
            p.lives, p.out, p.out_round, p.hand = self.start_lives, False, 0, []
        self.round = 0
        self.winner = None
        self.log = []
        self.dealer = None
        self.state = "playing"
        self.note(f"Neues Spiel – jeder hat {self.start_lives} Leben")
        self.start_round()

    # -- turn order ------------------------------------------------------------
    def next_index(self, index: int) -> int:
        n = len(self.players)
        for step in range(1, n + 1):
            p = self.players[(index + step) % n]
            if not p.screen and not p.out:
                return (index + step) % n
        return index

    def begin_turn(self) -> None:
        current = self.current
        human = current and not current.is_bot
        self.turn_end = time.time() + self.turn_seconds if human and self.turn_seconds else 0.0

    @property
    def deadline(self) -> float | None:
        if self.state != "playing":
            return None
        if self.phase == "turn":
            current = self.current
            return self.turn_end if self.turn_end and current and not current.is_bot else None
        return self.round_end_at or None

    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        if self.phase == "round_end":
            self.start_round()
            return
        current = self.current
        if current and not current.is_bot:
            self.note(f"⏱ Zeit um – {current.name} schiebt")
            self.do_pass(current)

    def event(self, kind: str, **data) -> None:
        self.last = {"seq": self.last["seq"] + 1, "kind": kind, **data}

    # -- rounds --------------------------------------------------------------
    def start_round(self) -> None:
        self.round += 1
        self.deck = new_deck()
        for p in self.players:
            p.hand = [self.deck.pop() for _ in range(3)] if not p.screen and not p.out else []
        self.middle = [self.deck.pop() for _ in range(3)]
        dealer = self.player(self.dealer)
        index = self.players.index(dealer) if dealer else random.randrange(len(self.players))
        index = self.next_index(index) if dealer or self.players[index].screen or self.players[index].out else index
        self.dealer = self.players[index].id
        self.turn = self.next_index(index)
        self.knocker = None
        self.final_left = set()
        self.passes = 0
        self.replaced = False
        self.moves = 0
        self.result = {}
        self.round_end_at = 0.0
        self.phase = "turn"
        self.event("deal")
        self.note(f"Runde {self.round}: {self.players[index].name} gibt")
        fire = next((p for p in self.active if is_feuer(p.hand)), None)
        if fire:
            self.note(f"🔥 Feuer! {fire.name} hat drei Asse")
            self.end_round("feuer", fire)
            return
        self.begin_turn()

    def end_turn(self, player: Player) -> None:
        self.moves += 1
        if is_feuer(player.hand):
            self.note(f"🔥 Feuer! {player.name} hat drei Asse")
            self.end_round("feuer", player)
            return
        if self.knocker and player.id != self.knocker:
            self.final_left.discard(player.id)
            if not self.final_left:
                self.end_round("knock")
                return
        self.turn = self.next_index(self.turn)
        self.begin_turn()

    def do_pass(self, player: Player) -> None:
        self.passes += 1
        self.event("pass", by=player.id)
        if not self.knocker and self.passes >= len(self.active):
            self.passes = 0
            if not self.replaced and len(self.deck) >= 3:
                self.replaced = True
                self.middle = [self.deck.pop() for _ in range(3)]
                self.event("replace", by=player.id)
                self.note("Alle haben geschoben – die Mitte wird ausgetauscht")
            else:
                self.note("Wieder haben alle geschoben – die Runde endet")
                self.end_round("passed")
                return
        self.end_turn(player)

    def end_round(self, reason: str, by: Player | None = None) -> None:
        active = self.active
        values = {p.id: hand_value(p.hand) for p in active}
        low = min(values.values())
        losers = [p for p in active if values[p.id] == low]
        result = {"reason": reason, "by": by.id if by else self.knocker, "values": values,
                  "hands": {p.id: [{"r": r, "s": s} for r, s in p.hand] for p in active},
                  "losers": [], "swim": [], "out": [], "spared": False}
        if len(losers) == len(active) and all(p.swimming for p in losers):
            # Everybody left would go under at once: this round doesn't count.
            result["spared"] = True
            self.note("Gleichstand – alle schwimmen, die Runde zählt nicht")
        else:
            for p in losers:
                result["losers"].append(p.id)
                if p.lives == 0:
                    p.out, p.out_round = True, self.round
                    result["out"].append(p.id)
                    self.note(f"💧 {p.name} geht unter und ist raus")
                else:
                    p.lives -= 1
                    if p.lives == 0:
                        result["swim"].append(p.id)
                        self.note(f"🏊 {p.name} schwimmt!")
                    else:
                        self.note(f"{p.name} verliert ein Leben ({self.fmt(low)})")
        self.result = result
        self.phase = "round_end"
        self.turn_end = 0.0
        self.event("end", reason=reason)
        if len(self.active) <= 1:
            self.finish()
        else:
            self.round_end_at = time.time() + ROUND_END_SECONDS

    @staticmethod
    def fmt(value: float) -> str:
        return str(value).replace(".0", "").replace(".", ",")

    def finish(self) -> None:
        self.state = "finished"
        self.turn_end = self.round_end_at = 0.0
        left = self.active
        best = left[0] if len(left) == 1 else max(left, key=lambda p: (p.lives, hand_value(p.hand)), default=None)
        self.winner = best.name if best else None
        if best:
            self.note(f"🏆 {best.name} gewinnt!")

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if not player:
            raise RuleError("Gerade nicht möglich")
        if kind == "screen":
            if self.state != "lobby":
                raise RuleError("Der Fernseher wird vor dem Start gewählt")
            current = self.screen
            if current and current is not player:
                raise RuleError(f"{current.name} ist schon der Fernseher")
            player.screen = not player.screen
            return
        if self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        if kind == "next_round":
            # Everyone (and the TV) may continue; a second press after someone else was quicker does nothing.
            if self.phase == "round_end":
                self.start_round()
            return
        if player.screen:
            raise RuleError("Der Fernseher zeigt nur an")
        if self.phase != "turn" or self.current is not player:
            raise RuleError("Du bist nicht am Zug")
        if kind == "swap":
            try:
                i, j = int(msg.get("hand")), int(msg.get("middle"))
            except (TypeError, ValueError):
                raise RuleError("Ungültige Karte")
            if not (0 <= i < 3 and 0 <= j < 3):
                raise RuleError("Ungültige Karte")
            player.hand[i], self.middle[j] = self.middle[j], player.hand[i]
            self.passes = 0
            self.event("swap", by=player.id, hand=i, middle=j)
            self.end_turn(player)
        elif kind == "swap_all":
            player.hand, self.middle = self.middle, player.hand
            self.passes = 0
            self.event("swap_all", by=player.id)
            self.end_turn(player)
        elif kind == "pass":
            self.do_pass(player)
        elif kind == "knock":
            if self.knocker:
                raise RuleError("Es wurde schon geklopft")
            self.knocker = player.id
            self.final_left = {p.id for p in self.active if p.id != player.id}
            self.passes = 0
            self.event("knock", by=player.id)
            self.note(f"✊ {player.name} klopft – jeder hat noch einen Zug")
            self.moves += 1
            self.turn = self.next_index(self.turn)
            self.begin_turn()
        else:
            raise RuleError("Unbekannte Aktion")

    # -- bots ----------------------------------------------------------------
    def pending_bots(self) -> list:
        current = self.current
        return [current] if current and current.is_bot else []

    def bot_step(self, bot: Player) -> None:
        self.act(bot.id, self.bot_move(bot), False)

    def bot_move(self, bot: Player) -> dict:
        now = hand_value(bot.hand)
        options = [(hand_value(self.middle), {"t": "swap_all"})]
        for i in range(3):
            for j in range(3):
                hand = list(bot.hand)
                hand[i] = self.middle[j]
                options.append((hand_value(hand) + self.potential(hand) * .01, {"t": "swap", "hand": i, "middle": j}))
        best_value, best = max(options, key=lambda o: o[0])
        # Knock with a good hand – and the longer the round runs, the sooner (so no round goes on forever).
        rounds = self.moves / len(self.active)
        threshold = 29 if rounds < 2 else 26 if rounds < 4 else 23 if rounds < 6 else 0
        if not self.knocker and now >= threshold and best_value < now + 2:
            return {"t": "knock"}
        if best_value > now + .005:
            return best
        return {"t": "pass"}

    @staticmethod
    def potential(hand) -> int:
        """Tie-breaker for bots: prefer hands whose cards share a suit (better for later swaps)."""
        suits = [s for _, s in hand]
        return max(suits.count(s) for s in suits)

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        me = self.player(viewer_id)
        current = self.current
        result = dict(self.result)
        if result and (not me or me.screen):
            result.pop("hands", None)   # the TV never shows cards of a hand
        playing_me = me and not me.screen and not me.out and self.state != "lobby"
        deadline = self.deadline
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "round": self.round,
            "settings": {"lives": self.start_lives, "seconds": self.turn_seconds},
            "screen": self.screen.id if self.screen else None,
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "screen": p.screen, "lives": p.lives,
                         "swimming": p.swimming, "out": p.out, "out_round": p.out_round, "dealer": p.id == self.dealer} for p in self.players],
            "turn": current.id if current else None,
            "middle": [{"r": r, "s": s} for r, s in self.middle],
            "hand": [{"r": r, "s": s} for r, s in me.hand] if playing_me else [],
            "value": hand_value(me.hand) if playing_me and me.hand else None,
            "knocker": self.knocker, "final_left": sorted(self.final_left),
            "passes": self.passes, "replaced": self.replaced, "active": len(self.active),
            "result": result, "last": self.last, "winner": self.winner,
            "remaining": max(0, round(deadline - time.time(), 1)) if deadline else None,
            "log": self.log[-6:],
        }
