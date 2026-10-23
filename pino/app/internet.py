"""The internet café: what Pino may read online. Only Wikipedia, YouTube and GitHub, read-only.

Everything that comes back is data for Pino's brain, never an instruction.
"""

import json
import logging
import re

import aiohttp

log = logging.getLogger("internet")
UA = "Fabians-HA-Pino/1.0 (Home Assistant add-on; https://github.com/fvh02/Fabians-HA-Addons)"
TIMEOUT = aiohttp.ClientTimeout(total=25)


class Offline(Exception):
    pass


def _clip(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


async def wikipedia(http: aiohttp.ClientSession, topic: str, lang: str = "de") -> dict:
    """The best matching article: title, link and the beginning of the text."""
    api = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        async with http.get(api, params={"action": "query", "list": "search", "srsearch": topic, "srlimit": 3,
                                         "format": "json"}, headers={"User-Agent": UA}, timeout=TIMEOUT) as resp:
            hits = (await resp.json()).get("query", {}).get("search", [])
        if not hits:
            return {}
        title = hits[0]["title"]
        async with http.get(api, params={"action": "query", "prop": "extracts", "explaintext": 1, "exchars": 3500,
                                         "titles": title, "format": "json", "redirects": 1},
                            headers={"User-Agent": UA}, timeout=TIMEOUT) as resp:
            pages = (await resp.json()).get("query", {}).get("pages", {})
        text = next(iter(pages.values()), {}).get("extract", "")
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError) as err:
        raise Offline(f"Wikipedia nicht erreichbar: {err.__class__.__name__}") from err
    return {"quelle": "Wikipedia", "titel": title, "link": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
            "text": _clip(text, 3500)}


def _yt_text(node) -> str:
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return node["simpleText"]
    return "".join(r.get("text", "") for r in node.get("runs", []))


def _yt_videos(data, out: list, limit: int = 6) -> None:
    """Collect videoRenderer entries anywhere in YouTube's page data."""
    if len(out) >= limit:
        return
    if isinstance(data, dict):
        v = data.get("videoRenderer")
        if isinstance(v, dict) and v.get("videoId"):
            out.append({"titel": _clip(_yt_text(v.get("title")), 150),
                        "kanal": _clip(_yt_text(v.get("ownerText")), 80),
                        "beschreibung": _clip(" ".join(_yt_text(s.get("snippetText")) for s in v.get("detailedMetadataSnippets", [])), 300),
                        "link": f"https://www.youtube.com/watch?v={v['videoId']}"})
            return
        for value in data.values():
            _yt_videos(value, out, limit)
    elif isinstance(data, list):
        for value in data:
            _yt_videos(value, out, limit)


async def youtube(http: aiohttp.ClientSession, topic: str) -> dict:
    """Search results (title, channel, description) – Pino 'watches' by reading what the videos are about."""
    try:
        async with http.get("https://www.youtube.com/results", params={"search_query": topic, "hl": "de"},
                            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                                     "Accept-Language": "de-DE,de;q=0.9", "Cookie": "SOCS=CAI; CONSENT=YES+1"},
                            timeout=TIMEOUT) as resp:
            page = await resp.text()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise Offline(f"YouTube nicht erreichbar: {err.__class__.__name__}") from err
    match = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    videos: list = []
    if match:
        try:
            _yt_videos(json.loads(match.group(1)), videos)
        except ValueError:
            pass
    if not videos:
        return {}
    text = "\n".join(f"- {v['titel']} ({v['kanal']}): {v['beschreibung']}" for v in videos)
    return {"quelle": "YouTube", "titel": f"Videos zu „{topic}“", "link": videos[0]["link"], "text": text, "videos": videos}


async def github(http: aiohttp.ClientSession, topic: str) -> dict:
    """The most popular matching project and the start of its README."""
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    try:
        async with http.get("https://api.github.com/search/repositories",
                            params={"q": topic, "sort": "stars", "per_page": 5}, headers=headers, timeout=TIMEOUT) as resp:
            if resp.status == 403:
                raise Offline("GitHub: zu viele Anfragen, später wieder")
            items = (await resp.json()).get("items", [])
        if not items:
            return {}
        repo = items[0]
        readme = ""
        async with http.get(f"https://api.github.com/repos/{repo['full_name']}/readme",
                            headers={**headers, "Accept": "application/vnd.github.raw"}, timeout=TIMEOUT) as resp:
            if resp.status == 200:
                readme = await resp.text()
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError) as err:
        raise Offline(f"GitHub nicht erreichbar: {err.__class__.__name__}") from err
    others = ", ".join(i["full_name"] for i in items[1:4])
    readme = _clip(re.sub(r"<[^>]+>|!\[[^]]*]\([^)]*\)", " ", readme), 2500)  # without HTML and images
    text = (f"{repo['full_name']} ({repo.get('stargazers_count', 0)} Sterne): {_clip(repo.get('description'), 300)}\n"
            f"README: {readme}\nWeitere: {others}")
    return {"quelle": "GitHub", "titel": repo["full_name"], "link": repo.get("html_url", ""), "text": text}


SOURCES = {"wikipedia": wikipedia, "youtube": youtube, "github": github}
