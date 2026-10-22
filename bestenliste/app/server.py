"""Spieleabend-Bestenliste: monthly rankings and achievements for the Spieleabend add-on.

- Spieleabend sends every finished game to POST /api/result (only that add-on is accepted).
- The web page (Home Assistant sidebar, port 8091, and inside the games under /bestenliste/) shows the
  ranking of the month, the leaders per game, achievements, the hall of fame and the last games.
- The ranking starts from zero every month; past months stay in the hall of fame. Achievements are forever.
"""

import asyncio
import json
import logging
import os
import re
import secrets
import time
from datetime import date
from pathlib import Path

import aiohttp
from aiohttp import web

import fabians_master
import ranking
from access import Gate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bestenliste")

DATA = Path(os.environ.get("BESTENLISTE_DATA", "/data"))
RESULTS = DATA / "results.jsonl"
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("BESTENLISTE_PORT", "8091"))
SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor").rstrip("/")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
INGRESS_IP = "172.30.32.2"
MAX_RESULTS = 20000


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPTIONS = load_options()
THEME = os.environ.get("BESTENLISTE_THEME") or OPTIONS.get("theme") or "dark"


# -- storage ----------------------------------------------------------------------------------
class Store:
    def __init__(self) -> None:
        self.results: list[dict] = []
        try:
            for line in RESULTS.read_text().splitlines():
                if line.strip():
                    self.results.append(json.loads(line))
        except (OSError, ValueError) as err:
            if RESULTS.exists():
                log.warning("Ergebnisse teilweise unlesbar: %s", err)
        self.results.sort(key=lambda r: r["ts"])

    def add(self, result: dict) -> None:
        self.results.append(result)
        DATA.mkdir(parents=True, exist_ok=True)
        with RESULTS.open("a") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def rewrite(self) -> None:
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = RESULTS.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self.results))
        tmp.replace(RESULTS)


store: Store


# -- who is calling -----------------------------------------------------------------------------
class Callers:
    """Only the Spieleabend add-on of the same repository may send results (checked via the Supervisor)."""

    def __init__(self) -> None:
        self.ip, self.checked = "", 0.0
        host = os.uname().nodename
        self.slug = (host.split("-", 1)[0] if "-" in host else "local") + "_spieleabend"
        self.trusted = {ip for ip in os.environ.get("BESTENLISTE_TRUSTED_IPS", "").split(",") if ip}

    async def is_spieleabend(self, request: web.Request) -> bool:
        if request.remote in self.trusted:
            return True
        if not SUPERVISOR_TOKEN:
            return False
        if request.remote != self.ip or time.time() - self.checked > 300:
            try:
                async with request.app["http"].get(f"{SUPERVISOR}/addons/{self.slug}/info",
                                                   headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    info = (await resp.json(content_type=None) or {}).get("data") or {}
                self.ip, self.checked = info.get("ip_address") or "", time.time()
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                log.warning("Supervisor nicht erreichbar: %s", err)
                return False
        return bool(self.ip) and request.remote == self.ip


callers = Callers()


def is_admin(request: web.Request) -> bool:
    """Corrections only through Home Assistant (sidebar), never from the home network or the games."""
    if os.environ.get("BESTENLISTE_ADMIN_OPEN") == "1":
        return True
    return request.remote == INGRESS_IP and "X-Ingress-Path" in request.headers


# -- views -------------------------------------------------------------------------------------
def clean_result(data: dict) -> dict:
    kind = str(data.get("kind") or "")[:30]
    players = []
    for p in (data.get("players") or [])[:20]:
        name = " ".join(str(p.get("name") or "").split())[:20]
        if not name or p.get("left"):
            continue          # people who left during the game don't count
        place = p.get("place")
        score = p.get("score")
        account = str(p.get("account") or "")
        players.append({"name": name, "bot": bool(p.get("bot")),
                        "account": account if re.fullmatch(r"[0-9a-f]{4,40}", account) and not p.get("bot") else None,
                        "place": int(place) if isinstance(place, int) and 0 < place <= 20 else None,
                        "score": score if isinstance(score, (int, float)) and abs(score) < 1e9 else None,
                        "won": bool(p.get("won")), "sips": max(0, min(500, int(p.get("sips") or 0)))})
    highlights = [{"name": str(h.get("name") or "")[:20], "what": str(h.get("what") or "")[:20],
                   "account": str(h.get("account") or "")[:40] or None}
                  for h in (data.get("highlights") or [])[:40]]
    return {"id": secrets.token_hex(5), "ts": time.time(), "kind": kind, "title": ranking.TITLES.get(kind, kind),
            "players": players, "highlights": highlights}


def recent_view(r: dict) -> dict:
    return {"id": r["id"], "ts": r["ts"], "title": r["title"], "kind": r["kind"], "counts": ranking.counts(r),
            "players": sorted(({"name": p["name"], "bot": p["bot"], "guest": not p["bot"] and not p.get("account"),
                                "place": p["place"], "won": p["won"], "score": p["score"], "sips": p["sips"],
                                "points": ranking.points(r, p) if p.get("account") else 0} for p in r["players"]),
                              key=lambda p: (p["place"] or 99, p["name"].casefold()))}


def overview(month: str | None, admin: bool) -> dict:
    now = time.time()
    current = ranking.month_of(now)
    month = month if month and len(month) == 7 else current
    results = [r for r in store.results if ranking.counts(r)]
    in_month = [r for r in results if ranking.month_of(r["ts"]) == month]
    players, finished = ranking.replay(store.results, now)
    rows = ranking.standings(in_month)

    games = []
    for kind, title in ranking.TITLES.items():
        rs = [r for r in in_month if r["kind"] == kind]
        if not rs:
            continue
        wins: dict[str, list] = {}
        for r in rs:
            for p in ranking.members(r):
                if p["won"]:
                    wins.setdefault(ranking.member_key(p), [p["name"], 0])[1] += 1
        leaders = sorted(({"name": n, "wins": w} for n, w in wins.values()), key=lambda x: -x["wins"])[:3]
        games.append({"kind": kind, "title": title, "played": len(rs), "leaders": leaders})
    games.sort(key=lambda g: -g["played"])

    today = date.today()
    first_next = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    months = sorted({ranking.month_of(r["ts"]) for r in results} | {current}, reverse=True)
    hall = [{"month": m, "label": ranking.month_label(m), "top": [{"name": r["name"], "points": r["points"], "wins": r["wins"],
                                                                     "place": r["place"]} for r in rows_[:3]]}
            for m, rows_ in sorted(finished.items(), reverse=True) if rows_]
    people = sorted(players.values(), key=lambda s: (-len(s["unlocked"]), s["name"].casefold()))
    shown = [r for r in store.results if ranking.month_of(r["ts"]) == month][-25:][::-1]
    return {
        "month": month, "label": ranking.month_label(month), "current": month == current,
        "reset_days": (first_next - today).days, "months": [{"month": m, "label": ranking.month_label(m)} for m in months],
        "ranking": rows, "games": games, "hall": hall,
        "recent": [recent_view(r) for r in shown],
        "players": [{"name": s["name"], "games": s["games"], "wins": s["wins"], "best_streak": s["best_streak"],
                     "achievements": ranking.achievement_view(s)} for s in people],
        "achievement_count": len(ranking.ACHIEVEMENTS), "admin": admin, "theme": THEME,
    }


# -- routes ------------------------------------------------------------------------------------
routes = web.RouteTableDef()


@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@routes.get("/api/overview")
async def api_overview(request: web.Request) -> web.Response:
    return web.json_response(overview(request.query.get("month"), is_admin(request)), headers={"Cache-Control": "no-store"})


@routes.post("/api/result")
async def api_result(request: web.Request) -> web.Response:
    if not await callers.is_spieleabend(request):
        log.warning("Ergebnis von %s abgelehnt (nicht der Spieleabend)", request.remote)
        return web.json_response({"error": "Nur der Spieleabend darf Ergebnisse melden"}, status=403)
    try:
        data = await request.json()
    except ValueError:
        return web.json_response({"error": "Ungültige Daten"}, status=400)
    result = clean_result(data if isinstance(data, dict) else {})
    if result["kind"] not in ranking.TITLES or not result["players"]:
        return web.json_response({"error": "Unbekanntes Spiel"}, status=400)
    month = ranking.month_of(result["ts"])
    before_players, _ = ranking.replay(store.results)
    before_rows = ranking.standings([r for r in store.results if ranking.counts(r) and ranking.month_of(r["ts"]) == month])
    store.add(result)
    notes = []
    if not ranking.counts(result):
        notes.append("🏆 Bestenliste: Partien mit weniger als zwei Menschen zählen nicht")
    elif not ranking.members(result):
        notes.append("🏆 Bestenliste: Niemand war angemeldet – melde dich an, um Punkte und Achievements zu sammeln")
    else:
        after_players, _ = ranking.replay(store.results)
        for k, state in after_players.items():
            old = before_players.get(k, {}).get("unlocked", {})
            for aid in state["unlocked"]:
                if aid not in old:
                    icon, title = ranking.title_of(aid)
                    notes.append(f"{icon} {state['name']} schaltet „{title}“ frei")
        rows = ranking.standings([r for r in store.results if ranking.counts(r) and ranking.month_of(r["ts"]) == month])
        old_leader = before_rows[0]["key"] if before_rows else None
        if rows and rows[0]["key"] != old_leader and rows[0]["place"] == 1 and (len(rows) == 1 or rows[1]["place"] != 1):
            notes.append(f"👑 {rows[0]['name']} führt jetzt die Bestenliste im {ranking.MONTHS[int(month[5:]) - 1]} an")
    log.info("Partie %s: %s", result["title"], ", ".join(p["name"] + (" 🏆" if p["won"] else "") for p in result["players"]))
    return web.json_response({"ok": True, "notes": notes[:6]})


@routes.post("/api/admin/delete")
async def admin_delete(request: web.Request) -> web.Response:
    if not is_admin(request):
        return web.json_response({"error": "Nur über Home Assistant"}, status=403)
    rid = str((await request.json()).get("id") or "")
    before = len(store.results)
    store.results = [r for r in store.results if r["id"] != rid]
    if len(store.results) == before:
        return web.json_response({"error": "Partie nicht gefunden"}, status=404)
    store.rewrite()
    return web.json_response({"ok": True})


@routes.post("/api/forget")
async def api_forget(request: web.Request) -> web.Response:
    """A deleted Spieleabend account: its results stay for the others, but without the account."""
    if not await callers.is_spieleabend(request):
        return web.json_response({"error": "Nur der Spieleabend"}, status=403)
    account = str((await request.json()).get("account") or "")
    changed = 0
    for r in store.results:
        for p in r["players"]:
            if p.get("account") == account:
                p.update(account=None, name="Gelöschtes Konto")
                changed += 1
        for h in r.get("highlights") or []:
            if h.get("account") == account:
                h.update(account=None, name="")
    if changed:
        store.rewrite()
    log.info("Konto aus %d Ergebnissen entfernt", changed)
    return web.json_response({"ok": True})


async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession(trust_env=False)
    log.info("Bestenliste bereit auf Port %s – %d Partien gespeichert", PORT, len(store.results))


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()


def main() -> None:
    global store
    store = Store()
    app = web.Application(client_max_size=256 * 1024)
    # Same code as the Spieleabend, from Fabians-HA-Master; without one, the internet is refused.
    code = (os.environ["BESTENLISTE_ACCESS_CODE"] if "BESTENLISTE_ACCESS_CODE" in os.environ
            else fabians_master.keys(wait=90).get("games_code"))
    Gate("Bestenliste", code, THEME, "bestenliste_zugang").setup(app)
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    # IPv4 only: callers are checked by their IPv4 address (the add-on network also has IPv6).
    web.run_app(app, host="0.0.0.0", port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
