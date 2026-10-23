"""Fabians-HA-Werkbank: Claude designs parts in FreeCAD, the add-on builds, checks and renders them and hands
them to Fabians-HA-3D-Druck – printing only after the owner confirms (on the phone or in the dashboard).

Two ways in: the assistant writes the scripts itself (command `werkbank`, via Fabians-HA-Master), or the owner
chats with Claude in the dashboard (Claude through the master). Photos with a reference sheet give real sizes.
"""

import asyncio
import io
import json
import logging
import os
import re
import shutil
import socket
import time
from pathlib import Path

import aiohttp
from aiohttp import web
from PIL import Image

import cad
import designer
import fabians_master
import measure
import render
from projects import NotFound, Store, now_iso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("werkbank")

DATA = Path(os.environ.get("WERKBANK_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("WERKBANK_PORT", "8106"))
INGRESS_IP = "172.30.32.2"
PENDING_HOURS = 3
MAX_PHOTO = 25 * 1024 * 1024


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPT = load_options()
MATERIAL = str(OPT.get("material") or "PLA").upper()
REFERENCE = str(OPT.get("referenz") or "a4").lower()


def prefix() -> str:
    host = socket.gethostname()
    return host.split("-", 1)[0] if "-" in host else "local"


DRUCK_URL = os.environ.get("WERKBANK_DRUCK_URL") or f"http://{prefix()}-druck3d:8095"


class Fail(Exception):
    def __init__(self, message: str, status: int = 400, **extra):
        super().__init__(message)
        self.status, self.extra = status, extra


# -- access ---------------------------------------------------------------------------------------------------
_master = {"ip": "", "at": 0.0}


def master_ip() -> str:
    if time.time() - _master["at"] > 300:
        try:
            _master["ip"] = socket.gethostbyname(f"{prefix()}-master")
        except OSError:
            _master["ip"] = ""
        _master["at"] = time.time()
    return _master["ip"]


@web.middleware
async def guard(request: web.Request, handler):
    # /dl/<token>/… is for Fabians-HA-3D-Druck: an unguessable link per version, nothing else is open.
    if not request.path.startswith("/dl/") and os.environ.get("WERKBANK_OPEN") != "1" \
            and request.remote not in (INGRESS_IP, master_ip()):
        return web.json_response({"error": "Nur über Home Assistant oder den Assistenten"}, status=403)
    try:
        return await handler(request)
    except Fail as err:
        return web.json_response({"error": str(err), **err.extra}, status=err.status)
    except NotFound as err:
        return web.json_response({"error": str(err)}, status=404)


async def body_of(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise Fail("JSON erwartet")
    if not isinstance(data, dict):
        raise Fail("JSON-Objekt erwartet")
    return data


routes = web.RouteTableDef()


def store(request: web.Request) -> Store:
    return request.app["store"]


# -- building versions ----------------------------------------------------------------------------------------------
async def build_version(app: web.Application, p: dict, source: str, values: dict | None, by: str, note: str) -> dict:
    """Runs the script in FreeCAD (one at a time), renders the preview and stores it as the next version."""
    st: Store = app["store"]
    async with app["cad_lock"]:
        p = st.get(p["id"])                         # fresh, another request may have added a version meanwhile
        n = st.next_version(p)
        folder = st.vdir(p["id"], n)
        material = p.get("material") or MATERIAL
        try:
            result = await asyncio.to_thread(cad.run, source, values or {}, material, folder)
        except cad.ScriptError:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
            raise
        await asyncio.to_thread(render.preview, sorted((folder / "teile").glob("*.stl")),
                                f"{p['name']} · Version {n}", result, folder / "vorschau.png")
        return st.add_version(p, n, result, by, note)


def summary(v: dict) -> str:
    g = v["gesamt"]["groesse_mm"]
    text = f"Version {v['n']}: {g[0]:g} × {g[1]:g} × {g[2]:g} mm, ca. {v['gesamt']['gewicht_g']:g} g {v.get('material', 'PLA')}"
    if len(v["teile"]) > 1:
        text += f", {len(v['teile'])} Teile"
    if v["warnungen"]:
        text += ". Achtung: " + "; ".join(v["warnungen"][:3])
    return text


def jpeg(path: Path) -> bytes:
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "JPEG", quality=88)
    return buf.getvalue()


# -- page -------------------------------------------------------------------------------------------------------------
@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@routes.get("/static/{name}")
async def static(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    if not re.match(r"^[a-z0-9_-]+\.(js|css)$", name) or not (STATIC / name).exists():
        raise web.HTTPNotFound()
    return web.FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"})


@routes.get("/api/anleitung")
async def api_guide(_: web.Request) -> web.Response:
    return web.json_response({"text": designer.GUIDE})


# -- projects -----------------------------------------------------------------------------------------------------------
@routes.get("/api/projekte")
async def api_projects(request: web.Request) -> web.Response:
    return web.json_response(store(request).list())


@routes.post("/api/projekte")
async def api_create(request: web.Request) -> web.Response:
    data = await body_of(request)
    p = store(request).create(str(data.get("name") or ""), str(data.get("beschreibung") or ""), str(data.get("von") or "dashboard"))
    return web.json_response(p)


def project_view(request: web.Request, p: dict) -> dict:
    return {**p, "arbeitet": request.app["busy"].get(p["id"], ""), "druck": request.app["pending"].get("data")}


@routes.get("/api/projekte/{id}")
async def api_project(request: web.Request) -> web.Response:
    return web.json_response(project_view(request, store(request).get(request.match_info["id"])))


@routes.delete("/api/projekte/{id}")
async def api_delete(request: web.Request) -> web.Response:
    store(request).delete(request.match_info["id"])
    return web.json_response({"ok": True})


@routes.post("/api/projekte/{id}/info")
async def api_info(request: web.Request) -> web.Response:
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request)
    if data.get("name"):
        p["name"] = str(data["name"]).strip()[:80]
    if "beschreibung" in data:
        p["beschreibung"] = str(data["beschreibung"]).strip()[:3000]
    if data.get("material"):
        p["material"] = str(data["material"]).upper()[:6]
    st.save(p)
    return web.json_response(p)


@routes.post("/api/projekte/{id}/skript")
async def api_script(request: web.Request) -> web.Response:
    """A script from the assistant (or pasted in the dashboard) becomes a new version."""
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request)
    source = str(data.get("skript") or "")
    if not source.strip():
        raise Fail("Kein Skript")
    by = str(data.get("von") or "assistent")[:20]
    try:
        v = await build_version(request.app, p, source, data.get("werte") or {}, by, str(data.get("notiz") or ""))
    except cad.ScriptError as err:
        raise Fail(f"Das Skript funktioniert nicht: {err}", 422)
    p = st.get(p["id"])
    if data.get("notiz"):
        st.chat(p, "claude", f"{data['notiz']}\n\n{summary(v)}", version=v["n"], von=by)
        st.save(p)
    return web.json_response({**v, "zusammenfassung": summary(v)})


@routes.post("/api/projekte/{id}/parameter")
async def api_parameters(request: web.Request) -> web.Response:
    """New values for the parameters of the latest (or a given) version – without Claude."""
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request)
    base = st.version(p, data.get("version"))
    source = (st.vdir(p["id"], base["n"]) / "skript.py").read_text(encoding="utf-8")
    values = {**base.get("werte", {}), **{k: v for k, v in (data.get("werte") or {}).items() if k in base.get("params", {})}}
    changed = ", ".join(f"{k} = {v}" for k, v in (data.get("werte") or {}).items() if base.get("werte", {}).get(k) != v)
    try:
        v = await build_version(request.app, p, source, values, "parameter", f"Parameter: {changed or 'unverändert'}")
    except cad.ScriptError as err:
        raise Fail(f"Mit diesen Werten geht es nicht: {err}", 422)
    return web.json_response({**v, "zusammenfassung": summary(v)})


async def chat_job(app: web.Application, pid: str, text: str) -> None:
    st: Store = app["store"]
    busy = app["busy"]
    try:
        p = st.get(pid)
        last = next((v for v in reversed(p["versionen"]) if v.get("ok")), None)
        script = (st.vdir(pid, last["n"]) / "skript.py").read_text(encoding="utf-8") if last else ""
        error, tried = "", script
        for attempt in range(3):
            busy[pid] = "Claude konstruiert …" if attempt == 0 else f"Claude korrigiert ({attempt + 1}. Versuch) …"
            answer = await asyncio.to_thread(designer.ask, designer.prompt_for(st.get(pid), text, tried, last, error))
            p = st.get(pid)
            if answer.get("name"):
                p["name"] = str(answer["name"]).strip()[:80] or p["name"]
                st.save(p)
            source = str(answer.get("skript") or "")
            if not source.strip():
                st.chat(p, "claude", str(answer.get("antwort") or "…"))
                st.save(p)
                return
            busy[pid] = "FreeCAD rechnet …"
            try:
                v = await build_version(app, p, source, {}, "claude", text)
            except cad.ScriptError as err:
                error, tried = str(err), source
                continue
            p = st.get(pid)
            st.chat(p, "claude", f"{answer.get('antwort') or ''}\n\n{summary(v)}".strip(), version=v["n"])
            st.save(p)
            return
        p = st.get(pid)
        st.chat(p, "claude", f"Das hat nach drei Versuchen nicht geklappt. Letzter Fehler: {error}")
        st.save(p)
    except designer.DesignError as err:
        p = st.get(pid)
        st.chat(p, "claude", f"⚠️ {err}")
        st.save(p)
    except Exception as err:  # noqa: BLE001
        log.exception("Chat")
        p = st.get(pid)
        st.chat(p, "claude", f"⚠️ Fehler: {str(err)[:300]}")
        st.save(p)
    finally:
        busy.pop(pid, None)


@routes.post("/api/projekte/{id}/chat")
async def api_chat(request: web.Request) -> web.Response:
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request)
    text = str(data.get("text") or "").strip()[:4000]
    if not text:
        raise Fail("Was soll Claude konstruieren?")
    if request.app["busy"].get(p["id"]):
        raise Fail("Claude arbeitet gerade an diesem Projekt – kurz warten", 409)
    st.chat(p, "du", text)
    st.save(p)
    request.app["busy"][p["id"]] = "Claude denkt nach …"
    asyncio.create_task(chat_job(request.app, p["id"], text))
    return web.json_response({"ok": True})


@routes.post("/api/projekte/{id}/masse")
async def api_add_measure(request: web.Request) -> web.Response:
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request)
    try:
        value = round(float(data.get("wert_mm")), 2)
    except (TypeError, ValueError):
        raise Fail("Maß in mm angeben")
    name = str(data.get("name") or "").strip()[:80] or "Maß"
    p["masse"].append({"name": name, "wert_mm": value, "quelle": str(data.get("quelle") or "eingegeben")[:120]})
    st.save(p)
    return web.json_response(p["masse"])


@routes.delete("/api/projekte/{id}/masse/{i}")
async def api_del_measure(request: web.Request) -> web.Response:
    st = store(request)
    p = st.get(request.match_info["id"])
    i = int(request.match_info["i"])
    if 0 <= i < len(p["masse"]):
        p["masse"].pop(i)
        st.save(p)
    return web.json_response(p["masse"])


VERSION_FILES = {"vorschau.png": "image/png", "modell.step": "application/step", "skript.py": "text/x-python",
                 "druck.stl": "model/stl", "druck.zip": "application/zip"}


@routes.get("/api/projekte/{id}/v/{n}/{file}")
async def api_version_file(request: web.Request) -> web.Response:
    st = store(request)
    p = st.get(request.match_info["id"])
    v = st.version(p, int(request.match_info["n"]))
    name = request.match_info["file"]
    folder = st.vdir(p["id"], v["n"])
    if name.startswith("teil-") and name.endswith(".stl"):
        path = folder / "teile" / name[5:]
        ctype = "model/stl"
    elif name in VERSION_FILES:
        path, ctype = folder / name, VERSION_FILES[name]
    else:
        raise web.HTTPNotFound()
    if not path.exists() or ".." in name:
        raise web.HTTPNotFound()
    download = request.query.get("download")
    headers = {"Content-Disposition": f'attachment; filename="{re.sub(r"[^A-Za-z0-9_.-]", "_", p["name"])}-v{v["n"]}-{name}"'} if download else {}
    return web.Response(body=path.read_bytes(), content_type=ctype, headers=headers)


@routes.get("/dl/{token}/{name}")
async def download_for_printer(request: web.Request) -> web.Response:
    found = store(request).by_token(request.match_info["token"])
    if not found:
        raise web.HTTPNotFound()
    p, v = found
    path = store(request).vdir(p["id"], v["n"]) / v["druckdatei"]
    return web.Response(body=path.read_bytes(), content_type="application/octet-stream")


# -- photos and measuring ------------------------------------------------------------------------------------------------
def reference_args(q) -> tuple[str, tuple | None]:
    kind = str(q.get("referenz") or REFERENCE).lower()
    custom = None
    if q.get("breite") and q.get("hoehe"):
        try:
            custom = (float(q["breite"]), float(q["hoehe"]))
            kind = "eigen"
        except ValueError:
            raise Fail("Eigene Referenz: Breite und Höhe in mm")
    return kind, custom


@routes.post("/api/fotos")
async def api_photo(request: web.Request) -> web.Response:
    """A photo with a reference (A4 sheet, card …): straightened, with the object's size."""
    st = store(request)
    data = await request.read()
    if not data or len(data) > MAX_PHOTO:
        raise Fail("Bild fehlt oder ist zu groß (max. 25 MB)")
    kind, custom = reference_args(request.query)
    fid, folder = st.new_photo()
    st.photo_meta(fid, name=str(request.query.get("name") or "")[:80], referenz_art=kind, erstellt=now_iso())
    (folder / "upload.bin").write_bytes(data)
    pid = request.query.get("projekt")
    if pid:
        p = st.get(pid)
        p["fotos"].append(fid)
        st.save(p)
    try:
        result = await asyncio.to_thread(measure.measure, data, kind if kind != "eigen" else "a4", folder, None, custom)
    except measure.MeasureError as err:
        raise Fail(str(err), 422, foto=fid, ecken_noetig=True)
    return web.json_response({"id": fid, **result})


@routes.post("/api/fotos/{fid}/ecken")
async def api_photo_corners(request: web.Request) -> web.Response:
    """The four corners of the reference, tapped by hand (pixels of original.jpg)."""
    st = store(request)
    fid = request.match_info["fid"]
    folder = st.photo_dir(fid)
    data = await body_of(request)
    corners = data.get("ecken")
    if not isinstance(corners, list) or len(corners) != 4:
        raise Fail("Genau vier Ecken angeben")
    kind, custom = reference_args(data)
    img = (folder / "original.jpg").read_bytes()
    try:
        result = await asyncio.to_thread(measure.measure, img, kind if kind != "eigen" else "a4", folder, corners, custom)
    except measure.MeasureError as err:
        raise Fail(str(err), 422)
    return web.json_response({"id": fid, **result})


@routes.get("/api/fotos/{fid}")
async def api_photo_info(request: web.Request) -> web.Response:
    return web.json_response(store(request).photo(request.match_info["fid"]))


@routes.get("/api/fotos/{fid}/{name}")
async def api_photo_file(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    if name not in ("original.jpg", "entzerrt.jpg", "entzerrt-roh.jpg"):
        raise web.HTTPNotFound()
    path = store(request).photo_dir(request.match_info["fid"]) / name
    if not path.exists():
        raise web.HTTPNotFound()
    return web.Response(body=path.read_bytes(), content_type="image/jpeg")


# -- showing and printing ------------------------------------------------------------------------------------------------
def notify(text: str, image: bytes | None = None) -> bool:
    return fabians_master.notify(text, image, "werkbank.jpg")


@routes.post("/api/projekte/{id}/zeigen")
async def api_show(request: web.Request) -> web.Response:
    """Sends the preview of a version to the owner's phone."""
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request) if request.can_read_body else {}
    v = st.version(p, data.get("version"))
    text = str(data.get("text") or "").strip() or f"🛠️ {p['name']} – {summary(v)}"
    sent = await asyncio.to_thread(notify, text[:900], jpeg(st.vdir(p["id"], v["n"]) / "vorschau.png"))
    return web.json_response({"gesendet": sent, "version": v["n"]})


def save_pending(app: web.Application, data: dict | None) -> None:
    app["pending"]["data"] = data
    path = DATA / "druckauftrag.json"
    if data:
        path.write_text(json.dumps(data, ensure_ascii=False))
    elif path.exists():
        path.unlink()


def pending(app: web.Application) -> dict | None:
    data = app["pending"].get("data")
    if data and time.time() - data["seit"] > PENDING_HOURS * 3600:
        save_pending(app, None)
        return None
    return data


@routes.post("/api/projekte/{id}/drucken")
async def api_print_prepare(request: web.Request) -> web.Response:
    """Slices the version in Fabians-HA-3D-Druck and sends picture, time and filament by iMessage. Printing only
    starts after the confirmation (POST /api/druck/bestaetigen – from the dashboard or by the assistant)."""
    st = store(request)
    p = st.get(request.match_info["id"])
    data = await body_of(request) if request.can_read_body else {}
    v = st.version(p, data.get("version"))
    if not v.get("ok"):
        raise Fail("Diese Version ist nicht druckbar")
    big = [w for w in v["warnungen"] if "Zu groß" in w]
    if big:
        raise Fail(big[0])
    material = str(data.get("material") or p.get("material") or MATERIAL).upper()
    suffix = Path(v["druckdatei"]).suffix
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", p["name"]).strip("-")[:40] or "teil"
    link = f"http://{socket.gethostname()}:{PORT}/dl/{v['token']}/{safe}-v{v['n']}{suffix}"
    body = {"model": link, "material": material, "supports": bool(data.get("stuetzen")), "orient": False}
    request.app["busy"][p["id"]] = "Wird für den Drucker vorbereitet (slicen) …"
    try:
        async with request.app["http"].post(DRUCK_URL + "/api/prepare", json=body, timeout=aiohttp.ClientTimeout(total=1200)) as resp:
            job = await resp.json(content_type=None)
            if resp.status >= 300:
                raise Fail(f"3D-Druck: {job.get('error') or resp.status}", 502)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise Fail(f"Fabians-HA-3D-Druck nicht erreichbar ({DRUCK_URL}) – installiert und gestartet?", 503) from err
    finally:
        request.app["busy"].pop(p["id"], None)
    info = {"projekt": p["id"], "name": p["name"], "version": v["n"], "job": job.get("id"), "zeit": job.get("time"),
            "gewicht_g": job.get("weight_g"), "material": material, "warnung": job.get("warning"), "seit": time.time()}
    save_pending(request.app, info)
    text = (f"🖨️ {p['name']} (Version {v['n']}) ist bereit: {info['zeit'] or '?'}, ca. {info['gewicht_g'] or '?'} g {material}."
            + (f"\n⚠️ {info['warnung']}" if info["warnung"] else "") + "\nSoll ich drucken? Antworte „Ja“ – die Druckplatte muss frei sein.")
    if not data.get("ohne_nachricht"):
        info["gesendet"] = await asyncio.to_thread(notify, text, jpeg(st.vdir(p["id"], v["n"]) / "vorschau.png"))
    p = st.get(p["id"])
    st.chat(p, "claude", f"Für den Drucker vorbereitet: {info['zeit']}, {info['gewicht_g']} g {material}. Wartet auf Bestätigung.", version=v["n"])
    st.save(p)
    return web.json_response(info)


@routes.get("/api/druck")
async def api_pending(request: web.Request) -> web.Response:
    return web.json_response(pending(request.app))


@routes.post("/api/druck/bestaetigen")
async def api_print_confirm(request: web.Request) -> web.Response:
    info = pending(request.app)
    if not info:
        raise Fail("Es wartet kein Druck auf Bestätigung", 404)
    try:
        async with request.app["http"].post(DRUCK_URL + "/api/print", json={"job": info["job"]},
                                            timeout=aiohttp.ClientTimeout(total=120)) as resp:
            result = await resp.json(content_type=None)
            if resp.status >= 300:
                raise Fail(f"3D-Druck: {result.get('error') or resp.status}", 502)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise Fail(f"Fabians-HA-3D-Druck nicht erreichbar ({DRUCK_URL})", 503) from err
    save_pending(request.app, None)
    st = store(request)
    try:
        p = st.get(info["projekt"])
        st.chat(p, "claude", f"🖨️ Druck gestartet (Version {info['version']}).", version=info["version"])
        st.save(p)
    except NotFound:
        pass
    return web.json_response({"gestartet": True, **result})


@routes.post("/api/druck/abbrechen")
async def api_print_cancel(request: web.Request) -> web.Response:
    save_pending(request.app, None)
    return web.json_response({"ok": True})


# -- start ------------------------------------------------------------------------------------------------------------------
async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession()
    app["store"] = Store(DATA)
    app["cad_lock"] = asyncio.Lock()
    app["busy"] = {}
    app["pending"] = {}
    try:
        app["pending"]["data"] = json.loads((DATA / "druckauftrag.json").read_text())
    except (OSError, ValueError):
        pass
    await asyncio.to_thread(app["store"].clean_photos)
    log.info("Werkbank bereit: %d Projekte, 3D-Druck unter %s", len(app["store"].list()), DRUCK_URL)


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()


def make_app() -> web.Application:
    app = web.Application(middlewares=[guard], client_max_size=MAX_PHOTO + 1024 * 1024)
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    # IPv4 only: callers are checked by their IPv4 address (the add-on network also has IPv6).
    web.run_app(make_app(), host="0.0.0.0", port=PORT, print=None, access_log=None)
