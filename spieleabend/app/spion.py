"""Spion: everyone secretly gets the same location and a fitting role – except the spy.

The questions are asked out loud; the phones hand out the cards, pick who starts, run the clock,
the votes and the spy's guess. One device can be the TV screen: it only shows public things.
"""

import random
import time

import spion_daten
from common import RuleError
from party import PartyGame

CARD_TIME = 120     # seconds to look at the card before the round starts anyway
VOTE_TIME = 60
GUESS_TIME = 60


class Game(PartyGame):
    KIND = "spion"
    MIN_PLAYERS, MAX_PLAYERS = 3, 16
    ROUNDS = (5, 3, 8, 10)
    TIMES = (480, 300, 600)        # 8 / 5 / 10 minutes of questions
    INPUT_PHASES = ("cards", "vote")

    def __init__(self, code: str):
        super().__init__(code)
        self.spy_setting = 1
        self.location = ""
        self.spies: list[str] = []
        self.roles: dict[str, str] = {}
        self.starter: str | None = None
        self.caller: str | None = None
        self.ask_left = 0.0           # question time left while a vote interrupts it
        self.final_vote = False
        self.last_vote: dict | None = None
        self.guesser: str | None = None
        self.self_reveal = False
        self.guess: str | None = None
        self.winner = ""             # spies | agents
        self.how = ""                # survived | innocent | guessed | caught | revealed_right | revealed_wrong

    # -- settings ------------------------------------------------------------
    def configure_more(self, settings: dict) -> None:
        spies = settings.get("spies")
        self.spy_setting = 2 if spies is not None and int(spies) == 2 else 1

    def settings_view(self) -> dict:
        return {**super().settings_view(), "spies": self.spy_setting}

    def phase_attr(self) -> str:
        return "pick" if self.phase == "vote" else "answer"

    @property
    def humans(self):
        return [p for p in self.gamers if not p.is_bot]

    # -- rounds --------------------------------------------------------------
    def setup_round(self) -> None:
        pool = [n for n in spion_daten.NAMES if n not in self.used] or spion_daten.NAMES
        self.location = random.choice(pool)
        self.used.add(self.location)
        gamers = self.gamers
        count = 2 if self.spy_setting == 2 and len(gamers) >= 5 else 1
        self.spies = [p.id for p in random.sample(gamers, count)]
        roles = list(spion_daten.BY_NAME[self.location][1])
        random.shuffle(roles)
        agents = [p for p in gamers if p.id not in self.spies]
        self.roles = {p.id: roles[i % len(roles)] for i, p in enumerate(agents)}
        starters = [p for p in gamers if not p.is_bot] or gamers
        self.starter = random.choice(starters).id
        self.caller = None
        self.ask_left = 0.0
        self.final_vote = False
        self.last_vote = None
        self.guesser = None
        self.self_reveal = False
        self.guess = None
        self.winner = self.how = ""
        self.phase = "cards"
        self.phase_end = time.time() + CARD_TIME
        self.note(f"Runde {self.round}: Schaut euch heimlich eure Karte an")

    def _start_questions(self) -> None:
        self.phase = "ask"
        self.phase_end = time.time() + self.seconds
        self.note(f"{self.player(self.starter).name} stellt die erste Frage")

    def _start_vote(self, caller, final: bool) -> None:
        self.final_vote = final
        self.ask_left = 0.0 if final else max(0.0, self.phase_end - time.time())
        self.caller = caller.id if caller and not caller.screen else None
        for p in self.players:
            p.pick = None
        self.phase = "vote"
        self.phase_end = time.time() + VOTE_TIME
        if final:
            self.note("Die Zeit ist um – letzte Abstimmung!")
        else:
            self.note(f"{caller.name if caller and not caller.screen else 'Jemand'} ruft zur Abstimmung")

    def _resolve_vote(self) -> None:
        votes = {p.id: p.pick for p in self.gamers if p.pick}
        tally: dict[str, int] = {}
        for target in votes.values():
            tally[target] = tally.get(target, 0) + 1
        need = len(self.humans) // 2 + 1
        top = max(tally.values(), default=0)
        leaders = [pid for pid, n in tally.items() if n == top]
        accused = leaders[0] if len(leaders) == 1 and top >= need else None
        self.last_vote = {"tally": tally, "votes": votes, "accused": accused, "need": need}
        if accused is None:
            if self.final_vote:
                self.note("Keine Mehrheit – der Spion entkommt")
                self._finish("spies", "survived")
            else:
                self.note("Keine Mehrheit – weiter geht's mit den Fragen")
                self.phase = "ask"
                self.phase_end = time.time() + max(5.0, self.ask_left)
            return
        target = self.player(accused)
        if accused in self.spies:
            self.note(f"{target.name} ist ein Spion! Letzte Chance: den Ort erraten")
            self._start_guess(accused, False)
        else:
            self.note(f"{target.name} war unschuldig!")
            self._finish("spies", "innocent")

    def _start_guess(self, spy_id: str, self_reveal: bool) -> None:
        self.guesser = spy_id
        self.self_reveal = self_reveal
        self.phase = "guess"
        self.phase_end = time.time() + GUESS_TIME

    def _resolve_guess(self, guess: str | None) -> None:
        self.guess = guess
        right = guess == self.location
        if self.self_reveal:
            self._finish("spies" if right else "agents", "revealed_right" if right else "revealed_wrong")
        else:
            self._finish("spies" if right else "agents", "guessed" if right else "caught")

    def _finish(self, winner: str, how: str) -> None:
        self.winner, self.how = winner, how
        votes = (self.last_vote or {}).get("votes", {})
        for p in self.gamers:
            spy = p.id in self.spies
            if winner == "spies" and spy:
                if p.id == self.guesser and how == "revealed_right":
                    p.gained = 4
                elif p.id == self.guesser and how == "guessed":
                    p.gained = 3
                else:
                    p.gained = 2
            elif winner == "agents" and not spy:
                p.gained = 1 + (1 if how == "caught" and votes.get(p.id) in self.spies else 0)
            p.score += p.gained
        self.phase = "reveal"
        self.phase_end = 0.0
        names = ", ".join(self.player(i).name for i in self.spies if self.player(i))
        self.note(("Die Spione gewinnen" if len(self.spies) > 1 else "Der Spion gewinnt") if winner == "spies"
                  else "Die Agenten gewinnen")
        self.note(f"Ort: {self.location} · {'Spione' if len(self.spies) > 1 else 'Spion'}: {names}")

    # -- timers --------------------------------------------------------------
    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        if self.phase == "cards":
            self._start_questions()
        elif self.phase == "ask":
            self._start_vote(None, True)
        elif self.phase == "vote":
            self._resolve_vote()
        elif self.phase == "guess":
            self._resolve_guess(None)

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if kind in ("screen", "next", "end_game") or not player or self.state != "playing":
            return super().act(player_id, msg, is_host)
        leader = is_host or player.id in self.leaders() or player.screen
        if kind == "seen":
            if self.phase != "cards" or player.screen:
                return
            player.answer = True
            if all(p.answer for p in self.humans):
                self._start_questions()
        elif kind == "skip":
            if not leader:
                raise RuleError("Nur der Gastgeber kann das")
            if self.phase == "cards":
                self._start_questions()
            elif self.phase == "vote":
                self._resolve_vote()
        elif kind == "call_vote":
            if self.phase != "ask":
                return            # someone else was quicker
            if player.is_bot:
                raise RuleError("Gerade nicht möglich")
            self._start_vote(player, False)
        elif kind == "vote":
            if self.phase != "vote" or player.screen:
                raise RuleError("Gerade wird nicht abgestimmt")
            target = str(msg.get("id") or "")
            if target and (target == player.id or not self.player(target) or self.player(target).screen):
                raise RuleError("Bitte jemand anderen wählen")
            player.pick = target       # "" = abstain
            if all(p.pick is not None for p in self.humans):
                self._resolve_vote()
        elif kind == "spy_reveal":
            if self.phase != "ask" or player.id not in self.spies:
                raise RuleError("Gerade nicht möglich")
            self.note(f"🕵️ {player.name} gibt sich als Spion zu erkennen und tippt auf den Ort!")
            self._start_guess(player.id, True)
        elif kind == "guess":
            if self.phase != "guess" or player.id != self.guesser:
                raise RuleError("Gerade nicht möglich")
            guess = str(msg.get("place") or "")
            if guess not in spion_daten.BY_NAME:
                raise RuleError("Bitte einen Ort aus der Liste wählen")
            self._resolve_guess(guess)
        else:
            raise RuleError("Unbekannte Aktion")

    # -- players who left: they look at nothing, abstain and guess at random ----
    def pending_bots(self) -> list:
        if self.state != "playing":
            return []
        if self.phase == "cards":
            return [p for p in self.gamers if p.is_bot and not p.answer]
        if self.phase == "vote":
            return [p for p in self.gamers if p.is_bot and p.pick is None]
        if self.phase == "guess":
            spy = self.player(self.guesser)
            return [spy] if spy and spy.is_bot else []
        return []

    def bot_step(self, bot) -> None:
        if self.phase == "cards":
            bot.answer = True
            if all(p.answer for p in self.humans):
                self._start_questions()
        elif self.phase == "vote":
            bot.pick = ""
            if all(p.pick is not None for p in self.humans):
                self._resolve_vote()
        elif self.phase == "guess":
            self._resolve_guess(random.choice(spion_daten.NAMES))

    # -- results -------------------------------------------------------------
    def place_of(self, player) -> int:
        """1 = most points at the end (ties share first place), 2 = everyone else."""
        top = max((p.score for p in self.gamers), default=0)
        return 1 if top > 0 and player.score == top else 2

    # -- view ----------------------------------------------------------------
    def extra_view(self, me) -> dict:
        over = self.phase == "reveal" or self.state == "finished"
        playing = me is not None and not me.screen
        spy = playing and me.id in self.spies
        known = over or (playing and not spy)
        show_vote = self.phase in ("guess", "reveal") or (self.phase == "ask" and self.last_vote)
        return {
            "locations": [[n, e] for n, e, _ in spion_daten.LOCATIONS],
            "role": ("spy" if spy else "agent") if playing else None,
            "location": self.location if known else None,
            "emoji": spion_daten.BY_NAME[self.location][0] if known and self.location else None,
            "my_role": self.roles.get(me.id) if playing and not spy else None,
            "spy_count": len(self.spies),
            "starter": self.starter, "caller": self.caller, "final_vote": self.final_vote,
            "ask_left": round(self.ask_left) if self.phase == "vote" and not self.final_vote else None,
            "my_vote": me.pick if me and self.phase == "vote" else None,
            "last_vote": self.last_vote if show_vote else None,
            "guesser": self.guesser if self.phase in ("guess", "reveal") else None,
            "self_reveal": self.self_reveal,
            "guess": self.guess if over else None,
            "winner": self.winner, "how": self.how,
            "spies": self.spies if over else [],
            "roles": self.roles if over else {},
        }


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
