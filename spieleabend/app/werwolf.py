"""Werwolf: the phones are the game master.

Night: Amor (first night only), the seer, the werewolves and the witch act on their phones while everyone
else keeps their eyes shut. Day: the dead are announced, the village discusses and lynches someone.
The TV screen only narrates and shows who is alive and the vote results – never secret information.
Players who leave become placeholders: their roles act automatically or are skipped after a short pause,
so no phase ever waits for them.
"""

import random
import time

import party
from common import RuleError
from party import PartyGame

ROLES_TIME = 120    # look at the role card
ROLE_TIME = 75      # seer, witch, Amor, hunter
WOLF_TIME = 90
VOTE_TIME = 90
ABSENT = (5.0, 9.0)  # pause for a role nobody plays any more (so the narration doesn't give it away)

WOLF, VILLAGER, SEER, WITCH, HUNTER, AMOR = "werwolf", "dorf", "seherin", "hexe", "jaeger", "amor"
ROLE_NAMES = {WOLF: "Werwolf", VILLAGER: "Dorfbewohner", SEER: "Seherin", WITCH: "Hexe", HUNTER: "Jäger", AMOR: "Amor"}
NIGHT_ORDER = (AMOR, SEER, WOLF, WITCH)


class Player(party.Player):
    def __init__(self, name: str, is_bot: bool = False):
        super().__init__(name, is_bot)
        self.role = ""
        self.alive = True


def wolf_count(players: int, setting: int) -> int:
    """Number of werewolves: automatic (0) or chosen, but always fewer than the rest."""
    auto = 1 if players <= 6 else 2 if players <= 10 else 3
    wanted = setting if setting in (1, 2, 3) else auto
    return max(1, min(wanted, (players - 1) // 2))


class Game(PartyGame):
    KIND = "werwolf"
    MIN_PLAYERS, MAX_PLAYERS = 5, 18
    TIMES = (180, 120, 300, 0)          # discussion time, 0 = until someone starts the vote
    INPUT_PHASES = ("roles", "vote")

    def __init__(self, code: str):
        super().__init__(code)
        self.wolves_setting = 0
        self.specials = 2                # 0: seer + witch, 1: + hunter, 2: + hunter + Amor
        self.night = 0
        self.lovers: list[str] = []
        self.victim: str | None = None
        self.wolf_votes: dict[str, str] = {}
        self.heal_left = True
        self.poison_left = True
        self.poisoned: str | None = None
        self.seer_result: dict | None = None
        self.seer_log: list[dict] = []
        self.events: list[dict] = []     # deaths to announce (dawn / verdict / end)
        self.hunter_id: str | None = None
        self.hunter_used = False
        self.return_to = ""
        self.last_vote: dict | None = None
        self.winner = ""                 # dorf | werwolf | liebe

    def new_player(self, name: str, is_bot: bool = False) -> Player:
        return Player(name, is_bot)

    # -- settings ------------------------------------------------------------
    def configure(self, settings: dict) -> None:
        seconds = settings.get("seconds")
        self.seconds = int(seconds) if seconds is not None and int(seconds) in self.TIMES else self.TIMES[0]
        wolves = settings.get("wolves")
        self.wolves_setting = int(wolves) if wolves is not None and int(wolves) in (0, 1, 2, 3) else 0
        specials = settings.get("specials")
        self.specials = int(specials) if specials is not None and int(specials) in (0, 1, 2) else 2

    def settings_view(self) -> dict:
        return {"seconds": self.seconds, "wolves": self.wolves_setting, "specials": self.specials}

    def phase_attr(self) -> str:
        return "pick" if self.phase == "vote" else "answer"

    # -- helpers -------------------------------------------------------------
    @property
    def alive(self) -> list[Player]:
        return [p for p in self.gamers if p.alive]

    def holder(self, role: str) -> Player | None:
        return next((p for p in self.gamers if p.role == role), None)

    def has_role(self, role: str) -> bool:
        return self.holder(role) is not None

    def alive_humans(self) -> list[Player]:
        return [p for p in self.alive if not p.is_bot]

    def is_wolf(self, p) -> bool:
        return p.role == WOLF

    # -- start ---------------------------------------------------------------
    def start(self) -> None:
        gamers = self.gamers
        if len(gamers) < self.MIN_PLAYERS:
            raise RuleError(f"Mindestens {self.MIN_PLAYERS} Spieler nötig (der Bildschirm zählt nicht)")
        if len(gamers) > self.MAX_PLAYERS:
            raise RuleError(f"Maximal {self.MAX_PLAYERS} Spieler")
        wolves = wolf_count(len(gamers), self.wolves_setting)
        specials = [SEER, WITCH] + ([HUNTER] if self.specials >= 1 else []) + ([AMOR] if self.specials >= 2 else [])
        specials = specials[:len(gamers) - wolves]
        roles = [WOLF] * wolves + specials
        roles += [VILLAGER] * (len(gamers) - len(roles))
        random.shuffle(roles)
        for p, role in zip(gamers, roles):
            p.role, p.alive = role, True
            p.answer = p.pick = None
            p.score = p.gained = 0
        for p in self.players:
            if p.screen:
                p.role, p.alive = "", False
        self.round = self.night = 0
        self.lovers = []
        self.victim = None
        self.wolf_votes = {}
        self.heal_left = self.poison_left = True
        self.poisoned = None
        self.seer_result = None
        self.seer_log = []
        self.events = []
        self.hunter_id = None
        self.hunter_used = False
        self.last_vote = None
        self.winner = ""
        self.log = []
        self.state = "playing"
        self.phase = "roles"
        self.phase_end = time.time() + ROLES_TIME
        self.note(f"{wolves} {'Werwolf' if wolves == 1 else 'Werwölfe'} haben sich ins Dorf geschlichen …")

    # -- night ---------------------------------------------------------------
    def _start_night(self) -> None:
        self.night += 1
        self.round = self.night
        self.victim = None
        self.wolf_votes = {}
        self.seer_result = None
        self.events = []
        self.last_vote = None
        for p in self.players:
            p.pick = None
        self.note(f"🌙 Nacht {self.night}: Das Dorf schläft ein …")
        self._night_step(None)

    def _night_step(self, after: str | None) -> None:
        order = list(NIGHT_ORDER)
        start = order.index(after) + 1 if after else 0
        for step in order[start:]:
            if step == AMOR and (self.night != 1 or not self.has_role(AMOR)):
                continue
            if step in (SEER, WITCH) and not self.has_role(step):
                continue
            self.phase = step
            if step == WOLF:
                self.phase_end = time.time() + WOLF_TIME
            else:
                holder = self.holder(step)
                acts = holder and holder.alive and not holder.is_bot
                self.phase_end = time.time() + (ROLE_TIME if acts else random.uniform(*ABSENT))
            return
        self._dawn()

    def _resolve_wolves(self) -> None:
        tally: dict[str, int] = {}
        for target in self.wolf_votes.values():
            if self.player(target) and self.player(target).alive:
                tally[target] = tally.get(target, 0) + 1
        top = max(tally.values(), default=0)
        choices = [pid for pid, n in tally.items() if n == top]
        self.victim = random.choice(choices) if choices else None
        self._night_step(WOLF)

    def _dawn(self) -> None:
        self.events = []
        dead = []
        if self.victim:
            dead.append((self.victim, WOLF))
        if self.poisoned:
            dead.append((self.poisoned, WITCH))
        self.poisoned = None
        for pid, cause in dead:
            self._kill(pid, cause)
        names = [self.player(e["id"]).name for e in self.events]
        self.note("☀️ Das Dorf erwacht – " + (f"{' und '.join(names)} {'ist' if len(names) == 1 else 'sind'} tot"
                                              if names else "niemand ist gestorben"))
        self._settle("dawn")

    def _kill(self, pid: str, cause: str) -> None:
        p = self.player(pid)
        if not p or not p.alive:
            return
        p.alive = False
        self.events.append({"id": pid, "cause": cause, "role": p.role})
        if pid in self.lovers:
            other = next(i for i in self.lovers if i != pid)
            self._kill(other, "liebe")

    def _settle(self, then: str) -> None:
        """After deaths: the hunter shoots, then the game ends or goes on with `then` (dawn / verdict)."""
        hunter = next((p for p in self.gamers if p.role == HUNTER and not p.alive), None)
        if hunter and not self.hunter_used:
            self.hunter_used = True
            self.hunter_id = hunter.id
            self.return_to = then
            self.phase = "hunter"
            self.phase_end = time.time() + ROLE_TIME
            return
        winner = self._winner()
        if winner:
            self._end(winner)
            return
        self.phase = then
        self.phase_end = 0.0

    def _winner(self) -> str:
        alive = self.alive
        wolves = [p for p in alive if p.role == WOLF]
        lovers = [self.player(i) for i in self.lovers]
        if (len(alive) == 2 and all(p and p.alive for p in lovers)
                and len({p.role == WOLF for p in lovers}) == 2):
            return "liebe"
        if not wolves:
            return "dorf"
        if len(wolves) >= len(alive) - len(wolves):
            return "werwolf"
        return ""

    def _end(self, winner: str) -> None:
        self.winner = winner
        self.state = "finished"
        self.phase_end = 0.0
        for p in self.gamers:
            p.score = 1 if self.place_of(p) == 1 else 0
        self.note({"dorf": "🏡 Das Dorf gewinnt – alle Werwölfe sind tot!",
                   "werwolf": "🐺 Die Werwölfe haben das Dorf übernommen!",
                   "liebe": "💘 Das Liebespaar gewinnt – gegen den Rest der Welt!"}[winner])

    def finish(self) -> None:
        """The host ends the game early: nobody wins."""
        self.state = "finished"
        self.phase_end = 0.0
        self.note("Das Spiel wurde beendet")

    # -- day -----------------------------------------------------------------
    def _start_day(self) -> None:
        self.phase = "day"
        self.phase_end = time.time() + self.seconds if self.seconds else 0.0

    def _start_vote(self) -> None:
        for p in self.players:
            p.pick = None
        self.phase = "vote"
        self.phase_end = time.time() + VOTE_TIME

    def _resolve_vote(self) -> None:
        votes = {p.id: p.pick for p in self.alive if p.pick is not None}
        tally: dict[str, int] = {}
        for target in votes.values():
            tally[target] = tally.get(target, 0) + 1
        top = max(tally.values(), default=0)
        leaders = [t for t, n in tally.items() if n == top]
        lynched = leaders[0] if top and len(leaders) == 1 and leaders[0] else None
        self.last_vote = {"votes": votes, "tally": tally, "lynched": lynched}
        self.events = []
        if lynched:
            self._kill(lynched, "dorf")
            self.note(f"⚖️ Das Dorf hat {self.player(lynched).name} gehängt")
        else:
            self.note("⚖️ Keine Mehrheit – heute stirbt niemand")
        self._settle("verdict")

    # -- timers --------------------------------------------------------------
    def on_deadline(self) -> None:
        if self.state != "playing":
            return
        phase = self.phase
        if phase == "roles":
            self._start_night()
        elif phase in (AMOR, SEER, WITCH):
            self._night_step(phase)
        elif phase == WOLF:
            self._resolve_wolves()
        elif phase == "hunter":
            self._settle(self.return_to)
        elif phase == "day":
            self._start_vote()
        elif phase == "vote":
            self._resolve_vote()

    # -- actions -------------------------------------------------------------
    def act(self, player_id: str, msg: dict, is_host: bool) -> None:
        kind = msg.get("t")
        player = self.player(player_id)
        if kind in ("screen", "end_game") or not player or self.state != "playing":
            return super().act(player_id, msg, is_host)
        leader = is_host or player.id in self.leaders() or player.screen
        phase = self.phase
        if kind == "skip":
            if not leader:
                raise RuleError("Nur der Gastgeber kann das")
            if phase == "roles":
                self._start_night()
            elif phase == "vote":
                self._resolve_vote()
            return
        if kind == "continue":
            # Everyone (and the TV) may move on after the announcement.
            if phase == "dawn":
                self._start_day()
            elif phase == "verdict":
                self._start_night()
            return
        if kind == "to_vote":
            if phase == "day" and (player.screen or player.alive):
                self._start_vote()
            return
        if player.screen:
            raise RuleError("Der Bildschirm zeigt nur an")
        if kind == "ready":
            if phase == "roles":
                player.answer = True
                if all(p.answer for p in self.gamers if not p.is_bot):
                    self._start_night()
            return
        if not player.alive and not (kind == "shoot" and player.id == self.hunter_id):
            raise RuleError("Tote spielen nicht mehr mit – aber zuschauen dürft ihr!")
        if kind == "amor":
            self._need(phase == AMOR and player.role == AMOR)
            ids = [str(i) for i in (msg.get("ids") or [])][:2]
            if len(ids) != 2 or ids[0] == ids[1] or not all(self.player(i) and self.player(i).alive and not self.player(i).screen for i in ids):
                raise RuleError("Bitte zwei verschiedene Spieler wählen")
            self.lovers = ids
            self._night_step(AMOR)
        elif kind == "see":
            self._need(phase == SEER and player.role == SEER and self.seer_result is None)
            target = self.player(str(msg.get("id")))
            if not target or target is player or not target.alive or target.screen:
                raise RuleError("Bitte einen anderen lebenden Spieler wählen")
            self.seer_result = {"id": target.id, "wolf": target.role == WOLF}
            self.seer_log.append({"night": self.night, **self.seer_result})
        elif kind == "seer_done":
            self._need(phase == SEER and player.role == SEER)
            self._night_step(SEER)
        elif kind == "wolf":
            self._need(phase == WOLF and player.role == WOLF)
            target = self.player(str(msg.get("id")))
            if not target or not target.alive or target.role == WOLF or target.screen:
                raise RuleError("Bitte ein Opfer aus dem Dorf wählen")
            self.wolf_votes[player.id] = target.id
            humans = [p for p in self.alive if p.role == WOLF and not p.is_bot]
            if all(self.wolf_votes.get(p.id) == target.id for p in humans):
                self._resolve_wolves()
        elif kind == "witch":
            self._need(phase == WITCH and player.role == WITCH)
            heal = bool(msg.get("heal"))
            poison = str(msg.get("poison") or "")
            if heal and (not self.heal_left or not self.victim):
                raise RuleError("Der Heiltrank ist schon verbraucht")
            if poison:
                target = self.player(poison)
                if not self.poison_left:
                    raise RuleError("Der Gifttrank ist schon verbraucht")
                if not target or not target.alive or target is player or target.screen:
                    raise RuleError("Bitte einen anderen lebenden Spieler wählen")
            if heal:
                self.heal_left = False
                self.victim = None
            if poison:
                self.poison_left = False
                self.poisoned = poison
            self._night_step(WITCH)
        elif kind == "shoot":
            self._need(phase == "hunter" and player.id == self.hunter_id)
            target = str(msg.get("id") or "")
            if target:
                p = self.player(target)
                if not p or not p.alive or p.screen:
                    raise RuleError("Bitte einen lebenden Spieler wählen")
                self._kill(target, HUNTER)
                self.note(f"🏹 {player.name} reißt {p.name} mit in den Tod")
            self._settle(self.return_to)
        elif kind == "vote":
            self._need(phase == "vote")
            target = str(msg.get("id") or "")
            if target and (target == player.id or not self.player(target) or not self.player(target).alive):
                raise RuleError("Bitte einen anderen lebenden Spieler wählen")
            player.pick = target          # "" = nobody
            if all(p.pick is not None for p in self.alive_humans()):
                self._resolve_vote()
        else:
            raise RuleError("Unbekannte Aktion")

    @staticmethod
    def _need(ok: bool) -> None:
        if not ok:
            raise RuleError("Gerade nicht möglich")

    # -- players who left: placeholders act automatically or are skipped ----------
    def pending_bots(self) -> list:
        if self.state != "playing":
            return []
        phase = self.phase
        if phase == "roles":
            return [p for p in self.gamers if p.is_bot and not p.answer]
        if phase == WOLF:
            wolves = [p for p in self.alive if p.role == WOLF]
            if wolves and all(p.is_bot for p in wolves):
                return wolves[:1]
            return []
        if phase in (AMOR, SEER, WITCH):
            holder = self.holder(phase)
            # Left during their turn: wait a moment, then the night goes on (see bot_step).
            if holder and holder.is_bot and self.phase_end - time.time() > ABSENT[1] + 1:
                return [holder]
            return []
        if phase == "hunter":
            hunter = self.player(self.hunter_id)
            return [hunter] if hunter and hunter.is_bot else []
        if phase == "vote":
            return [p for p in self.alive if p.is_bot and p.pick is None]
        return []

    def bot_step(self, bot) -> None:
        phase = self.phase
        if phase == "roles":
            bot.answer = True
            if all(p.answer for p in self.gamers if not p.is_bot):
                self._start_night()
        elif phase == WOLF:
            targets = [p for p in self.alive if p.role != WOLF]
            if targets:
                self.wolf_votes[bot.id] = random.choice(targets).id
            self._resolve_wolves()
        elif phase in (AMOR, SEER, WITCH):
            self.phase_end = time.time() + random.uniform(*ABSENT)
        elif phase == "hunter":
            self._settle(self.return_to)
        elif phase == "vote":
            bot.pick = ""
            if all(p.pick is not None for p in self.alive_humans()):
                self._resolve_vote()

    # -- results -------------------------------------------------------------
    def place_of(self, player) -> int:
        """1 = on the winning side, 2 = everyone else."""
        if self.winner == "dorf":
            return 1 if player.role != WOLF else 2
        if self.winner == "werwolf":
            return 1 if player.role == WOLF else 2
        if self.winner == "liebe":
            return 1 if player.id in self.lovers else 2
        return 2

    # -- view ----------------------------------------------------------------
    def view_for(self, viewer_id) -> dict:
        view = super().view_for(viewer_id)
        me = self.player(viewer_id)
        # Night timers only for whoever is acting (a short countdown would give away an absent role).
        if self.phase in NIGHT_ORDER and not self._acting(me):
            view["remaining"] = None
        return view

    def _acting(self, me) -> bool:
        if not me or me.screen or not me.alive or self.state != "playing":
            return False
        return me.role == self.phase

    def extra_view(self, me) -> dict:
        over = self.state == "finished"
        gamer = me is not None and not me.screen
        ghost = gamer and not me.alive and self.state == "playing"
        sees_all = over or ghost
        wolf = gamer and me.role == WOLF
        acting = self._acting(me)
        view = {
            "role": me.role if gamer else None,
            "alive": me.alive if gamer else None,
            "night": self.night,
            "village": [{"id": p.id, "alive": p.alive,
                         "role": p.role if (sees_all or not p.alive or p is me or (wolf and p.role == WOLF)) else None}
                        for p in self.gamers],
            "lovers": self.lovers if (sees_all or (gamer and (me.id in self.lovers or me.role == AMOR))) else [],
            "has": {r: self.has_role(r) for r in (SEER, WITCH, HUNTER, AMOR)},
            "wolves_total": sum(1 for p in self.gamers if p.role == WOLF),
            "events": self.events if self.phase in ("dawn", "verdict", "hunter") or over else [],
            "hunter": self.hunter_id if self.phase == "hunter" or over else None,
            "last_vote": self.last_vote if self.phase in ("verdict", "hunter") or over else None,
            "my_vote": me.pick if gamer and self.phase == "vote" else None,
            "winner": self.winner,
        }
        if wolf and self.phase == WOLF and me.alive:
            view["wolf_votes"] = self.wolf_votes
        if gamer and me.role == SEER:
            view["seer_log"] = self.seer_log
            view["seer_result"] = self.seer_result if acting else None
        if acting and me.role == WITCH:
            view["witch"] = {"victim": self.victim, "heal": self.heal_left, "poison": self.poison_left}
        return view


MIN_PLAYERS, MAX_PLAYERS = Game.MIN_PLAYERS, Game.MAX_PLAYERS
