"""Reads what a listing page reveals: title, picture, location, rating, guests, rooms, amenities, price.

Airbnb (and other sites) change their pages often and sometimes block automatic visitors, so this
is best effort: whatever is found is kept, the rest can be filled in by hand on the page.
"""

import asyncio
import html as htmllib
import re

import aiohttp

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/141.0.0.0 Safari/537.36")


def _meta(text: str, prop: str) -> str:
    m = re.search(rf"""<meta[^>]+(?:property|name)=["']{re.escape(prop)}["'][^>]*content=["']([^"']*)""", text, re.I) \
        or re.search(rf"""<meta[^>]+content=["']([^"']*)["'][^>]*(?:property|name)=["']{re.escape(prop)}["']""", text, re.I)
    return htmllib.unescape(m.group(1)).strip() if m else ""


def _first(pattern: str, text: str, cast=str):
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return cast(m.group(1))
    except ValueError:
        return None


def parse(text: str, url: str) -> dict:
    """Facts from the HTML of a listing page (Airbnb first, generic meta tags for other sites)."""
    title = _meta(text, "og:title") or _first(r"<title[^>]*>([^<]+)", text) or ""
    info = {
        "url": url,
        "titel": htmllib.unescape(title).replace(" - Airbnb", "").strip()[:200],
        "beschreibung": _meta(text, "og:description")[:600],
        "bild": _meta(text, "og:image"),
    }
    lat = _first(r'"lat(?:itude)?"\s*:\s*(-?\d{1,3}\.\d+)', text, float)
    lon = _first(r'"(?:lng|lon|longitude)"\s*:\s*(-?\d{1,3}\.\d+)', text, float)
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
        info["lat"], info["lon"] = lat, lon
    rating = _first(r'"(?:starRating|avgRating|guestSatisfactionOverall|ratingValue)"\s*:\s*"?(\d(?:\.\d+)?)', text, float)
    if rating:
        info["bewertung"] = rating
    reviews = _first(r'"(?:reviewCount|visibleReviewCount|reviewsCount)"\s*:\s*"?(\d+)', text, int)
    if reviews:
        info["anzahl_bewertungen"] = reviews
    guests = _first(r'"personCapacity"\s*:\s*(\d+)', text, int) or _first(r"(\d+)\s+(?:Gäste|guests)", text, int)
    if guests:
        info["gaeste"] = guests
    for key, pat in (("schlafzimmer", r"(\d+)\s+(?:Schlafzimmer|bedrooms?)"), ("betten", r"(\d+)\s+(?:Betten|Bett|beds?)\b"),
                     ("baeder", r"(\d+(?:[.,]5)?)\s+(?:Badezimmer|Bäder|Bad|baths?|bathrooms?)\b")):
        value = _first(pat, info["titel"] + " " + info["beschreibung"] + " " + text[:200000], lambda v: float(v.replace(",", ".")))
        if value:
            info[key] = value
    amenities = re.findall(r'"(?:title|name)"\s*:\s*"([^"]{3,40})"\s*,\s*"(?:available|isAvailable)"\s*:\s*true', text)
    if amenities:
        info["ausstattung"] = sorted(set(amenities))[:40]
    price = _first(r'"(?:priceString|displayPrice|discountedPrice|price)"\s*:\s*"([^"]*\d[^"]*)"', text)
    if price:
        info["preis_text"] = htmllib.unescape(price)[:60]
    return info


async def fetch(session: aiohttp.ClientSession, url: str) -> dict:
    headers = {"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8", "Accept": "text/html,*/*"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=25), max_redirects=8) as r:
            if r.status >= 400:
                return {"url": url, "fehler": f"Seite nicht abrufbar (HTTP {r.status}) – bitte die Angaben von Hand ergänzen"}
            text = await r.text(errors="replace")
            final = str(r.url)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        return {"url": url, "fehler": f"Seite nicht erreichbar ({err.__class__.__name__}) – bitte die Angaben von Hand ergänzen"}
    info = parse(text, final)
    if not info.get("titel"):
        info["fehler"] = "Auf der Seite war nichts zu finden – bitte die Angaben von Hand ergänzen"
    return info


def clean_url(text: str) -> str | None:
    m = re.search(r"https?://\S+", text or "")
    if not m:
        return None
    url = m.group(0).rstrip(").,;")
    # Airbnb: drop tracking parameters but keep the dates/guests, they change the price
    if "airbnb." in url:
        base, _, query = url.partition("?")
        keep = [p for p in query.split("&") if p.split("=")[0] in ("check_in", "check_out", "adults", "children", "guests")]
        url = base + ("?" + "&".join(keep) if keep else "")
    return url

