"""Fabians-HA-Serien: a calendar of the series you follow.

Series data comes from TVmaze (free, no key; CC BY-SA). Every 30 minutes the add-on looks at the
episodes of the followed series and sends an iMessage through Fabians-HA-Master when new episodes
are out today or a new season gets a start date. Only Home Assistant (Ingress) and the master (the
assistant's bridge) may call it.
"""

import asyncio
import json
import logging
import os
import re
import socket
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

import aiohttp
from aiohttp import web

import fabians_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("serien")

DATA = Path(os.environ.get("SERIEN_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("SERIEN_PORT", "8103"))
INGRESS_IP = os.environ.get("SERIEN_INGRESS_IP", "172.30.32.2")
TVMAZE = os.environ.get("SERIEN_TVMAZE", "https://api.tvmaze.com").rstrip("/")
REFRESH = 6 * 3600          # episode lists are fetched again after this long
CHECK = int(os.environ.get("SERIEN_CHECK", "1800"))
MAX_SHOWS = 200


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPTIONS = load_options()
NOTIFY = OPTIONS.get("meldungen", True) is not False
QUIET_FROM = int(OPTIONS.get("ruhe_ab", 22))
QUIET_TO = int(OPTIONS.get("ruhe_bis", 8))
routes = web.RouteTableDef()


class Fail(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# -- state ------------------------------------------------------------------------------------------
class State:
    """Followed series with their episodes, kept in one JSON file."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("shows", {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False))
        tmp.replace(self.path)

    @property
    def shows(self) -> dict:
        return self.data["shows"]


state = State(DATA / "serien.json")


# -- TVmaze ---------------------------------------------------------------------------------------------
async def tvmaze(session: aiohttp.ClientSession, path: str, params: dict | None = None):
    for attempt in range(3):
        try:
            async with session.get(TVMAZE + path, params=params, timeout=aiohttp.ClientTimeout(total=20),
                                   headers={"User-Agent": "Fabians-HA-Serien/1.0"}) as r:
                if r.status == 429:         # rate limit: 20 calls per 10 seconds
                    await asyncio.sleep(3 + 3 * attempt)
                    continue
                if r.status == 404:
                    raise Fail(404, "Diese Serie gibt es bei TVmaze nicht")
                if r.status >= 400:
                    raise Fail(502, f"TVmaze antwortet mit {r.status}")
                return await r.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            if attempt == 2:
                raise Fail(503, f"TVmaze nicht erreichbar ({err.__class__.__name__})")
            await asyncio.sleep(2)
    raise Fail(503, "TVmaze ist gerade überlastet – bitte gleich noch einmal")


def clean_html(text: str | None, limit: int = 400) -> str:
    text = unescape(re.sub(r"<[^>]+>", "", text or "")).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def channel(show: dict) -> str:
    return ((show.get("webChannel") or {}).get("name") or (show.get("network") or {}).get("name") or "").strip()


def show_info(show: dict) -> dict:
    return {"id": show["id"], "name": show.get("name") or "?", "kanal": channel(show), "status": show.get("status") or "",
            "start": show.get("premiered") or "", "sprache": show.get("language") or "",
            "genres": show.get("genres") or [], "bild": (show.get("image") or {}).get("medium") or "",
            "beschreibung": clean_html(show.get("summary")), "link": show.get("url") or ""}


def episode_info(ep: dict) -> dict:
    return {"id": ep["id"], "staffel": ep.get("season"), "folge": ep.get("number"), "titel": ep.get("name") or "",
            "datum": ep.get("airdate") or "", "zeit": ep.get("airstamp") or "", "laenge": ep.get("runtime")}


def aired_at(ep: dict) -> datetime | None:
    stamp = ep.get("zeit")
    if stamp:
        try:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            pass
    if ep.get("datum"):
        try:
            return datetime.fromisoformat(ep["datum"]).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


async def refresh_show(session: aiohttp.ClientSession, show_id: str, force: bool = False) -> None:
    entry = state.shows[show_id]
    if not force and time.time() - entry.get("geladen", 0) < REFRESH:
        return
    show = await tvmaze(session, f"/shows/{show_id}")
    episodes = await tvmaze(session, f"/shows/{show_id}/episodes", {"specials": 0})
    entry.update(show_info(show))
    entry["folgen"] = [episode_info(e) for e in episodes if e.get("season") is not None]
    entry["geladen"] = time.time()


def code(ep: dict) -> str:
    return f"S{ep['staffel'] or 0:02d}E{ep['folge'] or 0:02d}"


def german_date(d: datetime) -> str:
    days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    local = d.astimezone()
    return f"{days[local.weekday()]} {local:%d.%m.%Y}"


# -- what is new ------------------------------------------------------------------------------------------
def due_messages(now: datetime) -> list[tuple[str, str, list[int], int | None]]:
    """(show id, text, episode ids to mark, announced season) for everything to report now."""
    out = []
    for sid, entry in state.shows.items():
        if not entry.get("melden", True):
            continue
        told = set(entry.get("gemeldet", []))
        fresh = [e for e in entry.get("folgen", []) if e["id"] not in told and (t := aired_at(e)) and now - timedelta(hours=36) <= t <= now]
        if fresh:
            fresh.sort(key=lambda e: (e["staffel"], e["folge"]))
            where = f" ({entry['kanal']})" if entry.get("kanal") else ""
            if len(fresh) == 1:
                e = fresh[0]
                title = f" „{e['titel']}“" if e["titel"] and not re.fullmatch(r"Episode \d+", e["titel"]) else ""
                text = f"📺 Neu: {entry['name']} – {code(e)}{title}{where}"
            else:
                seasons = sorted({e["staffel"] for e in fresh})
                text = (f"📺 Neu: {entry['name']} – {len(fresh)} Folgen "
                        f"({'Staffel ' + str(seasons[0]) if len(seasons) == 1 else code(fresh[0]) + '–' + code(fresh[-1])}){where}")
            out.append((sid, text, [e["id"] for e in fresh], None))
        # a new season with a date: announced once
        known = entry.get("staffel_bekannt", 0)
        future = [e for e in entry.get("folgen", []) if (t := aired_at(e)) and t > now and (e["staffel"] or 0) > known]
        if future:
            first = min(future, key=lambda e: (e["staffel"], e["folge"]))
            if first["folge"] == 1:
                when = aired_at(first)
                where = f" bei {entry['kanal']}" if entry.get("kanal") else ""
                out.append((sid, f"📅 {entry['name']}: Staffel {first['staffel']} startet am {german_date(when)}{where}.", [], first["staffel"]))
    return out


def quiet(now: datetime) -> bool:
    hour = now.astimezone().hour
    return (QUIET_FROM <= hour or hour < QUIET_TO) if QUIET_FROM > QUIET_TO else QUIET_FROM <= hour < QUIET_TO


async def check(app: web.Application, send: bool = True) -> list[str]:
    session = app["http"]
    for sid in list(state.shows):
        try:
            await refresh_show(session, sid)
        except Fail as err:
            log.warning("%s: %s", state.shows[sid].get("name", sid), err)
    now = datetime.now(timezone.utc)
    sent = []
    for sid, text, episode_ids, season in due_messages(now):
        if send and NOTIFY and not quiet(now):
            if not await asyncio.to_thread(fabians_master.notify, text):
                continue
            sent.append(text)
        elif send and NOTIFY:
            continue            # quiet hours: sent in the morning
        entry = state.shows[sid]
        entry["gemeldet"] = (entry.get("gemeldet", []) + episode_ids)[-400:]
        if season:
            entry["staffel_bekannt"] = max(entry.get("staffel_bekannt", 0), season)
    state.save()
    return sent


async def checker(app: web.Application) -> None:
    await asyncio.sleep(20)
    while True:
        try:
            sent = await check(app)
            if sent:
                log.info("Gemeldet: %s", " | ".join(sent))
        except Exception:       # never let the loop die
            log.exception("Prüfung fehlgeschlagen")
        await asyncio.sleep(CHECK)


def start_baseline(entry: dict) -> None:
    """When a series is followed, everything already out counts as known – only new things are reported."""
    now = datetime.now(timezone.utc)
    entry["gemeldet"] = [e["id"] for e in entry.get("folgen", []) if (t := aired_at(e)) and t <= now][-400:]
    current = [e["staffel"] or 0 for e in entry.get("folgen", []) if (t := aired_at(e)) and t <= now]
    planned = [e["staffel"] or 0 for e in entry.get("folgen", []) if (t := aired_at(e)) and t > now and e["folge"] == 1]
    # an already announced next season is reported once right away (that's what you want to know)
    entry["staffel_bekannt"] = max(current or [0])
    if not planned:
        entry["staffel_bekannt"] = max([entry["staffel_bekannt"]] + [e["staffel"] or 0 for e in entry.get("folgen", [])])


# -- access -------------------------------------------------------------------------------------------------
_master = {"ip": "", "at": 0.0}


def master_ip() -> str:
    if time.time() - _master["at"] > 300:
        host = socket.gethostname()
        try:
            _master["ip"] = socket.gethostbyname((host.split("-", 1)[0] if "-" in host else "local") + "-master")
        except OSError:
            _master["ip"] = ""
        _master["at"] = time.time()
    return _master["ip"]


@web.middleware
async def guard(request: web.Request, handler):
    if os.environ.get("SERIEN_OPEN") != "1" and request.remote not in (INGRESS_IP, master_ip()):
        return web.json_response({"error": "Nur über Home Assistant oder den Assistenten"}, status=403)
    try:
        return await handler(request)
    except Fail as err:
        return web.json_response({"error": str(err)}, status=err.status)


# -- views ----------------------------------------------------------------------------------------------------
def next_episode(entry: dict, now: datetime) -> dict | None:
    future = [e for e in entry.get("folgen", []) if (t := aired_at(e)) and t > now]
    return min(future, key=lambda e: aired_at(e)) if future else None


def last_episode(entry: dict, now: datetime) -> dict | None:
    past = [e for e in entry.get("folgen", []) if (t := aired_at(e)) and t <= now]
    return max(past, key=lambda e: aired_at(e)) if past else None


def view(entry: dict, now: datetime) -> dict:
    nxt, last = next_episode(entry, now), last_episode(entry, now)
    out = {k: entry.get(k) for k in ("id", "name", "kanal", "status", "bild", "beschreibung", "link", "genres")}
    out["melden"] = entry.get("melden", True)
    status = {"Running": "läuft", "Ended": "beendet", "To Be Determined": "unklar", "In Development": "in Entwicklung"}
    out["status"] = status.get(entry.get("status"), entry.get("status") or "")
    if nxt:
        out["naechste"] = {**nxt, "code": code(nxt), "am": german_date(aired_at(nxt)), "in_tagen": (aired_at(nxt) - now).days}
    if last:
        out["letzte"] = {**last, "code": code(last), "am": german_date(aired_at(last))}
    return out


def find_followed(ref: str) -> str:
    ref = str(ref).strip()
    if ref in state.shows:
        return ref
    low = ref.casefold()
    hits = [sid for sid, e in state.shows.items() if low in e.get("name", "").casefold()]
    if len(hits) == 1:
        return hits[0]
    raise Fail(404, f"„{ref}“ ist nicht in deiner Liste" if not hits else f"„{ref}“ passt auf mehrere: "
               + ", ".join(state.shows[h]["name"] for h in hits))


# -- API --------------------------------------------------------------------------------------------------------
@routes.get("/")
async def index_page(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@routes.get("/api/suche")
async def api_search(request: web.Request) -> web.Response:
    q = " ".join(request.query.get("q", "").split())[:80]
    if not q:
        raise Fail(400, "Wonach suchen?")
    hits = await tvmaze(request.app["http"], "/search/shows", {"q": q})
    return web.json_response({"treffer": [{**show_info(h["show"]), "gefolgt": str(h["show"]["id"]) in state.shows}
                                          for h in hits[:10]]})


@routes.get("/api/serien")
async def api_followed(_: web.Request) -> web.Response:
    now = datetime.now(timezone.utc)
    shows = sorted((view(e, now) for e in state.shows.values()),
                   key=lambda s: (s.get("naechste") is None, (s.get("naechste") or {}).get("zeit") or "", s["name"]))
    return web.json_response({"serien": shows})


@routes.get("/api/demnaechst")
async def api_upcoming(request: web.Request) -> web.Response:
    days = max(1, min(120, int(request.query.get("tage", 30))))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=int(request.query.get("zurueck", 2)))
    items = []
    for entry in state.shows.values():
        for e in entry.get("folgen", []):
            t = aired_at(e)
            if t and since <= t <= now + timedelta(days=days):
                items.append({**e, "code": code(e), "serie": entry["name"], "serie_id": entry["id"], "kanal": entry.get("kanal", ""),
                              "am": german_date(t), "tag": t.astimezone().date().isoformat(), "neu": t <= now})
    items.sort(key=lambda i: i["zeit"] or i["datum"])
    return web.json_response({"folgen": items})


@routes.post("/api/folgen")
async def api_follow(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except ValueError:
        raise Fail(400, "Ungültige Anfrage")
    session = request.app["http"]
    ref = str(data.get("id") or "").strip()
    if not ref and data.get("name"):
        hits = await tvmaze(session, "/search/shows", {"q": str(data["name"])[:80]})
        if not hits:
            raise Fail(404, f"Keine Serie „{data['name']}“ gefunden")
        ref = str(hits[0]["show"]["id"])
    if not ref.isdigit():
        raise Fail(400, "id oder name fehlt")
    if ref not in state.shows:
        if len(state.shows) >= MAX_SHOWS:
            raise Fail(400, f"Höchstens {MAX_SHOWS} Serien")
        state.shows[ref] = {"id": int(ref), "melden": True, "seit": time.time()}
        try:
            await refresh_show(session, ref, force=True)
        except Fail:
            state.shows.pop(ref, None)
            raise
        start_baseline(state.shows[ref])
        state.save()
        log.info("Folge jetzt: %s", state.shows[ref]["name"])
    return web.json_response(view(state.shows[ref], datetime.now(timezone.utc)))


@routes.delete("/api/folgen/{ref}")
async def api_unfollow(request: web.Request) -> web.Response:
    sid = find_followed(request.match_info["ref"])
    name = state.shows.pop(sid)["name"]
    state.save()
    return web.json_response({"entfernt": name})


@routes.patch("/api/folgen/{ref}")
async def api_settings(request: web.Request) -> web.Response:
    sid = find_followed(request.match_info["ref"])
    data = await request.json()
    if "melden" in data:
        state.shows[sid]["melden"] = bool(data["melden"])
        state.save()
    return web.json_response(view(state.shows[sid], datetime.now(timezone.utc)))


@routes.post("/api/pruefen")
async def api_check(request: web.Request) -> web.Response:
    for sid in list(state.shows):
        state.shows[sid]["geladen"] = 0
    sent = await check(request.app)
    return web.json_response({"gemeldet": sent})


# -- start --------------------------------------------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession(trust_env=True)
    app["checker"] = asyncio.create_task(checker(app))
    log.info("Serien-Kalender bereit auf Port %s – %d Serien, Meldungen %s", PORT, len(state.shows),
             f"an (Ruhe {QUIET_FROM}–{QUIET_TO} Uhr)" if NOTIFY else "aus")


async def on_cleanup(app: web.Application) -> None:
    app["checker"].cancel()
    await app["http"].close()


def main() -> None:
    app = web.Application(middlewares=[guard])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    # IPv4 only: callers are checked by their IPv4 address (the add-on network also has IPv6).
    web.run_app(app, host="0.0.0.0", port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
