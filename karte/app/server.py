"""Fabians-HA-Karte: a map of the places you ate at, filled in by the assistant.

The assistant reads the menu photo and what was ordered, takes the location from the Home Assistant app
and sends it here. The add-on finds the restaurant in OpenStreetMap, saves menu, order and photos, and
then lets Claude (through Fabians-HA-Master, with web search) look it up online and compare the sources.
The page in the Home Assistant sidebar shows everything on a map.

Only Home Assistant (Ingress) and Fabians-HA-Master (the assistant's bridge) may call it.
"""

import asyncio
import io
import json
import logging
import os
import socket
import time
import uuid
from datetime import datetime
from pathlib import Path

import aiohttp
from aiohttp import web
from PIL import Image, ImageOps, UnidentifiedImageError

import abgleich
import fabians_master
import geo
import oeffnung
from store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("karte")

DATA = Path(os.environ.get("KARTE_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PHOTOS = DATA / "fotos"
PORT = int(os.environ.get("KARTE_PORT", "8102"))
INGRESS_IP = os.environ.get("KARTE_INGRESS_IP", "172.30.32.2")
MAX_PHOTO = 10 * 1024 * 1024
MATCH_RADIUS = 150      # m around the location in which the restaurant is looked for
RECHECK_AFTER = 30 * 86400


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPTIONS = load_options()
# The tracker for the location: a Find My device (iCloud integration) or a person; empty = automatic.
DEVICE = str(os.environ.get("KARTE_GERAET") or OPTIONS.get("geraet") or OPTIONS.get("person") or "").strip()
# The Apple ID (from the master) names the account when a fresh Find My position is requested.
APPLE_ID = (os.environ["KARTE_APPLE_ID"] if "KARTE_APPLE_ID" in os.environ
            else fabians_master.keys(wait=60).get("icloud_apple_id", ""))
store = Store(DATA / "karte.sqlite3")
routes = web.RouteTableDef()
checking: set[int] = set()


class Fail(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# -- access: Home Assistant and the master only ------------------------------------------------
_master_ip = {"ip": "", "at": 0.0}


def master_ip() -> str:
    if time.time() - _master_ip["at"] > 300:
        host = socket.gethostname()
        name = (host.split("-", 1)[0] if "-" in host else "local") + "-master"
        try:
            _master_ip["ip"] = socket.gethostbyname(name)
        except OSError:
            _master_ip["ip"] = ""
        _master_ip["at"] = time.time()
    return _master_ip["ip"]


@web.middleware
async def guard(request: web.Request, handler):
    if os.environ.get("KARTE_OPEN") != "1" and request.remote not in (INGRESS_IP, master_ip()):
        return web.json_response({"error": "Nur über Home Assistant oder den Assistenten"}, status=403)
    try:
        return await handler(request)
    except Fail as err:
        return web.json_response({"error": str(err)}, status=err.status)


async def body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise Fail(400, "Ungültige Anfrage")
    if not isinstance(data, dict):
        raise Fail(400, "Ungültige Anfrage")
    return data


def text(value, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


def price(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        p = float(str(value).replace("€", "").replace(",", ".").strip())
    except ValueError:
        return None
    return round(p, 2) if 0 <= p < 10000 else None


def rating(value) -> float | None:
    try:
        r = float(value)
    except (TypeError, ValueError):
        return None
    return max(1.0, min(5.0, r))


# -- views ---------------------------------------------------------------------------------------
def summary(p: dict) -> dict:
    online = p.get("online") or {}
    return {"id": p["id"], "name": p["name"], "lat": p["lat"], "lon": p["lon"], "address": p["address"],
            "kind": p["kind"], "cuisine": p["cuisine"] or online.get("kueche", ""), "visits": p.get("visits", 0),
            "last_visit": p.get("last_visit"), "rating": round(p["rating"], 1) if p.get("rating") else None,
            "online_rating": online.get("bewertung") or None, "price_level": online.get("preisniveau", ""),
            "check": p["check_state"], "differences": len(online.get("abweichungen") or [])}


def detail(place_id: int) -> dict:
    p = store.place(place_id)
    if not p:
        raise Fail(404, "Diesen Ort gibt es nicht (mehr)")
    visits = store.visits(place_id)
    full = {**summary({**p, "visits": len(visits), "last_visit": visits[0]["at"] if visits else None,
                       "rating": (sum(v["rating"] for v in visits if v["rating"]) / max(1, sum(1 for v in visits if v["rating"])))
                       if any(v["rating"] for v in visits) else None}),
            "note": p["note"], "from_menu": p["from_menu"], "osm": p["osm"], "online": p["online"],
            "checked_at": p["checked_at"], "visit_list": visits, "dishes": store.dishes(place_id),
            "photos": store.photos(place_id)}
    return full


# -- background: online research ----------------------------------------------------------------
async def check(place_id: int, notify: bool) -> None:
    if place_id in checking:
        return
    checking.add(place_id)
    store.update_place(place_id, check_state="läuft")
    try:
        place = store.place(place_id)
        result = await abgleich.research(place, store.dishes(place_id))
    except (fabians_master.MasterError, ValueError) as err:
        log.warning("Abgleich %s fehlgeschlagen: %s", place_id, err)
        store.update_place(place_id, check_state=f"Fehler: {str(err)[:200]}")
        return
    finally:
        checking.discard(place_id)
    fields = {"online": result, "checked_at": time.time(), "check_state": "fertig"}
    place = store.place(place_id)
    if not place["address"] and result.get("adresse"):
        fields["address"] = text(result["adresse"])
    if not place["cuisine"] and result.get("kueche"):
        fields["cuisine"] = text(result["kueche"], 60)
    store.update_place(place_id, **fields)
    log.info("Abgleich %s (%s) fertig, %d Abweichung(en)", place_id, place["name"], len(result.get("abweichungen") or []))
    if notify:
        lines = [f"📍 {place['name']} ist auf deiner Karte."]
        info = [x for x in (result.get("kueche"), result.get("preisniveau"),
                            f"{result['bewertung']:.1f}★ ({result.get('bewertung_quelle') or 'online'})" if result.get("bewertung") else "")
                if x]
        if info:
            lines.append(" · ".join(info))
        if result.get("oeffnungszeiten"):
            lines.append(f"🕒 {result['oeffnungszeiten']}")
        if result.get("dauerhaft_geschlossen"):
            lines.append("⚠️ Laut Internet dauerhaft geschlossen.")
        for diff in (result.get("abweichungen") or [])[:4]:
            lines.append(f"↔️ {diff}")
        await asyncio.to_thread(fabians_master.notify, "\n".join(lines))


def start_check(place_id: int, notify: bool) -> None:
    task = asyncio.create_task(check(place_id, notify))
    background.add(task)
    task.add_done_callback(background.discard)


background: set[asyncio.Task] = set()


# -- API ------------------------------------------------------------------------------------------
@routes.get("/")
async def index_page(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@routes.get("/api/standort")
async def api_location(request: web.Request) -> web.Response:
    try:
        loc = await geo.current_location(request.app["http"], DEVICE, APPLE_ID)
    except geo.GeoError as err:
        raise Fail(503, str(err))
    loc["address"] = await geo.reverse(request.app["http"], loc["lat"], loc["lon"])
    return web.json_response(loc)


async def position(request: web.Request, data: dict) -> tuple[float, float, str]:
    if data.get("lat") not in (None, "") and data.get("lon") not in (None, ""):
        try:
            return float(data["lat"]), float(data["lon"]), "angegeben"
        except (TypeError, ValueError):
            raise Fail(400, "Ungültige Koordinaten")
    try:
        loc = await geo.current_location(request.app["http"], DEVICE, APPLE_ID)
    except geo.GeoError as err:
        raise Fail(503, str(err))
    age = loc.get("alter_s")
    when = "gerade eben" if loc["frisch_abgefragt"] or (age is not None and age < 90) else \
        f"vor {age // 60} Min." if age is not None else "Zeit unbekannt"
    accuracy = f", ±{int(loc['accuracy'])} m" if loc.get("accuracy") else ""
    return loc["lat"], loc["lon"], f"{loc['name']} ({loc['quelle']}, {when}{accuracy})"


@routes.get("/api/in-der-naehe")
async def api_nearby(request: web.Request) -> web.Response:
    lat, lon, _ = await position(request, dict(request.query))
    try:
        found = await geo.nearby(request.app["http"], lat, lon, MATCH_RADIUS)
    except geo.GeoError as err:
        raise Fail(503, str(err))
    return web.json_response({"lat": lat, "lon": lon, "places": found[:15]})


@routes.get("/api/offen")
async def api_open(request: web.Request) -> web.Response:
    """Is a shop, restaurant or office open now? Looked up around the person (or a named place)."""
    query = text(request.query.get("q"), 80)
    if not query:
        raise Fail(400, "Wonach soll ich suchen? ?q=NAME")
    session = request.app["http"]
    place_name = text(request.query.get("ort"), 80)
    if place_name:
        try:
            point = await geo.geocode(session, place_name)
        except geo.GeoError as err:
            raise Fail(503, str(err))
        if not point:
            raise Fail(404, f"Ort „{place_name}“ nicht gefunden")
        lat, lon, where = point[0], point[1], place_name
    else:
        lat, lon, where = await position(request, dict(request.query))
    try:
        found = await geo.find_named(session, query, lat, lon, 5000)
    except geo.GeoError as err:
        raise Fail(503, str(err))
    now = datetime.now()
    results = []
    for f in found[:6]:
        hours = f["tags"].get("opening_hours", "")
        state = oeffnung.status(hours, now) if hours else {"verstanden": False, "roh": ""}
        results.append({"name": f["name"], "art": f["art"], "adresse": f["address"], "entfernung_m": f["distance_m"],
                        "oeffnungszeiten": hours or "nicht in OpenStreetMap", "heute": oeffnung.today_text(hours) if hours else "",
                        "jetzt": state.get("text") or ("unbekannt – Öffnungszeiten bitte online prüfen" if not hours
                                                      else "Öffnungszeiten zu speziell – Rohtext prüfen"),
                        "offen": state.get("offen")})
    return web.json_response({"suche": query, "um": now.strftime("%a %d.%m. %H:%M"), "standort": where, "treffer": results})


@routes.post("/api/besuch")
async def api_visit(request: web.Request) -> web.Response:
    """A visit from the assistant: restaurant details from the menu, the menu, what was ordered."""
    data = await body(request)
    menu_info = data.get("restaurant") or {}
    if not isinstance(menu_info, dict):
        raise Fail(400, "restaurant muss ein Objekt sein")
    name = text(menu_info.get("name"), 120)
    session = request.app["http"]
    place_id = data.get("ort_id")
    match, certainty, candidates = None, "", []
    if place_id:
        place = store.place(int(place_id))
        if not place:
            raise Fail(404, "Diesen Ort gibt es nicht")
        lat, lon, where = place["lat"], place["lon"], "bekannter Ort"
    else:
        lat, lon, where = await position(request, data)
        try:
            candidates = await geo.nearby(session, lat, lon, MATCH_RADIUS)
        except geo.GeoError as err:
            log.info("Overpass: %s", err)
        match, certainty = geo.best_match(candidates, name)
        if match is None and name:
            # Not around the location (e.g. the visit is entered later): search the name nearby.
            try:
                hits = await geo.search(session, f"{name} {text(menu_info.get('address'), 120)}".strip(), (lat, lon))
            except geo.GeoError:
                hits = []
            hits = [h for h in hits if geo.distance_m((lat, lon), (h["lat"], h["lon"])) < 3000]
            if hits:
                match, certainty = hits[0], "über Namenssuche"
                match["distance_m"] = round(geo.distance_m((lat, lon), (match["lat"], match["lon"])))
        place = store.place_by_osm(match["osm_id"]) if match else None
        if not place:
            # A place already on the map close by with the same name counts as the same place.
            for p in store.places():
                if geo.distance_m((lat, lon), (p["lat"], p["lon"])) < 120 and name and geo.name_score(name, p["name"]) >= 0.75:
                    place = p
                    break
        if not place:
            if not match and not name:
                raise Fail(422, "Kein Restaurant in der Nähe gefunden und kein Name angegeben – bitte den Namen nennen")
            src = match or {}
            new_id = store.add_place(
                name=src.get("name") or name, lat=src.get("lat") or lat, lon=src.get("lon") or lon,
                address=src.get("address") or text(menu_info.get("address"), 160),
                kind=(src.get("tags") or {}).get("amenity") or "restaurant",
                cuisine=(src.get("tags") or {}).get("cuisine", "").replace(";", ", "),
                osm_id=src.get("osm_id"), osm=src or {}, from_menu={})
            place = store.place(new_id)
            if not place["address"]:
                store.update_place(new_id, address=await geo.reverse(session, place["lat"], place["lon"]))
    pid = place["id"]
    # what the menu says about the restaurant (name, address, phone …) – kept for the comparison
    info = {k: text(v, 160) for k, v in menu_info.items() if k in ("name", "address", "phone", "website", "note") and v}
    if info:
        store.update_place(pid, from_menu={**(place.get("from_menu") or {}), **info})
    dishes = []
    for d in data.get("speisekarte") or []:
        if isinstance(d, dict) and text(d.get("name")):
            dishes.append({"section": text(d.get("section"), 60), "name": text(d.get("name"), 120),
                           "price": price(d.get("price")), "description": text(d.get("description"), 300)})
    n_dishes = store.save_dishes(pid, dishes[:300])
    ordered = []
    for o in data.get("bestellt") or []:
        if isinstance(o, dict) and text(o.get("name")):
            ordered.append({"name": text(o.get("name"), 120), "price": price(o.get("price")),
                            "qty": max(1, min(20, int(o.get("qty") or 1))), "note": text(o.get("note"), 200)})
    visit_id = None
    if ordered or data.get("bewertung") is not None or data.get("notiz") or data.get("nur_ort") is not True:
        at = time.time()
        if data.get("zeit"):
            try:
                at = datetime.fromisoformat(str(data["zeit"])).timestamp()
            except ValueError:
                pass
        total = price(data.get("summe"))
        if total is None and ordered and all(o["price"] is not None for o in ordered):
            total = round(sum(o["price"] * o["qty"] for o in ordered), 2)
        visit_id = store.add_visit(pid, at, ordered, total, rating(data.get("bewertung")), text(data.get("notiz"), 500))
    # The online research runs for a new place and again after a month (or after a failed try).
    place = store.place(pid)
    fresh = place["checked_at"] and time.time() - place["checked_at"] < RECHECK_AFTER and place["check_state"] == "fertig"
    notify = bool(data.get("melden", True))
    if not fresh:
        start_check(pid, notify=notify)
    return web.json_response({
        "ort": summary({**store.place(pid), "visits": len(store.visits(pid))}), "besuch_id": visit_id,
        "zuordnung": certainty or ("bekannter Ort" if place_id else "neu"), "standort": where,
        "andere_in_der_naehe": [{"name": c["name"], "distance_m": c["distance_m"], "osm_id": c["osm_id"]}
                                for c in candidates[:6] if not match or c["osm_id"] != match.get("osm_id")],
        "gerichte_gespeichert": n_dishes,
        "abgleich": "schon abgeglichen am " + datetime.fromtimestamp(place["checked_at"]).strftime("%d.%m.%Y") if fresh
        else "läuft – das Ergebnis kommt per iMessage" if notify else "läuft"})


def save_image(raw: bytes) -> str:
    """Store a photo (shrunk to at most 1600 px, as JPEG); returns the file name."""
    PHOTOS.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        img.thumbnail((1600, 1600))
        img.convert("RGB").save(PHOTOS / name, "JPEG", quality=82)
    except (UnidentifiedImageError, OSError, ValueError):
        # A format Pillow cannot read (e.g. HEIC) is kept as it is; Safari shows it anyway.
        name = name.replace(".jpg", ".bin")
        (PHOTOS / name).write_bytes(raw)
    return name


@routes.post("/api/ort/{id}/foto")
async def api_add_photo(request: web.Request) -> web.Response:
    pid = int(request.match_info["id"])
    if not store.place(pid):
        raise Fail(404, "Diesen Ort gibt es nicht")
    raw = await request.read()
    if not raw or len(raw) > MAX_PHOTO:
        raise Fail(413, "Foto fehlt oder ist zu groß (höchstens 10 MB)")
    kind = request.query.get("art", "foto")
    kind = kind if kind in ("foto", "speisekarte", "essen", "beleg") else "foto"
    visit = request.query.get("besuch")
    file = await asyncio.to_thread(save_image, raw)
    photo_id = store.add_photo(pid, int(visit) if visit and visit.isdigit() else None, file, kind)
    return web.json_response({"foto_id": photo_id})


@routes.get("/api/foto/{id}")
async def api_photo(request: web.Request) -> web.StreamResponse:
    photo = store.photo(int(request.match_info["id"]))
    if not photo or not (PHOTOS / photo["file"]).exists():
        raise Fail(404, "Foto nicht gefunden")
    ctype = "image/jpeg" if photo["file"].endswith(".jpg") else "application/octet-stream"
    return web.FileResponse(PHOTOS / photo["file"], headers={"Content-Type": ctype, "Cache-Control": "max-age=86400"})


@routes.get("/api/orte")
async def api_places(request: web.Request) -> web.Response:
    query = geo.norm(request.query.get("suche", ""))
    places = [summary(p) for p in store.places()]
    if query:
        places = [p for p in places if query in geo.norm(f"{p['name']} {p['address']} {p['cuisine']}")
                  or any(query in geo.norm(d["name"]) for d in store.dishes(p["id"]))]
    return web.json_response({"orte": places})


@routes.get("/api/ort/{id}")
async def api_place(request: web.Request) -> web.Response:
    return web.json_response(detail(int(request.match_info["id"])))


@routes.patch("/api/ort/{id}")
async def api_edit_place(request: web.Request) -> web.Response:
    pid = int(request.match_info["id"])
    if not store.place(pid):
        raise Fail(404, "Diesen Ort gibt es nicht")
    data = await body(request)
    fields = {}
    for key, limit in (("name", 120), ("address", 160), ("cuisine", 60), ("note", 1000)):
        if key in data:
            fields[key] = text(data[key], limit)
    if fields.get("name") == "":
        raise Fail(400, "Name fehlt")
    if fields:
        store.update_place(pid, **fields)
    if "besuch_id" in data:
        store.rate_visit(int(data["besuch_id"]), rating(data.get("bewertung")) if "bewertung" in data else None,
                         text(data["notiz"], 500) if "notiz" in data else None)
    return web.json_response(detail(pid))


@routes.delete("/api/ort/{id}")
async def api_delete_place(request: web.Request) -> web.Response:
    for file in store.delete_place(int(request.match_info["id"])):
        (PHOTOS / file).unlink(missing_ok=True)
    return web.json_response({"ok": True})


@routes.post("/api/ort/{id}/abgleich")
async def api_recheck(request: web.Request) -> web.Response:
    pid = int(request.match_info["id"])
    if not store.place(pid):
        raise Fail(404, "Diesen Ort gibt es nicht")
    start_check(pid, notify=request.query.get("melden") == "1")
    return web.json_response({"ok": True, "abgleich": "läuft"})


# -- start ---------------------------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession(trust_env=True)
    # A check interrupted by a restart is simply marked; the button on the page starts it again.
    for p in store.places():
        if p["check_state"] == "läuft":
            store.update_place(p["id"], check_state="unterbrochen")
    log.info("Karte bereit auf Port %s – %d Orte%s", PORT, len(store.places()),
             f", Standort von {DEVICE}" if DEVICE else ", Standort automatisch (Wo ist? vor Home-Assistant-App)")


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()


def main() -> None:
    app = web.Application(middlewares=[guard], client_max_size=MAX_PHOTO + 1024 * 1024)
    app.add_routes(routes)
    app.router.add_static("/static/", STATIC)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    # IPv4 only: callers are checked by their IPv4 address (the add-on network also has IPv6).
    web.run_app(app, host="0.0.0.0", port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
