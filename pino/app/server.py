"""Fabians-HA-Pino: a kiwi with a life of its own in a small sandbox world.

The world (buildings) and Pino's life run here; his brain is Ollama on another computer in the home network,
Claude (through Fabians-HA-Master) designs new buildings and builds his websites. The page in Home Assistant
shows the world in 3D; the assistant asks through the master what Pino is doing.
"""

import asyncio
import base64
import json
import logging
import os
import posixpath
import re
import secrets
import socket
import time
from pathlib import Path

import aiohttp
from aiohttp import web

import fabians_master
from brain import Brain
from pino import Pino, Settings, stamp
from workshop import SITE_PATH, ClaudeError, design_building
from world import World, WorldError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pino")

DATA = Path(os.environ.get("PINO_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("PINO_PORT", "8105"))
INGRESS_IP = "172.30.32.2"


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPT = load_options()


class Fail(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# -- access ---------------------------------------------------------------------------------------------------
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
    if os.environ.get("PINO_OPEN") != "1" and request.remote not in (INGRESS_IP, master_ip()):
        return web.json_response({"error": "Nur über Home Assistant oder den Assistenten"}, status=403)
    try:
        return await handler(request)
    except Fail as err:
        return web.json_response({"error": str(err)}, status=err.status)
    except WorldError as err:
        return web.json_response({"error": str(err)}, status=400)


async def body_of(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise Fail("JSON erwartet")
    if not isinstance(data, dict):
        raise Fail("JSON-Objekt erwartet")
    return data


routes = web.RouteTableDef()


def app_of(request: web.Request) -> tuple[World, Pino]:
    return request.app["world"], request.app["pino"]


# -- page --------------------------------------------------------------------------------------------------------
@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@routes.get("/static/{name}")
async def static(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    if not re.match(r"^[a-z0-9_-]+\.(js|css)$", name) or not (STATIC / name).exists():
        raise web.HTTPNotFound()
    return web.FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"})


# -- world -------------------------------------------------------------------------------------------------------
@routes.get("/api/world")
async def api_world(request: web.Request) -> web.Response:
    world, _ = app_of(request)
    return web.json_response(world.public())


@routes.get("/api/state")
async def api_state(request: web.Request) -> web.Response:
    world, pino = app_of(request)
    return web.json_response({"pino": pino.public(), "world_version": world.version, "jobs": list(request.app["jobs"].values())[-10:]})


@routes.post("/api/buildings")
async def api_place(request: web.Request) -> web.Response:
    world, _ = app_of(request)
    data = await body_of(request)
    b = world.place(str(data.get("type")), int(data.get("x", 0)), int(data.get("z", 0)), int(data.get("rot", 0)))
    return web.json_response({**b, "door": world.door(b)})


@routes.post("/api/buildings/{id}")
async def api_move(request: web.Request) -> web.Response:
    world, _ = app_of(request)
    data = await body_of(request)
    b = world.move(request.match_info["id"], int(data.get("x", 0)), int(data.get("z", 0)), int(data.get("rot", 0)))
    return web.json_response({**b, "door": world.door(b)})


@routes.delete("/api/buildings/{id}")
async def api_remove(request: web.Request) -> web.Response:
    world, _ = app_of(request)
    world.remove(request.match_info["id"])
    return web.json_response({"ok": True})


# -- building creator ---------------------------------------------------------------------------------------------
async def run_design(app: web.Application, job: dict, existing: dict | None) -> None:
    world: World = app["world"]
    try:
        raw = await asyncio.to_thread(design_building, job["request"], existing)
        raw["request"] = job["request"] if not existing else (existing.get("request", "") + " | " + job["request"])[-1000:]
        t = world.add_type(raw, existing["id"] if existing else None)
        job.update(status="fertig", type=t["id"], name=t["name"], emoji=t["emoji"])
        log.info("Gebäude erstellt: %s", t["name"])
    except (ClaudeError, WorldError) as err:
        job.update(status="fehler", error=str(err))
    except Exception as err:  # noqa: BLE001
        log.exception("Gebäude-Ersteller")
        job.update(status="fehler", error=str(err)[:300])
    job["done"] = stamp()


@routes.post("/api/types")
async def api_create_type(request: web.Request) -> web.Response:
    """Describe a building (or a change to an own one); Claude designs it in the background."""
    world, _ = app_of(request)
    data = await body_of(request)
    text = " ".join(str(data.get("request") or "").split())[:1000]
    if len(text) < 5:
        raise Fail("Beschreibe das Gebäude in ein paar Worten")
    existing = None
    if data.get("base"):
        existing = world.custom.get(str(data["base"]))
        if not existing:
            raise Fail("Nur selbst erstellte Gebäude können geändert werden")
    jobs = request.app["jobs"]
    if sum(1 for j in jobs.values() if j["status"] == "läuft") >= 2:
        raise Fail("Claude baut gerade schon zwei Gebäude – kurz warten", 429)
    job = {"id": secrets.token_hex(4), "status": "läuft", "request": text, "base": existing["id"] if existing else None,
           "started": stamp()}
    jobs[job["id"]] = job
    while len(jobs) > 30:
        jobs.pop(next(iter(jobs)))
    asyncio.create_task(run_design(request.app, job, existing))
    return web.json_response(job)


@routes.delete("/api/types/{id}")
async def api_delete_type(request: web.Request) -> web.Response:
    world, _ = app_of(request)
    world.delete_type(request.match_info["id"])
    return web.json_response({"ok": True})


# -- Pino's things ---------------------------------------------------------------------------------------------------
@routes.get("/api/pino/{what}")
async def api_pino(request: web.Request) -> web.Response:
    _, pino = app_of(request)
    what, s = request.match_info["what"], pino.s
    n = max(1, min(200, int(request.query.get("n") or 30)))
    if what == "tagebuch":
        return web.json_response(s["diary"][:n])
    if what == "erlebnisse":
        return web.json_response(s["events"][:n])
    if what == "wissen":
        return web.json_response(s["knowledge"])
    if what == "bilder":
        return web.json_response(s["paintings"][:n])
    if what == "webseiten":
        return web.json_response(pino.sites.list())
    if what == "status":
        return web.json_response(pino.status_text())
    if what == "interessen":
        return web.json_response(pino.public()["interests"])
    raise web.HTTPNotFound()


@routes.get("/bilder/{id}.svg")
async def picture(request: web.Request) -> web.Response:
    _, pino = app_of(request)
    pid = request.match_info["id"]
    path = pino.pictures / f"{pid}.svg"
    if not re.match(r"^[0-9a-f-]+$", pid) or not path.exists():
        raise web.HTTPNotFound()
    return web.Response(body=path.read_bytes(), content_type="image/svg+xml",
                        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


NAV_SCRIPT = ("<script>document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[data-pino-page]');"
              "if(a){e.preventDefault();parent.postMessage({pinoPage:a.getAttribute('data-pino-page')},'*');}});</script>")


def render_page(files: dict[str, str], page: str) -> str:
    """One page of a website with its CSS, JS and SVG inlined, so it can be shown in a sandboxed frame
    (no access to Home Assistant) without loading anything from the add-on. Links to other pages of the
    site are passed to the dashboard, which shows that page next."""
    folder = posixpath.dirname(page)

    def local(ref: str) -> str | None:
        ref = ref.split("#")[0].split("?")[0].strip()
        if not ref or re.match(r"^[a-z]+:|^//", ref, re.I):
            return None
        path = posixpath.normpath(posixpath.join(folder, ref)).lstrip("/")
        return path if path in files else None

    html = files[page]

    def css(m):
        path = local(m.group(2))
        return f"<style>{files[path]}</style>" if path else m.group(0)

    def js(m):
        path = local(m.group(1))
        return f"<script>{files[path].replace('</script', '<\\/script')}</script>" if path else m.group(0)

    def asset(m):
        path = local(m.group(2))
        if path and path.endswith(".svg"):
            data = base64.b64encode(files[path].encode()).decode()
            return f'{m.group(1)}"data:image/svg+xml;base64,{data}"'
        return m.group(0)

    def link(m):
        ref = m.group(2)
        path = local(ref)
        if path and path.endswith(".html"):
            return f'href="#" data-pino-page="{path}"'
        if ref.startswith("#"):
            return m.group(0)
        return m.group(0)

    html = re.sub(r"<link\b[^>]*rel=[\"']?stylesheet[\"']?[^>]*href=([\"'])([^\"']+)\1[^>]*>", css, html, flags=re.I)
    html = re.sub(r"<link\b[^>]*href=([\"'])([^\"']+)\1[^>]*rel=[\"']?stylesheet[\"']?[^>]*>", css, html, flags=re.I)
    html = re.sub(r"<script\b[^>]*src=[\"']([^\"']+)[\"'][^>]*>\s*</script>", js, html, flags=re.I)
    html = re.sub(r"((?:src|href)=)[\"']([^\"']+\.svg)[\"']", asset, html, flags=re.I)
    html = re.sub(r"(href)=[\"']([^\"']+)[\"']", link, html, flags=re.I)
    csp = "<meta http-equiv=\"Content-Security-Policy\" content=\"connect-src 'none'; form-action 'none'; frame-src 'none'; object-src 'none'\">"
    html = re.sub(r"<head[^>]*>", lambda m: m.group(0) + csp, html, count=1, flags=re.I) if re.search(r"<head", html, re.I) else csp + html
    return html + NAV_SCRIPT


@routes.get("/api/webseiten/{slug}")
async def api_site(request: web.Request) -> web.Response:
    _, pino = app_of(request)
    slug = request.match_info["slug"]
    page = request.query.get("seite") or "index.html"
    if not re.match(r"^[a-z0-9-]{1,40}$", slug) or not SITE_PATH.match(page) or ".." in page:
        raise web.HTTPNotFound()
    files = await asyncio.to_thread(pino.sites.files, slug)
    if page not in files:
        raise Fail("Diese Seite gibt es nicht", 404)
    meta = next((s for s in pino.sites.list() if s["slug"] == slug), {})
    pages = sorted(p for p in files if p.endswith(".html"))
    return web.json_response({"html": render_page(files, page), "page": page, "pages": pages, "meta": meta})


# -- start ------------------------------------------------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession()
    world = World(DATA / "world.json")
    brain = Brain(str(OPT.get("ollama_url") or "").strip(), str(OPT.get("ollama_modell") or "qwen2.5:3b").strip())
    brain.http = app["http"]
    pino = Pino(DATA, world, brain, Settings(OPT), fabians_master.notify)
    pino.http = app["http"]
    app.update(world=world, pino=pino, jobs={})
    app["loop"] = asyncio.create_task(pino.run())
    log.info("Pino lebt: %d Gebäude, Gehirn %s (%s)", len(world.buildings), brain.url or "nicht eingetragen", brain.model)
    if not brain.url:
        log.warning("Option ollama_url ist leer – Pino döst, bis sein Gehirn (Ollama) eingetragen ist")


async def on_cleanup(app: web.Application) -> None:
    app["loop"].cancel()
    app["pino"].save()
    await app["http"].close()


def make_app() -> web.Application:
    app = web.Application(middlewares=[guard])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    # IPv4 only: callers are checked by their IPv4 address (the add-on network also has IPv6).
    web.run_app(make_app(), host="0.0.0.0", port=PORT, print=None, access_log=None)
