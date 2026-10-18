"""Places from open data: OpenStreetMap (Nominatim for addresses, Overpass for places) and Wikipedia.

Used for the spot suggestions (candidates that Claude picks from, so nothing is made up) and to
describe the surroundings of an accommodation (distances to centre, beach, supermarket …).
"""

import asyncio
import logging
import math
import time

import aiohttp

log = logging.getLogger("urlaub.geo")

UA = "Fabians-HA-Urlaub/1.0 (Home Assistant add-on; https://github.com/fvh02/Fabians-HA-Addons)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
WIKI = "https://{lang}.wikipedia.org/w/api.php"

_last_nominatim = 0.0
_nominatim_lock = asyncio.Lock()


class GeoError(Exception):
    pass


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


async def geocode(session: aiohttp.ClientSession, query: str) -> dict | None:
    """Coordinates and name of a place ("Lissabon", "Hvar, Kroatien", an address)."""
    global _last_nominatim
    async with _nominatim_lock:     # Nominatim allows one request per second
        wait = 1.1 - (time.monotonic() - _last_nominatim)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_nominatim = time.monotonic()
        params = {"q": query, "format": "jsonv2", "limit": "1", "accept-language": "de", "addressdetails": "1"}
        try:
            async with session.get(NOMINATIM, params=params, headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=20)) as r:
                data = await r.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise GeoError(f"Ortssuche nicht erreichbar ({err.__class__.__name__})")
    if not data:
        return None
    hit = data[0]
    return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "name": hit.get("display_name", query),
            "country_code": (hit.get("address") or {}).get("country_code", "")}


async def overpass(session: aiohttp.ClientSession, query: str) -> list[dict]:
    last = None
    for url in OVERPASS:
        try:
            async with session.post(url, data={"data": query}, headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=70)) as r:
                if r.status == 200:
                    return (await r.json(content_type=None)).get("elements", [])
                last = f"HTTP {r.status}"
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            last = err.__class__.__name__
    raise GeoError(f"OpenStreetMap ist gerade nicht erreichbar ({last}) – bitte später noch einmal")


# What counts as an interesting place, and how it is labelled for Claude.
SPOT_FILTERS = [
    'node["tourism"~"viewpoint|attraction|artwork|museum|gallery|picnic_site"]',
    'way["tourism"~"viewpoint|attraction|museum"]',
    'node["natural"~"beach|waterfall|cave_entrance|peak|spring|hot_spring|bay|cliff|arch|rock"]',
    'way["natural"~"beach|bay|cliff"]',
    'node["historic"]', 'way["historic"~"castle|ruins|fort|monastery|archaeological_site|tower"]',
    'node["man_made"~"lighthouse|tower|windmill"]',
    'node["leisure"~"beach_resort|nature_reserve|park|swimming_area"]',
    'way["leisure"~"nature_reserve|beach_resort|swimming_area"]',
    'node["amenity"~"bar|pub|biergarten|cafe|ice_cream"]["name"]',
    'node["amenity"="restaurant"]["name"]["cuisine"]',
    'node["waterway"="waterfall"]',
]


def _label(tags: dict) -> str:
    for key in ("tourism", "natural", "historic", "man_made", "leisure", "amenity", "waterway"):
        if key in tags:
            return f"{key}={tags[key]}"
    return ""


async def spot_candidates(session: aiohttp.ClientSession, lat: float, lon: float, radius_km: float = 15) -> list[dict]:
    """Named places around a point, from OpenStreetMap and Wikipedia, most interesting first."""
    r = int(radius_km * 1000)
    body = "".join(f"{f}(around:{r},{lat},{lon});" for f in SPOT_FILTERS)
    query = f"[out:json][timeout:60];({body});out center tags 700;"
    elements, wiki = await asyncio.gather(overpass(session, query), wikipedia_nearby(session, lat, lon, min(10.0, radius_km)),
                                          return_exceptions=True)
    if isinstance(elements, Exception):
        if isinstance(wiki, Exception) or not wiki:
            raise elements
        elements = []
    if isinstance(wiki, Exception):
        log.info("Wikipedia nicht erreichbar: %s", wiki)
        wiki = []
    out, seen = [], set()
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name:de") or tags.get("name")
        if not name or name.lower() in seen:
            continue
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None:
            continue
        seen.add(name.lower())
        info = {k: tags[k] for k in ("description", "cuisine", "opening_hours", "wikipedia", "website", "ele", "fee", "access")
                if k in tags}
        score = sum(1 for k in ("wikipedia", "wikidata", "description", "website", "image") if k in tags)
        out.append({"id": f"osm{el['type'][0]}{el['id']}", "name": name, "art": _label(tags), "lat": round(plat, 5),
                    "lon": round(plon, 5), "km": round(distance_km((lat, lon), (plat, plon)), 1), "info": info, "_score": score})
    for page in wiki:
        if page["name"].lower() in seen:
            continue
        seen.add(page["name"].lower())
        out.append({**page, "_score": 2})
    # The best documented and nearest first, but keep the whole mix (well-known places are often too
    # well documented – Claude decides what is a hidden gem).
    out.sort(key=lambda c: (-c["_score"], c["km"]))
    for c in out:
        c.pop("_score", None)
    return out[:220]


async def wikipedia_nearby(session: aiohttp.ClientSession, lat: float, lon: float, radius_km: float = 10, lang: str = "de") -> list[dict]:
    params = {"action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": str(int(radius_km * 1000)),
              "gslimit": "60", "format": "json"}
    try:
        async with session.get(WIKI.format(lang=lang), params=params, headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=20)) as r:
            data = await r.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
        raise GeoError(str(err))
    return [{"id": f"wp{p['pageid']}", "name": p["title"], "art": "wikipedia-artikel", "lat": round(p["lat"], 5),
             "lon": round(p["lon"], 5), "km": round(p["dist"] / 1000, 1), "info": {}} for p in data.get("query", {}).get("geosearch", [])]


# What is looked up around an accommodation: label → (OSM key, accepted values, element types)
NEAR = {
    "supermarkt": ("shop", {"supermarket", "convenience"}, "node"),
    "restaurant": ("amenity", {"restaurant", "cafe", "bar", "pub"}, "node"),
    "strand": ("natural", {"beach"}, "nwr"),
    "haltestelle": ("public_transport", {"platform"}, "node"),
    "bahnhof": ("railway", {"station"}, "node"),
}


async def surroundings(session: aiohttp.ClientSession, lat: float, lon: float, centre: tuple[float, float] | None) -> dict:
    """What is near an accommodation – the basis for the location score."""
    body = "".join(f'{types}["{key}"~"^({"|".join(sorted(values))})$"](around:2500,{lat},{lon});'
                   for key, values, types in NEAR.values())
    elements = await overpass(session, f"[out:json][timeout:40];({body});out center tags 600;")
    result: dict = {}
    for label, (key, values, _) in NEAR.items():
        found = []
        for el in elements:
            if (el.get("tags") or {}).get(key) not in values:
                continue
            plat = el.get("lat") or (el.get("center") or {}).get("lat")
            plon = el.get("lon") or (el.get("center") or {}).get("lon")
            if plat is not None:
                found.append(distance_km((lat, lon), (plat, plon)))
        found.sort()
        result[label] = {"naechstes_km": round(found[0], 2) if found else None, "anzahl_1km": sum(1 for d in found if d <= 1)}
    if centre:
        result["zentrum_km"] = round(distance_km((lat, lon), centre), 2)
    return result
