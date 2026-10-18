"""Codewörter: two teams, 25 words, one secret key. (rules, no networking)

Each team has a Hinweisgeber who sees which words belong to which team. They give one word and a number,
their team taps the matching cards on their phones. 9 cards for the starting team, 8 for the other,
7 neutral ones and one Attentäter – whoever reveals it loses at once. A TV screen shows the board and the
hint, never the key. Players who leave become computer players: a Hinweisgeber's role goes to a teammate,
and a team without people left plays on by itself, so a game never gets stuck.
"""

import random
import secrets
import time

from codewoerter_daten import WORDS
from common import RuleError

MIN_PLAYERS, MAX_PLAYERS = 4, 16
TIMES = (0, 60, 90, 120, 180)       # seconds per hint and per guessing turn, 0 = no limit
TEAMS = ("rot", "blau")
NAMES = {"rot": "Rot", "blau": "Blau"}
ASSASSIN, NEUTRAL = "attentaeter", "neutral"
UNLIMITED = -1                      # hint number "∞"
SIZE = 25


def other(team: str) -> str:
    return "blau" if team == "rot" else "rot"


def norm(word: str) -> str:
    return word.lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")


class Player:
    def __init__(self, name: str, is_bot: bool = False):
        self.id = secrets.token_hex(4)
        self.name = name
        self.is_bot = is_bot
        self.screen = False          # the TV: only shows the board
        self.team: str | None = None
        self.spy = False             # Hinweisgeber of their team
        self.sel: int | None = None  # card this player has tapped (visible to the team)


class Game:
    KIND = "codewoerter"
    NO_BOTS = True

    def __init__(self, code: str):
        self.code = code
        self.players: list[Player] = []
        self.host_id: str | None = None
        self.state = "lobby"      # lobby | playing | finished
        self.phase = "hint"       # hint | guess
        self.seconds = 0
        self.words: list[str] = []
        self.colors: list[str] = []
        self.revealed: list[bool] = []
        self.starter = "rot"
        self.turn = "rot"
        self.hint: dict | None = None      # {"word", "number"}
        self.guesses_left: int | None = None  # None = unlimited
        self.hints: list[dict] = []        # all hints of this game: team, word, number, found
        self.last: dict | None = None      # last revealed card (for the animation)
        self.winner: str | None = None
        self.reason = ""                   # cards | assassin
        self.phase_end = 0.0
        self.used: set[str] = set()
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
    def gamers(self) -> list[Player]:
        return [p for p in self.players if not p.screen]

    @property
    def screen(self):
        return next((p for p in self.players if p.screen), None)

    def members(self, team: str) -> list[Player]:
        return [p for p in self.players if p.team == team and not p.screen]

    def spy_of(self, team: str):
        return next((p for p in self.members(team) if p.spy), None)

    def guessers(self, team: str) -> list[Player]:
        return [p for p in self.members(team) if not p.spy]

    def configure(self, settings: dict) -> None:
        seconds = settings.get("seconds")
        seconds = int(seconds) if seconds is not None else 0
        self.seconds = seconds if seconds in TIMES else 0

    def add_player(self, player: Player) -> None:
        if player.is_bot:
            raise RuleError("In diesem Spiel gibt es keine Computer-Spieler")
        if self.state != "lobby":
            raise RuleError("Das Spiel läuft bereits")
        if len(self.players) >= MAX_PLAYERS + 1:  # + the TV screen
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        self.players.append(player)
        if self.host_id is None:
            self.host_id = player.id

    def remove_player(self, player_id: str) -> None:
        player = self.player(player_id)
        if player:
            self.players.remove(player)
        if self.host_id == player_id:
            self.host_id = next((p.id for p in self.players if not p.is_bot and not p.screen),
                                next((p.id for p in self.players if not p.is_bot), None))

    def place_of(self, player) -> int | None:
        """For the Bestenliste: 1 = winning team, 2 = the others."""
        if not self.winner:
            return None
        return 1 if player.team == self.winner else 2

    # -- start -------------------------------------------------------------------
    def start(self) -> None:
        gamers = self.gamers
        if len(gamers) < MIN_PLAYERS:
            raise RuleError(f"Mindestens {MIN_PLAYERS} Spieler nötig (der Bildschirm zählt nicht)")
        if len(gamers) > MAX_PLAYERS:
            raise RuleError(f"Maximal {MAX_PLAYERS} Spieler")
        rematch = self.state == "finished"
        # Whoever hasn't picked a team goes to the smaller one.
        free = [p for p in gamers if p.team not in TEAMS]
        random.shuffle(free)
        for p in free:
            p.team = min(TEAMS, key=lambda t: (len(self.members(t)), random.random()))
            p.spy = False
        for t in TEAMS:
            if len(self.members(t)) < 2:
                raise RuleError("Jedes Team braucht mindestens 2 Spieler – wechselt das Team oder mischt neu")
        for t in TEAMS:
            self._pick_spy(t, rotate=rematch)
        self.state = "playing"
        self.log = []
        self.hints = []
        self.winner = None
        self.reason = ""
        self.last = None
        self._deal()
        self.note(f"Team {NAMES[self.starter]} beginnt mit 9 Karten, Team {NAMES[other(self.starter)]} hat 8")
        self._begin_turn(self.starter)

    def _pick_spy(self, team: str, rotate: bool) -> None:
        members = self.members(team)
        current = self.spy_of(team)
        people = [p for p in members if not p.is_bot] or members
        if current in people and (not rotate or len(people) == 1):
            chosen = current
        elif current in people:
            chosen = people[(people.index(current) + 1) % len(people)]   # the next one gives the hints
        else:
            chosen = random.choice(people)
        for p in members:
            p.spy = p is chosen

    def _deal(self) -> None:
        pool = [w for w in WORDS if w not in self.used]
        if len(pool) < SIZE:
            self.used = set()
            pool = list(WORDS)
        self.words = random.sample(pool, SIZE)
        self.used.update(self.words)
        self.starter = random.choice(TEAMS)
        colors = [self.starter] * 9 + [other(self.starter)] * 8 + [NEUTRAL] * 7 + [ASSASSIN]
        random.shuffle(colors)
        self.colors = colors
        self.revealed = [False] * SIZE

    # -- turns -------------------------------------------------------------------
    def _begin_turn(self, team: str) -> None:
        self.turn = team
        self.phase = "hint"
        self.hint = None
        self.guesses_left = None
        for p in self.players:
            p.sel = None
        self._timer()

    def _timer(self) -> None:
        self.phase_end = time.time() + self.seconds if self.seconds else 0.0

    def left(self, team: str) -> int:
        return sum(1 for c, r in zip(self.colors, self.revealed) if c == team and not r)

    def _finish(self, winner: str, reason: str) -> None:
        self.winner, self.reason = winner, reason
        self.state = "finished"
        self.phase_end = 0.0
        for p in self.players:
            p.sel = None
        self.note(f"🏆 Team {NAMES[winner]} gewinnt!")

    def _end_turn(self, why: str = "") -> None:
        if why:
            self.note(why)
        self._begin_turn(other(self.turn))

    def check_hint(self, word: str) -> str:
        word = " ".join(str(word or "").split())
        if not word:
            raise RuleError("Bitte gib einen Hinweis ein")
        if " " in word:
            raise RuleError("Nur ein einziges Wort als Hinweis")
        if len(word) > 24 or not all(part.isalpha() for part in word.split("-")):
            raise RuleError("Der Hinweis muss ein Wort aus Buchstaben sein")
        h = norm(word)
        for w, r in zip(self.words, self.revealed):
            n = norm(w)
            if r:
                continue
            if h == n:
                raise RuleError(f"„{w}“ liegt auf dem Spielfeld – nimm ein anderes Wort")
            if h.startswith(n) or h.endswith(n) or n.startswith(h) or n.endswith(h):
                raise RuleError(f"„{word}“ ist zu nah an „{w}“ auf dem Spielfeld")
        return word

    def give_hint(self, word: str, number: int) -> None:
        if number != UNLIMITED and not 0 <= number <= 9:
            raise RuleError("Bitte eine Zahl von 0 bis 9 wählen")
        self.hint = {"word": word, "number": number}
        # Number + 1 guesses; 0 and ∞ allow as many as the team likes (until a wrong card).
        self.guesses_left = number + 1 if number >= 1 else None
        self.hints.append({"team": self.turn, "word": word, "number": number, "found": []})
        self.phase = "guess"
        self._timer()
        shown = "∞" if number == UNLIMITED else str(number)
        self.note(f"Hinweis für Team {NAMES[self.turn]}: {word} {shown}")

    def reveal(self, index: int, by: Player | None) -> None:
        if not 0 <= index < SIZE or self.revealed[index]:
            raise RuleError("Diese Karte ist schon aufgedeckt")
        self.revealed[index] = True
        color, word, team = self.colors[index], self.words[index], self.turn
        for p in self.players:
            if p.sel == index:
                p.sel = None
        self.last = {"i": index, "by": by.name if by else "", "team": team}
        who = by.name if by else f"Team {NAMES[team]}"
        if self.hints and self.hints[-1]["team"] == team:
            self.hints[-1]["found"].append({"w": word, "c": color})
        if color == ASSASSIN:
            self.note(f"💀 {who} deckt den Attentäter auf: {word}")
            self._finish(other(team), "assassin")
            return
        for t in (team, other(team)):
            if self.left(t) == 0:
                self.note(f"{who} deckt {word} auf – alle Wörter von Team {NAMES[t]} gefunden")
                self._finish(t, "cards")
                return
        if color == team:
            self.note(f"✓ {who}: {word} – richtig!")
            if self.guesses_left is not None:
                self.guesses_left -= 1
                if self.guesses_left <= 0:
                    self._end_turn("Keine Versuche mehr – der Zug ist vorbei")
        elif color == NEUTRAL:
            self._end_turn(f"✗ {who}: {word} ist neutral – Zug vorbei")
        else:
            self._end_turn(f"✗ {who}: {word} gehört Team {NAMES[color]} – Zug vorbei")

    # -- timer -------------------------------------------------------------------
    @property
    def deadline(self) -> float | None:
        return self.phase_end if self.state == "playing" and self.phase_end else None

    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        if self.phase == "hint":
            self._end_turn(f"⏱ Zeit um – Team {NAMES[self.turn]} hat keinen Hinweis bekommen")
        else:
            self._end_turn(f"⏱ Zeit um – Team {NAMES[other(self.turn)]} ist dran")

    # -- actions -----------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if not player:
            raise RuleError("Gerade nicht möglich")
        if self.state == "lobby":
            self._lobby_act(player, kind, is_host)
            return
        if self.state != "playing":
            raise RuleError("Gerade nicht möglich")
        lead = is_host or player.screen
        if kind == "skip":
            # Host or TV: nobody gives a hint / the team doesn't finish – move on.
            if not lead:
                raise RuleError("Nur der Gastgeber kann den Zug überspringen")
            self._end_turn(f"Zug von Team {NAMES[self.turn]} übersprungen")
            return
        if player.screen:
            raise RuleError("Der Bildschirm zeigt nur an")
        if kind == "hint":
            if self.phase != "hint" or player.team != self.turn or not player.spy:
                raise RuleError("Gerade gibt jemand anderes den Hinweis")
            word = self.check_hint(msg.get("word"))
            try:
                number = int(msg.get("number"))
            except (TypeError, ValueError):
                raise RuleError("Bitte eine Zahl wählen") from None
            self.give_hint(word, number)
        elif kind in ("select", "reveal", "end_turn"):
            if self.phase != "guess" or player.team != self.turn:
                raise RuleError("Dein Team ist gerade nicht dran")
            if player.spy:
                raise RuleError("Der Hinweisgeber rät nicht mit")
            if kind == "end_turn":
                self._end_turn(f"{player.name} beendet den Zug für Team {NAMES[self.turn]}")
                return
            index = msg.get("i")
            index = int(index) if index is not None else player.sel
            if index is None or not 0 <= index < SIZE:
                raise RuleError("Tippe zuerst auf eine Karte")
            if self.revealed[index]:
                raise RuleError("Diese Karte ist schon aufgedeckt")
            if kind == "select":
                player.sel = None if player.sel == index else index
            else:
                self.reveal(index, player)
        else:
            raise RuleError("Unbekannte Aktion")

    def _lobby_act(self, player: Player, kind, is_host: bool) -> None:
        if kind == "screen":
            current = self.screen
            if current and current is not player:
                raise RuleError(f"{current.name} ist schon der Bildschirm")
            player.screen = not player.screen
            player.team, player.spy = None, False
        elif kind in ("team_rot", "team_blau"):
            if player.screen:
                raise RuleError("Der Bildschirm spielt nicht mit")
            team = kind[5:]
            if player.team != team:
                player.team, player.spy = team, False
        elif kind == "spy":
            if player.screen or player.team not in TEAMS:
                raise RuleError("Wähle zuerst ein Team")
            if player.spy:
                player.spy = False
            else:
                for p in self.members(player.team):
                    p.spy = False
                player.spy = True
        elif kind == "shuffle":
            if not is_host:
                raise RuleError("Nur der Gastgeber kann die Teams mischen")
            gamers = self.gamers
            random.shuffle(gamers)
            first = random.choice(TEAMS)
            for i, p in enumerate(gamers):
                p.team = first if i % 2 == 0 else other(first)
                p.spy = False
        else:
            raise RuleError("Gerade nicht möglich")

    # -- players who left (computer players) ------------------------------------
    def humans(self, team: str) -> list[Player]:
        return [p for p in self.members(team) if not p.is_bot]

    def pending_bots(self) -> list:
        if self.state != "playing":
            return []
        # A Hinweisgeber who left: a teammate takes over (handled in bot_step).
        handover = [s for s in (self.spy_of(t) for t in TEAMS) if s and s.is_bot and self.humans(s.team)]
        if handover:
            return handover
        if self.phase == "hint":
            spy = self.spy_of(self.turn)
            return [spy] if spy and spy.is_bot else []
        if not any(not p.is_bot for p in self.guessers(self.turn)):
            return [p for p in self.guessers(self.turn) if p.is_bot][:1]
        return []

    def bot_step(self, bot: Player) -> None:
        if bot.spy and self.humans(bot.team):
            heir = random.choice(self.humans(bot.team))
            bot.spy, heir.spy, heir.sel = False, True, None
            self.note(f"🕵️ {heir.name} ist jetzt Hinweisgeber für Team {NAMES[bot.team]}")
            return
        if self.phase == "hint" and bot.spy and bot.team == self.turn:
            # A team without people left: a plain hint so the game goes on.
            self.give_hint("(Computer)", 1)
            return
        if self.phase == "guess" and bot.team == self.turn and not bot.spy:
            # Computer guessers only guess once per turn and never touch the Attentäter.
            choices = [i for i in range(SIZE) if not self.revealed[i] and self.colors[i] != ASSASSIN]
            team = self.turn
            self.reveal(random.choice(choices), bot)
            if self.state == "playing" and self.phase == "guess" and self.turn == team:
                self._end_turn()

    # -- view --------------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        me = self.player(viewer_id)
        over = self.state == "finished"
        key = bool(me and me.spy and not me.screen and self.state == "playing") or over
        # Taps are shared with the team on turn (and the TV), so they can discuss them.
        sees_sel = bool(me and (me.screen or me.team == self.turn)) and self.state == "playing"
        board = [{"w": w, "r": r, "c": c if (r or key) else None}
                 for w, c, r in zip(self.words, self.colors, self.revealed)] if self.state != "lobby" else []
        return {
            "kind": self.KIND, "code": self.code, "state": self.state, "phase": self.phase,
            "host": self.host_id, "settings": {"seconds": self.seconds},
            "screen": self.screen.id if self.screen else None,
            "players": [{"id": p.id, "name": p.name, "bot": p.is_bot, "screen": p.screen, "team": p.team, "spy": p.spy,
                         "sel": p.sel if sees_sel and p.team == self.turn else None} for p in self.players],
            "board": board, "turn": self.turn, "starter": self.starter,
            "hint": self.hint, "guesses_left": self.guesses_left,
            "hints": self.hints[-12:],
            "left": {t: self.left(t) for t in TEAMS} if self.colors else {},
            "total": {t: self.colors.count(t) for t in TEAMS} if self.colors else {},
            "last": self.last, "winner": self.winner, "reason": self.reason,
            "remaining": max(0, round(self.phase_end - time.time(), 1)) if self.deadline else None,
            "seconds": self.seconds,
            "log": self.log[-6:],
        }
