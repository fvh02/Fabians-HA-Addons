"""Where you are (Home Assistant) and which restaurant that is (OpenStreetMap: Overpass and Nominatim)."""

import asyncio
import difflib
import logging
import math
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import aiohttp

log = logging.getLogger("karte.geo")

UA = "Fabians-HA-Karte/1.0 (Home Assistant add-on; https://github.com/fvh02/Fabians-HA-Addons)"
SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor").rstrip("/")
NOMINATIM = os.environ.get("KARTE_NOMINATIM", "https://nominatim.openstreetmap.org")
OVERPASS = tuple(os.environ.get("KARTE_OVERPASS", "https://overpass-api.de/api/interpreter,"
                                "https://overpass.kumi.systems/api/interpreter").split(","))
EATING = "restaurant|cafe|fast_food|bar|pub|biergarten|ice_cream|food_court"

_last_nominatim = 0.0
_nominatim_lock = asyncio.Lock()


class GeoError(Exception):
    pass


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(restaurant|ristorante|trattoria|pizzeria|cafe|bistro|bar|gasthaus|gaststatte|imbiss|the|zum|zur|das|der|die|la|le|il)\b", " ", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def name_score(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


# -- Home Assistant ----------------------------------------------------------------------------------
# Devices from Apple's Find My come from Home Assistant's iCloud integration; their trackers carry
# these attributes (the companion app's trackers don't).
FINDMY_ATTRS = ("device_status", "account_fetch_interval", "owner_fullname")
FRESH_WAIT = float(os.environ.get("KARTE_FRESH_WAIT", "25"))


async def _ha(session: aiohttp.ClientSession, method: str, path: str, body: dict | None = None):
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        raise GeoError("Kein Zugriff auf Home Assistant")
    try:
        async with session.request(method, f"{SUPERVISOR}/core/api{path}", json=body,
                                   headers={"Authorization": f"Bearer {token}"}, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status >= 400:
                raise GeoError(f"Home Assistant antwortet mit {r.status}")
            return await r.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        raise GeoError(f"Home Assistant nicht erreichbar ({err.__class__.__name__})")


def is_findmy(state: dict) -> bool:
    return state["entity_id"].startswith("device_tracker.") and any(k in (state.get("attributes") or {}) for k in FINDMY_ATTRS)


def _has_gps(state: dict) -> bool:
    a = state.get("attributes") or {}
    return a.get("latitude") is not None and a.get("longitude") is not None


def pick(states: list[dict], wanted: str = "") -> dict:
    """The tracker to use: the configured one, otherwise an iPhone from Find My, otherwise a person."""
    if wanted:
        for s in states:
            if s["entity_id"] == wanted:
                if not _has_gps(s):
                    raise GeoError(f"{wanted} hat gerade keinen Standort")
                return s
        raise GeoError(f"{wanted} gibt es in Home Assistant nicht")
    findmy = [s for s in states if is_findmy(s) and _has_gps(s)]
    findmy.sort(key=lambda s: ("iphone" not in (str((s.get("attributes") or {}).get("device_name", "")) + s["entity_id"]).lower(),
                               s["entity_id"]))
    if findmy:
        return findmy[0]
    people = [s for s in states if s["entity_id"].startswith("person.") and _has_gps(s)]
    people += [s for s in states if s["entity_id"].startswith("device_tracker.") and _has_gps(s)]
    if people:
        return people[0]
    raise GeoError("Kein Standort in Home Assistant – richte die iCloud-Integration (Wo ist?) oder die "
                   "Home-Assistant-App auf dem Handy ein")


async def refresh_findmy(session: aiohttp.ClientSession, state: dict, apple_id: str = "") -> bool:
    """Asks Apple for a new position of a Find My device and waits (up to FRESH_WAIT s) until it is there."""
    before = state.get("last_updated")
    body = {"account": apple_id} if apple_id else {}
    try:
        await _ha(session, "POST", "/services/icloud/update", body)
    except GeoError as err:
        if not apple_id:
            log.info("icloud.update ohne Konto: %s", err)
        return False
    deadline = time.monotonic() + FRESH_WAIT
    while time.monotonic() < deadline:
        await asyncio.sleep(2)
        try:
            now = await _ha(session, "GET", f"/states/{state['entity_id']}")
        except GeoError:
            return False
        if now.get("last_updated") != before and _has_gps(now):
            state.clear()
            state.update(now)
            return True
    return False


def age_seconds(state: dict) -> int | None:
    stamp = (state.get("attributes") or {}).get("last_seen") or state.get("last_updated")
    try:
        ts = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - ts).total_seconds()))


async def current_location(session: aiohttp.ClientSession, wanted: str = "", apple_id: str = "", fresh: bool = True) -> dict:
    """The person's position: live from Find My (asked for a fresh fix) if set up in Home Assistant,
    otherwise from the Home Assistant app."""
    states = await _ha(session, "GET", "/states")
    state = pick(states, wanted)
    refreshed = False
    if fresh and is_findmy(state):
        refreshed = await refresh_findmy(session, state, apple_id)
    a = state.get("attributes") or {}
    return {"lat": float(a["latitude"]), "lon": float(a["longitude"]), "accuracy": a.get("gps_accuracy"),
            "entity": state["entity_id"], "name": a.get("friendly_name") or state["entity_id"],
            "quelle": "Wo ist? (iCloud)" if is_findmy(state) else "Home-Assistant-App",
            "frisch_abgefragt": refreshed, "alter_s": age_seconds(state), "updated": state.get("last_updated")}


# -- OpenStreetMap ------------------------------------------------------------------------------------
async def _nominatim(session: aiohttp.ClientSession, path: str, params: dict):
    global _last_nominatim
    async with _nominatim_lock:     # Nominatim allows one request per second
        wait = 1.1 - (time.monotonic() - _last_nominatim)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_nominatim = time.monotonic()
        try:
            async with session.get(f"{NOMINATIM}/{path}", params={**params, "format": "jsonv2", "accept-language": "de"},
                                   headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=20)) as r:
                return await r.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise GeoError(f"Ortssuche nicht erreichbar ({err.__class__.__name__})")


def address_of(addr: dict) -> str:
    street = " ".join(x for x in (addr.get("road") or addr.get("pedestrian") or "", addr.get("house_number", "")) if x)
    town = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or ""
    return ", ".join(x for x in (street, " ".join(x for x in (addr.get("postcode", ""), town) if x)) if x)


async def reverse(session: aiohttp.ClientSession, lat: float, lon: float) -> str:
    try:
        data = await _nominatim(session, "reverse", {"lat": lat, "lon": lon, "addressdetails": 1, "zoom": 18})
    except GeoError:
        return ""
    return address_of((data or {}).get("address") or {}) or (data or {}).get("display_name", "")


async def search(session: aiohttp.ClientSession, query: str, near: tuple[float, float] | None) -> list[dict]:
    params = {"q": query, "limit": 5, "addressdetails": 1}
    if near:   # prefer results around the person
        d = 0.05
        params.update(viewbox=f"{near[1] - d},{near[0] + d},{near[1] + d},{near[0] - d}")
    data = await _nominatim(session, "search", params) or []
    return [{"name": h.get("name") or query, "lat": float(h["lat"]), "lon": float(h["lon"]),
             "address": address_of(h.get("address") or {}), "osm_id": f"{h.get('osm_type', '')[:1]}{h.get('osm_id')}",
             "tags": {"amenity": h.get("type", "")}} for h in data if h.get("lat")]


async def overpass(session: aiohttp.ClientSession, query: str) -> list[dict]:
    last = None
    for url in OVERPASS:
        try:
            async with session.post(url, data={"data": query}, headers={"User-Agent": UA},
                                    timeout=aiohttp.ClientTimeout(total=40)) as r:
                if r.status == 200:
                    return (await r.json(content_type=None)).get("elements", [])
                last = f"HTTP {r.status}"
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            last = err.__class__.__name__
    raise GeoError(f"OpenStreetMap ist gerade nicht erreichbar ({last})")


def _from_osm(el: dict, here: tuple[float, float]) -> dict:
    tags = el.get("tags") or {}
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    street = " ".join(x for x in (tags.get("addr:street", ""), tags.get("addr:housenumber", "")) if x)
    town = " ".join(x for x in (tags.get("addr:postcode", ""), tags.get("addr:city", "")) if x)
    return {"name": tags.get("name", ""), "lat": lat, "lon": lon, "osm_id": f"{el['type'][0]}{el['id']}",
            "address": ", ".join(x for x in (street, town) if x), "distance_m": round(distance_m(here, (lat, lon))),
            "tags": {k: v for k, v in tags.items() if k in ("amenity", "cuisine", "website", "contact:website", "phone",
                                                             "contact:phone", "opening_hours", "outdoor_seating",
                                                             "diet:vegetarian", "diet:vegan", "takeaway", "wheelchair")}}


async def nearby(session: aiohttp.ClientSession, lat: float, lon: float, radius: int = 150) -> list[dict]:
    """Named places to eat around a point, nearest first."""
    q = (f'[out:json][timeout:25];(nwr["amenity"~"^({EATING})$"]["name"](around:{radius},{lat},{lon}););'
         "out center tags 60;")
    found = [_from_osm(el, (lat, lon)) for el in await overpass(session, q)]
    found = [f for f in found if f["lat"] is not None and f["name"]]
    return sorted(found, key=lambda f: f["distance_m"])


def best_match(candidates: list[dict], name: str) -> tuple[dict | None, str]:
    """The candidate that fits the name from the menu (or simply the nearest one) and how sure that is."""
    if not candidates:
        return None, "keine"
    if name:
        scored = sorted(((name_score(name, c["name"]), -c["distance_m"], c) for c in candidates),
                        key=lambda t: (t[0], t[1]), reverse=True)
        score, _, best = scored[0]
        if score >= 0.75:
            return best, "sicher"
        if score >= 0.5:
            return best, "unsicher"
        return None, "kein_name"
    nearest = candidates[0]
    close = [c for c in candidates if c["distance_m"] <= nearest["distance_m"] + 25]
    return nearest, "sicher" if len(close) == 1 and nearest["distance_m"] <= 40 else "unsicher"


async def find_named(session: aiohttp.ClientSession, query: str, lat: float, lon: float, radius: int = 5000) -> list[dict]:
    """Shops, restaurants, offices … whose name contains the query, around a point, nearest first."""
    words = [re.escape(w) for w in re.findall(r"[\wÄÖÜäöüß'&.-]+", query)][:6]
    if not words:
        return []
    pattern = ".*".join(words).replace('"', "")
    q = (f'[out:json][timeout:25];(nwr["name"~"{pattern}",i](around:{radius},{lat},{lon});'
         f'nwr["brand"~"{pattern}",i](around:{radius},{lat},{lon}););out center tags 40;')
    found = []
    for el in await overpass(session, q):
        item = _from_osm(el, (lat, lon))
        tags = el.get("tags") or {}
        item["tags"]["opening_hours"] = tags.get("opening_hours", "")
        item["art"] = tags.get("amenity") or tags.get("shop") or tags.get("office") or tags.get("tourism") or tags.get("leisure") or ""
        if item["lat"] is not None and item["name"]:
            found.append(item)
    return sorted(found, key=lambda f: f["distance_m"])


async def geocode(session: aiohttp.ClientSession, query: str) -> tuple[float, float] | None:
    hits = await _nominatim(session, "search", {"q": query, "limit": 1})
    return (float(hits[0]["lat"]), float(hits[0]["lon"])) if hits else None
