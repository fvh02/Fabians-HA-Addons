"""Fabians-HA-Himmel: what is to be seen in the sky above home.

ISS passes (orbit data from CelesTrak, computed here), moon phases, meteor showers, eclipses and the
cloud forecast for the coming nights (Open-Meteo). The location is Home Assistant's home. In the
afternoon the add-on reports the evening's highlights when the sky will be clear, and reminds a few
minutes before a bright ISS pass. Only Home Assistant (Ingress) and Fabians-HA-Master may call it.
"""

import asyncio
import json
import logging
import os
import socket
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from aiohttp import web

import astro
import fabians_master

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("himmel")

DATA = Path(os.environ.get("HIMMEL_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("HIMMEL_PORT", "8104"))
INGRESS_IP = os.environ.get("HIMMEL_INGRESS_IP", "172.30.32.2")
SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor").rstrip("/")
TLE_URL = os.environ.get("HIMMEL_TLE_URL", "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE")
METEO = os.environ.get("HIMMEL_METEO", "https://api.open-meteo.com/v1/forecast")


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPT = load_options()
DAILY_HOUR = int(OPT.get("meldung_uhrzeit", 17))
ISS_REMINDER = OPT.get("iss_erinnerung", True) is not False
MIN_ELEV = int(OPT.get("min_hoehe", 30))
MAX_CLOUDS = int(OPT.get("wolken_max", 50))
REMIND_FROM, REMIND_TO = int(OPT.get("erinnerung_von", 6)), int(OPT.get("erinnerung_bis", 23))
routes = web.RouteTableDef()
cache: dict = {}


class Fail(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def local_label(t: datetime) -> str:
    return f"{TAGE[t.weekday()]} {t:%d.%m. %H:%M}"


def load_state() -> dict:
    try:
        return json.loads((DATA / "himmel.json").read_text())
    except (OSError, ValueError):
        return {}


def save_state(s: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "himmel.tmp").write_text(json.dumps(s))
    (DATA / "himmel.tmp").replace(DATA / "himmel.json")


state = load_state()


# -- sources ------------------------------------------------------------------------------------------------
async def home(session: aiohttp.ClientSession) -> dict:
    """Home location and time zone from Home Assistant (or HIMMEL_LAT/LON for tests)."""
    if "home" in cache:
        return cache["home"]
    if os.environ.get("HIMMEL_LAT"):
        h = {"lat": float(os.environ["HIMMEL_LAT"]), "lon": float(os.environ["HIMMEL_LON"]), "hoehe": 50,
             "zeitzone": os.environ.get("HIMMEL_TZ", "Europe/Berlin"), "name": "Zuhause"}
    else:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        try:
            async with session.get(f"{SUPERVISOR}/core/api/config", headers={"Authorization": f"Bearer {token}"},
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                c = await r.json(content_type=None)
            h = {"lat": float(c["latitude"]), "lon": float(c["longitude"]), "hoehe": float(c.get("elevation") or 0),
                 "zeitzone": c.get("time_zone") or "Europe/Berlin", "name": c.get("location_name") or "Zuhause"}
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError) as err:
            raise Fail(503, f"Standort aus Home Assistant nicht lesbar ({err.__class__.__name__})")
    cache["home"] = h
    return h


async def tle(session: aiohttp.ClientSession) -> tuple[str, str]:
    """ISS orbit data, fetched at most every 12 hours (kept in /data for when CelesTrak is down)."""
    saved = state.get("tle")
    if saved and time.time() - saved["at"] < 12 * 3600:
        return saved["l1"], saved["l2"]
    try:
        async with session.get(TLE_URL, timeout=aiohttp.ClientTimeout(total=20), headers={"User-Agent": "Fabians-HA-Himmel/1.0"}) as r:
            lines = [l.strip() for l in (await r.text()).splitlines() if l.strip()]
        l1 = next(l for l in lines if l.startswith("1 "))
        l2 = next(l for l in lines if l.startswith("2 "))
        state["tle"] = {"l1": l1, "l2": l2, "at": time.time()}
        save_state(state)
        return l1, l2
    except (aiohttp.ClientError, asyncio.TimeoutError, StopIteration) as err:
        if saved:
            log.info("CelesTrak nicht erreichbar (%s) – nehme die gespeicherten Bahndaten", err.__class__.__name__)
            return saved["l1"], saved["l2"]
        raise Fail(503, "Bahndaten der ISS nicht verfügbar (CelesTrak nicht erreichbar)")


async def clouds(session: aiohttp.ClientSession, h: dict) -> dict[str, int]:
    """Cloud cover per hour (local ISO hour → %) for the next 4 days, cached for an hour."""
    hit = cache.get("clouds")
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    params = {"latitude": h["lat"], "longitude": h["lon"], "hourly": "cloud_cover", "forecast_days": 4, "timezone": h["zeitzone"]}
    try:
        async with session.get(METEO, params=params, timeout=aiohttp.ClientTimeout(total=20)) as r:
            data = (await r.json(content_type=None))["hourly"]
        result = {t[:13]: int(c) for t, c in zip(data["time"], data["cloud_cover"]) if c is not None}
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError) as err:
        log.info("Wetter nicht erreichbar: %s", err)
        result = {}
    cache["clouds"] = (time.time(), result)
    return result


# -- the sky --------------------------------------------------------------------------------------------------
async def overview(session: aiohttp.ClientSession) -> dict:
    h = await home(session)
    tz = ZoneInfo(h["zeitzone"])
    now = datetime.now(timezone.utc)
    key = int(now.timestamp() // 900)       # recomputed every 15 minutes
    if cache.get("overview", (None,))[0] == key:
        return cache["overview"][1]
    l1, l2 = await tle(session)
    raw = await asyncio.to_thread(astro.passes, l1, l2, h["lat"], h["lon"], h["hoehe"], now - timedelta(minutes=10), 10, 10)
    cloud = await clouds(session, h)
    passes = []
    for p in raw:
        local = datetime.fromisoformat(p["beginn"]).astimezone(tz)
        passes.append({**p, "lokal": local_label(local), "tag": local.date().isoformat(),
                       "wolken": cloud.get(local.strftime("%Y-%m-%dT%H"))})
    nights = []
    today = now.astimezone(tz).date()
    for i in range(3):
        d = today + timedelta(days=i)
        span = await asyncio.to_thread(astro.dark_hours, d, h["lat"], h["lon"], tz)
        if not span:
            nights.append({"datum": d.isoformat(), "dunkel": None, "wolken": None})
            continue
        hours = []
        t = span[0].replace(minute=0)
        while t < span[1]:
            c = cloud.get(t.strftime("%Y-%m-%dT%H"))
            if c is not None:
                hours.append(c)
            t += timedelta(hours=1)
        nights.append({"datum": d.isoformat(), "dunkel": f"{span[0]:%H:%M}–{span[1]:%H:%M}",
                       "wolken": round(sum(hours) / len(hours)) if hours else None})
    result = {
        "ort": h["name"], "jetzt": now.astimezone(tz).strftime("%d.%m.%Y %H:%M"),
        "mond": astro.moon_now(now),
        "mondphasen": [{**m, "lokal": local_label(datetime.fromisoformat(m["zeit"]).astimezone(tz))}
                       for m in astro.moon_phases(now, 4)],
        "iss": [p for p in passes if p["sichtbar"]][:15],
        "iss_alle": len(passes),
        "naechte": nights,
        "sternschnuppen": [{**s, "mond": astro.moon_now(datetime.fromisoformat(s["datum"] + "T22:00:00+00:00"))["beleuchtet"]}
                           for s in astro.showers_between(today, today + timedelta(days=90))],
        "finsternisse": astro.eclipses_between(today, today + timedelta(days=5 * 366)),
        "einstellungen": {"min_hoehe": MIN_ELEV, "wolken_max": MAX_CLOUDS},
    }
    cache["overview"] = (key, result)
    return result


def tonight(o: dict, tz: ZoneInfo, now: datetime) -> dict:
    """What is worth looking at tonight (local evening until next morning)."""
    today = now.astimezone(tz).date()
    morning = datetime.combine(today + timedelta(days=1), datetime.min.time(), tz) + timedelta(hours=7)
    iss = [p for p in o["iss"] if p["max_hoehe"] >= MIN_ELEV and now <= datetime.fromisoformat(p["beginn"]) <= morning]
    showers = [s for s in o["sternschnuppen"] if date.fromisoformat(s["datum"]) in (today, today + timedelta(days=1))]
    eclipses = [e for e in o["finsternisse"] if date.fromisoformat(e["datum"]) in (today, today + timedelta(days=1))]
    night = next((n for n in o["naechte"] if n["datum"] == today.isoformat()), None)
    full_or_new = [m for m in o["mondphasen"] if datetime.fromisoformat(m["zeit"]).astimezone(tz).date() == today]
    return {"iss": iss, "sternschnuppen": showers, "finsternisse": eclipses, "nacht": night, "mondphase_heute": full_or_new}


def tonight_text(t: dict, o: dict) -> str | None:
    lines = []
    for e in t["finsternisse"]:
        lines.append(f"🌘 {e['name']} am {date.fromisoformat(e['datum']):%d.%m.}: {e['sichtbarkeit']}")
    for s in t["sternschnuppen"]:
        moon = "Mond stört kaum" if s["mond"] < 35 else f"Mond {s['mond']} % hell"
        lines.append(f"🌠 {s['name']}: bis zu {s['pro_stunde']} Sternschnuppen pro Stunde – {s['tipp']} ({moon})")
    for p in t["iss"]:
        lines.append(f"🛰️ ISS {p['lokal'].split(' ', 2)[2]} Uhr von {p['von']} nach {p['nach']}, bis {p['max_hoehe']}° hoch, "
                     f"{p['dauer_s'] // 60} Min.")
    if not lines:
        return None
    night = t["nacht"] or {}
    clouds = night.get("wolken")
    if clouds is not None and clouds > MAX_CLOUDS and not t["finsternisse"]:
        return None                     # nothing to see behind the clouds
    weather = f"☁️ Bewölkung nachts etwa {clouds} %" if clouds is not None else ""
    moon = f"🌙 Mond {o['mond']['beleuchtet']} % ({o['mond']['phase']})"
    return "✨ Heute am Himmel:\n" + "\n".join(lines + [x for x in (weather, moon) if x])


# -- background ----------------------------------------------------------------------------------------------------
async def notifier(app: web.Application) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            await notify_once(app)
        except Fail as err:
            log.info("Prüfung: %s", err)
        except Exception:
            log.exception("Prüfung fehlgeschlagen")
        await asyncio.sleep(120)


async def notify_once(app: web.Application) -> None:
    session = app["http"]
    h = await home(session)
    tz = ZoneInfo(h["zeitzone"])
    now = datetime.now(timezone.utc)
    local = now.astimezone(tz)
    o = await overview(session)
    if local.hour == DAILY_HOUR and state.get("taeglich") != local.date().isoformat():
        state["taeglich"] = local.date().isoformat()
        text = tonight_text(tonight(o, tz, now), o)
        if text and await asyncio.to_thread(fabians_master.notify, text):
            log.info("Abendmeldung gesendet")
        save_state(state)
    if ISS_REMINDER and REMIND_FROM <= local.hour < REMIND_TO:
        told = state.setdefault("iss_erinnert", [])
        for p in o["iss"]:
            start = datetime.fromisoformat(p["beginn"])
            if p["max_hoehe"] < MIN_ELEV or p["beginn"] in told or not (timedelta(0) < start - now <= timedelta(minutes=12)):
                continue
            if p.get("wolken") is not None and p["wolken"] > MAX_CLOUDS:
                continue
            minutes = max(1, int((start - now).total_seconds() // 60))
            text = (f"🛰️ In {minutes} Min. fliegt die ISS über dich: ab {start.astimezone(tz):%H:%M} Uhr von {p['von']}, "
                    f"höchster Punkt {p['max_hoehe']}° im {p['richtung_max']}, verschwindet im {p['nach']}.")
            if await asyncio.to_thread(fabians_master.notify, text):
                told.append(p["beginn"])
                state["iss_erinnert"] = told[-50:]
                save_state(state)


# -- access ------------------------------------------------------------------------------------------------------------
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
    if os.environ.get("HIMMEL_OPEN") != "1" and request.remote not in (INGRESS_IP, master_ip()):
        return web.json_response({"error": "Nur über Home Assistant oder den Assistenten"}, status=403)
    try:
        return await handler(request)
    except Fail as err:
        return web.json_response({"error": str(err)}, status=err.status)


# -- API ----------------------------------------------------------------------------------------------------------------
@routes.get("/")
async def index_page(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@routes.get("/api/uebersicht")
async def api_overview(request: web.Request) -> web.Response:
    return web.json_response(await overview(request.app["http"]))


@routes.get("/api/heute")
async def api_tonight(request: web.Request) -> web.Response:
    session = request.app["http"]
    h = await home(session)
    o = await overview(session)
    t = tonight(o, ZoneInfo(h["zeitzone"]), datetime.now(timezone.utc))
    return web.json_response({**t, "mond": o["mond"], "text": tonight_text(t, o) or "Heute Nacht nichts Besonderes am Himmel."})


async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession(trust_env=True)
    app["task"] = asyncio.create_task(notifier(app))
    log.info("Himmel bereit auf Port %s – Abendmeldung um %d Uhr, ISS-Erinnerung %s (ab %d°, höchstens %d %% Wolken)",
             PORT, DAILY_HOUR, "an" if ISS_REMINDER else "aus", MIN_ELEV, MAX_CLOUDS)


async def on_cleanup(app: web.Application) -> None:
    app["task"].cancel()
    await app["http"].close()


def main() -> None:
    app = web.Application(middlewares=[guard])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app, port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
