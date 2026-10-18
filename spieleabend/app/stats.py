"""Reports finished games to the Bestenliste add-on (rankings and achievements).

The Bestenliste is found by this add-on's host name ("1a2b3c4d-spieleabend" → "1a2b3c4d-bestenliste").
Without it nothing happens; results that could not be delivered are kept and sent later.
"""

import asyncio
import json
import logging
import os
import socket
import time
from pathlib import Path

import aiohttp

log = logging.getLogger("bestenliste")

PORT = 8091
PENDING = Path(os.environ.get("SPIELE_DATA", "/data")) / "bestenliste-pending.json"
MAX_PENDING = 300

TITLES = {
    "stapeljagd": "Stapeljagd", "tiefpunkt": "Tiefpunkt", "farbrausch": "Farbrausch", "kritzelpost": "Kritzelpost",
    "schnellmaler": "Schnellmaler", "galgenraten": "Galgenraten", "imposter": "Imposter", "schaetzmeister": "Schätzmeister",
    "werwuerde": "Wer würde eher …?", "luegenbaron": "Lügenbaron", "punchline": "Punchline", "nochnie": "Ich hab noch nie …",
    "wahrheit": "Wahrheit oder Trinken", "ringoffire": "Ring of Fire", "trinklotto": "Trinklotto", "pyramide": "Pyramide",
    "pferderennen": "Pferderennen", "buzzer": "Buzzer-Quiz", "sortierfix": "Sortierfix", "spion": "Spion",
    "codewoerter": "Codewörter", "werwolf": "Werwolf", "blindmaler": "Blind gezeichnet",
    "stadtlandfluss": "Stadt-Land-Fluss", "schwimmen": "Schwimmen (31)",
}
HIGHER_WINS = {"schaetzmeister", "luegenbaron", "punchline", "schnellmaler", "galgenraten", "imposter",
               "buzzer", "sortierfix", "blindmaler", "stadtlandfluss"}
LOWER_WINS = {"tiefpunkt"}
WINNER_ONLY = {"stapeljagd", "farbrausch", "schwimmen"}
# Drinking games: the score counts sips, nobody "wins".
SIPS = {"nochnie", "pferderennen", "pyramide", "trinklotto", "wahrheit"}


def url() -> str:
    env = os.environ.get("SPIELE_BESTENLISTE_URL", "").strip()
    if env:
        return env.rstrip("/")
    host = socket.gethostname()
    prefix = host.split("-", 1)[0] if "-" in host else "local"
    return f"http://{prefix}-bestenliste:{PORT}"


def _score(p) -> float | None:
    for attr in ("total", "score"):
        value = getattr(p, attr, None)
        if isinstance(value, (int, float)):
            return value
    return None


def result(kind: str, game) -> dict:
    """What the Bestenliste needs to know about a finished game."""
    people = [p for p in game.players if not getattr(p, "screen", False)]
    players = []
    for p in people:
        left = p.is_bot and p.name.endswith(" (Bot)")      # a person who left during the game
        players.append({"name": p.name[:-6] if left else p.name, "bot": bool(p.is_bot), "left": left,
                        "account": getattr(p, "account", None), "score": _score(p), "place": None, "won": False})
    winner = getattr(game, "winner", None)
    if hasattr(game, "place_of"):
        # Team games (Codewörter, Werwolf, Spion): the game knows who was on the winning side.
        for p, x in zip(people, players):
            x["place"] = game.place_of(p)
    elif kind in HIGHER_WINS or kind in LOWER_WINS:
        sign = -1 if kind in LOWER_WINS else 1
        ordered = sorted(players, key=lambda x: -sign * (x["score"] or 0))
        for i, x in enumerate(ordered):
            same = i and ordered[i - 1]["score"] == x["score"]
            x["place"] = ordered[i - 1]["place"] if same else i + 1
    elif kind in WINNER_ONLY and isinstance(winner, str) and winner:
        for x in players:
            x["place"] = 1 if x["name"] == winner or x["name"] + " (Bot)" == winner else 2
    for x in players:
        x["won"] = x["place"] == 1 and len(players) > 1
        if kind in SIPS:
            x["sips"], x["score"] = int(x["score"] or 0), None
    accounts = {x["name"]: x["account"] for x in players if x["account"]}
    highlights = [{"name": n, "what": w, "account": accounts.get(n)} for n, w in getattr(game, "highlights", [])]
    game.highlights = []
    return {"kind": kind, "title": TITLES.get(kind, kind), "ts": time.time(), "players": players, "highlights": highlights}


class Reporter:
    def __init__(self) -> None:
        try:
            self.pending: list[dict] = json.loads(PENDING.read_text())
        except (OSError, ValueError):
            self.pending = []
        self.lock = asyncio.Lock()

    def _save(self) -> None:
        try:
            PENDING.parent.mkdir(parents=True, exist_ok=True)
            PENDING.write_text(json.dumps(self.pending[-MAX_PENDING:], ensure_ascii=False))
        except OSError as err:
            log.warning("Ergebnisse nicht gespeichert: %s", err)

    async def report(self, data: dict) -> list[str]:
        """Sends this result (and any older ones still waiting); returns notes for the game log."""
        async with self.lock:
            self.pending.append(data)
            notes: list[str] = []
            try:
                async with aiohttp.ClientSession(trust_env=False, timeout=aiohttp.ClientTimeout(total=8)) as session:
                    while self.pending:
                        async with session.post(url() + "/api/result", json=self.pending[0]) as resp:
                            if resp.status >= 300:
                                raise aiohttp.ClientError(f"Status {resp.status}")
                            answer = await resp.json(content_type=None)
                        sent = self.pending.pop(0)
                        if sent is data:
                            notes = [str(n) for n in (answer or {}).get("notes", [])][:6]
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as err:
                log.info("Bestenliste nicht erreichbar (%s) – %d Ergebnis(se) warten", err, len(self.pending))
            self._save()
            return notes


async def forget(account_id: str) -> None:
    """A deleted account: the Bestenliste removes it from all results."""
    try:
        async with aiohttp.ClientSession(trust_env=False, timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.post(url() + "/api/forget", json={"account": account_id}) as resp:
                if resp.status >= 300:
                    log.warning("Bestenliste hat das Löschen abgelehnt (%s)", resp.status)
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        log.warning("Bestenliste nicht erreichbar – Konto dort nicht gelöscht: %s", err)


async def proxy(request, path: str):
    """Shows the Bestenliste page inside the games (/bestenliste/), read-only."""
    from aiohttp import web
    if request.method != "GET":
        raise web.HTTPMethodNotAllowed(request.method, ["GET"])
    try:
        async with aiohttp.ClientSession(trust_env=False, timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url()}/{path}", params=request.query) as resp:
                body = await resp.read()
                return web.Response(body=body, status=resp.status, content_type=resp.content_type,
                                    headers={"Cache-Control": "no-store"})
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return web.Response(text="<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                                 "<body style='font-family:system-ui;background:#151827;color:#eee;padding:24px'>"
                                 "<h2>🏆 Bestenliste</h2><p>Das Add-on <b>Spieleabend-Bestenliste</b> ist nicht installiert "
                                 "oder läuft gerade nicht.</p><p><a style='color:#9cf' href='../'>Zurück zu den Spielen</a></p>",
                            content_type="text/html", status=503)
