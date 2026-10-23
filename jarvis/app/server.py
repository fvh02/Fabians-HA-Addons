"""Fabians-HA-Jarvis: a voice assistant on the projector, in the style of J.A.R.V.I.S.

The projector (Android app = full-screen browser) shows the HUD; you speak into the phone (remote page) or the
projector's microphone. Speech becomes text here (faster-whisper), the assistant answers with all its tools
(through Fabians-HA-Master → Fabians-HA-Assistent), and the answer is spoken here (Piper) and played on the
projector. HUD and remote get every change live (server-sent events).

Access: through Home Assistant (ingress) or – for the projector in the home network – port 8107 with a token
that the app gets once with a 6-digit pairing code.
"""

import asyncio
import hmac
import json
import logging
import os
import re
import secrets
import socket
import time
from pathlib import Path

import aiohttp
from aiohttp import web

import fabians_master
import speech

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("jarvis")

DATA = Path(os.environ.get("JARVIS_DATA", "/data"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("JARVIS_PORT", "8107"))
INGRESS_IP = "172.30.32.2"
SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor")
SESSION_IDLE = 15 * 60
APK_URL = "https://github.com/fvh02/Fabians-HA-Addons/releases/download/jarvis-app/jarvis.apk"


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPT = load_options()
ANREDE = str(OPT.get("anrede") or "Sir").strip()[:30]
SYSTEM = f"""Du sprichst gerade als J.A.R.V.I.S. mit der Person – per Sprache, über den Beamer im Wohnzimmer
(Fabians-HA-Jarvis). Deine Antwort wird vorgelesen und groß an die Wand projiziert:
- kurz: meist 1–3 Sätze, keine Aufzählungen, kein Markdown, keine Emojis, keine Links;
- Zahlen, Uhrzeiten und Einheiten so, dass man sie gut vorlesen kann;
- im Stil von J.A.R.V.I.S.: souverän, höflich, mit trockenem britischen Humor; sprich die Person mit „{ANREDE}“ an.
Du hast alle deine Werkzeuge (Smarthome mit `haus`, alle Add-ons, Kalender, Gedächtnis, Pakete …): erledige Aufgaben
direkt und sag kurz, was du getan hast. Wenn du nachfragen oder eine Bestätigung brauchst (z. B. vor einem Druck),
frag kurz – die Person antwortet per Sprache im selben Gespräch. Bilder kannst du hier nicht zeigen: beschreibe kurz,
oder schick sie, wenn es passt, zusätzlich per iMessage."""


class Fail(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


# -- tokens and pairing ------------------------------------------------------------------------------------------
class Access:
    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("geraete", [])
        if not self.data.get("code"):
            self.new_code()
        self.attempts: list[float] = []

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data))

    def new_code(self) -> str:
        self.data["code"] = f"{secrets.randbelow(1_000_000):06d}"
        self.save()
        return self.data["code"]

    def pair(self, code: str, name: str) -> str:
        now = time.time()
        self.attempts = [t for t in self.attempts if now - t < 600]
        if len(self.attempts) >= 10:
            raise Fail("Zu viele Versuche – in 10 Minuten wieder", 429)
        self.attempts.append(now)
        if not hmac.compare_digest(str(code).strip(), self.data["code"]):
            raise Fail("Falscher Code", 403)
        token = secrets.token_urlsafe(32)
        self.data["geraete"].append({"name": (name or "Gerät")[:40], "token": token, "seit": int(now)})
        self.new_code()            # every code works once
        return token

    def valid(self, token: str) -> bool:
        return bool(token) and any(hmac.compare_digest(token, d["token"]) for d in self.data["geraete"])

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.data["geraete"]):
            self.data["geraete"].pop(index)
            self.save()


OPEN_PATHS = ("/static/", "/api/koppeln", "/api/ping")


@web.middleware
async def guard(request: web.Request, handler):
    if request.remote == INGRESS_IP or os.environ.get("JARVIS_OPEN") == "1":
        request["ingress"] = request.remote == INGRESS_IP
    elif not request.path.startswith(OPEN_PATHS):
        token = request.query.get("t") or request.headers.get("X-Jarvis-Token", "")
        if not request.app["access"].valid(token):
            if request.path in ("/", "/hud", "/fernbedienung"):
                return web.Response(text="Nicht gekoppelt – Kopplungscode in Home Assistant unter Jarvis.", status=403)
            return web.json_response({"error": "Nicht gekoppelt"}, status=403)
    try:
        return await handler(request)
    except Fail as err:
        return web.json_response({"error": str(err)}, status=err.status)


routes = web.RouteTableDef()


# -- live state -----------------------------------------------------------------------------------------------------
class Hub:
    """The conversation state; every change goes to all open HUDs and remotes."""

    def __init__(self):
        self.state = {"modus": "bereit", "frage": "", "antwort": "", "aktionen": [], "audio": "", "dauer": 0,
                      "fehler": "", "verlauf": [], "assistent": "unbekannt"}
        self.queues: set[asyncio.Queue] = set()
        self.session = ""
        self.session_at = 0.0
        self.busy = False

    def update(self, **values) -> None:
        self.state.update(values, zeit=time.time())
        for q in list(self.queues):
            if q.qsize() < 50:
                q.put_nowait({"typ": "zustand", **self.state})

    def send(self, event: dict) -> None:
        for q in list(self.queues):
            q.put_nowait(event)


@routes.get("/api/ereignisse")
async def api_events(request: web.Request) -> web.StreamResponse:
    hub: Hub = request.app["hub"]
    resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    await resp.prepare(request)
    q: asyncio.Queue = asyncio.Queue()
    hub.queues.add(q)
    q.put_nowait({"typ": "zustand", **hub.state})
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=15)
                await resp.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
            except asyncio.TimeoutError:
                await resp.write(b": ping\n\n")
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        hub.queues.discard(q)
    return resp


# -- the conversation ------------------------------------------------------------------------------------------------
RESET = re.compile(r"^(neues gespräch|vergiss (das|alles)|von vorne)\W*$", re.I)
STOP = re.compile(r"^(stopp?|stop|sei still|ruhe|halt)\W*$", re.I)


async def ask_assistant(app: web.Application, text: str) -> dict:
    hub: Hub = app["hub"]
    session = hub.session if time.time() - hub.session_at < SESSION_IDLE else ""
    body = {"prompt": text, "session": session, "system": SYSTEM}
    try:
        return await asyncio.to_thread(fabians_master._call, "POST", "/api/agent", body, 1000)
    except fabians_master.MasterError as err:
        return {"error": str(err)}


async def say(app: web.Application, text: str, **extra) -> None:
    """Speaks the text; the HUD plays it and shows it while speaking."""
    hub: Hub = app["hub"]
    spoken = speech.speakable(text)
    audio, seconds = "", 0.0
    if spoken:
        try:
            wav, seconds = await asyncio.to_thread(app["voice"].speak, spoken)
            name = f"{int(time.time() * 1000)}-{secrets.token_hex(3)}.wav"
            (DATA / "audio" / name).write_bytes(wav)
            audio = f"audio/{name}"
            for old in sorted((DATA / "audio").glob("*.wav"))[:-20]:
                old.unlink(missing_ok=True)
        except Exception as err:  # noqa: BLE001 – without a voice Jarvis still shows the answer
            log.warning("Sprachausgabe: %s", err)
    hub.update(modus="spricht" if audio else "bereit", antwort=text, audio=audio, dauer=round(seconds, 2), **extra)
    if audio:
        await asyncio.sleep(seconds + 0.8)
        if hub.state.get("audio") == audio:
            hub.update(modus="bereit")


async def handle(app: web.Application, text: str, source: str) -> None:
    hub: Hub = app["hub"]
    text = text.strip()[:2000]
    if STOP.match(text):
        hub.send({"typ": "stopp"})
        hub.update(modus="bereit", audio="")
        return
    if RESET.match(text):
        hub.session = ""
        await say(app, f"Wie Sie wünschen, {ANREDE}. Wir fangen von vorne an.", frage=text, aktionen=[], fehler="")
        return
    if hub.busy:
        hub.send({"typ": "hinweis", "text": "Einen Moment – ich bin noch bei der letzten Frage."})
        return
    hub.busy = True
    try:
        hub.update(modus="denkt", frage=text, antwort="", aktionen=[], audio="", fehler="", quelle=source)
        result = await ask_assistant(app, text)
        if result.get("error") and not result.get("text"):
            hub.update(assistent="fehler")
            log.warning("Assistent: %s", result["error"])
            await say(app, f"Verzeihung, {ANREDE}, ich erreiche den Assistenten gerade nicht.", fehler=str(result["error"])[:300])
            return
        hub.session, hub.session_at = result.get("session") or hub.session, time.time()
        actions = [a.get("detail") or a.get("tool") for a in result.get("tools") or [] if a.get("tool") != "Read"][-8:]
        answer = re.sub(r"\*\*|__|`+|^#+\s*", "", str(result.get("text") or ""), flags=re.M).strip() or f"Erledigt, {ANREDE}."
        hub.state["verlauf"] = ([{"frage": text, "antwort": answer, "zeit": time.time()}] + hub.state["verlauf"])[:20]
        await say(app, answer, aktionen=actions, assistent="verbunden")
    finally:
        hub.busy = False


@routes.post("/api/frage")
async def api_question(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except ValueError:
        raise Fail("JSON erwartet")
    text = str(data.get("text") or "").strip()
    if not text:
        raise Fail("Was möchtest du wissen?")
    asyncio.create_task(handle(request.app, text, str(data.get("quelle") or "text")))
    return web.json_response({"ok": True})


@routes.post("/api/sprache")
async def api_speech(request: web.Request) -> web.Response:
    """A recording (webm/ogg/wav/m4a) from the phone or the projector's microphone."""
    audio = await request.read()
    if len(audio) > 15 * 1024 * 1024:
        raise Fail("Aufnahme zu lang")
    ctype = request.headers.get("Content-Type", "")
    suffix = ".wav" if "wav" in ctype else ".ogg" if "ogg" in ctype else ".m4a" if "mp4" in ctype or "aac" in ctype else ".webm"
    hub: Hub = request.app["hub"]
    hub.update(modus="versteht", frage="", antwort="", aktionen=[], audio="")
    try:
        text = await asyncio.to_thread(request.app["ears"].transcribe, audio, suffix)
    except speech.SpeechError as err:
        hub.update(modus="bereit", fehler=str(err))
        raise Fail(str(err), 422)
    if not text:
        hub.update(modus="bereit")
        hub.send({"typ": "hinweis", "text": "Ich habe nichts verstanden."})
        return web.json_response({"text": ""})
    asyncio.create_task(handle(request.app, text, str(request.query.get("quelle") or "sprache")))
    return web.json_response({"text": text})


@routes.post("/api/hoert")
async def api_listening(request: web.Request) -> web.Response:
    """The HUD or the phone records: show it on all screens and stop any speech."""
    data = await request.json() if request.can_read_body else {}
    hub: Hub = request.app["hub"]
    if data.get("an"):
        hub.send({"typ": "stopp"})
        hub.update(modus="hoert", audio="")
    elif hub.state["modus"] == "hoert":
        hub.update(modus="bereit")
    return web.json_response({"ok": True})


@routes.post("/api/stopp")
async def api_stop(request: web.Request) -> web.Response:
    hub: Hub = request.app["hub"]
    hub.send({"typ": "stopp"})
    if hub.state["modus"] == "spricht":
        hub.update(modus="bereit", audio="")
    return web.json_response({"ok": True})


@routes.post("/api/neu")
async def api_new(request: web.Request) -> web.Response:
    hub: Hub = request.app["hub"]
    hub.session = ""
    hub.update(frage="", antwort="", aktionen=[], verlauf=[], modus="bereit")
    return web.json_response({"ok": True})


@routes.get("/audio/{name}")
async def audio_file(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    path = DATA / "audio" / name
    if not re.match(r"^[0-9a-f-]+\.wav$", name) or not path.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "no-store"})


# -- pages and setup ---------------------------------------------------------------------------------------------------
def page(name: str) -> web.FileResponse:
    return web.FileResponse(STATIC / name, headers={"Cache-Control": "no-cache"})


@routes.get("/")
async def index(request: web.Request) -> web.Response:
    return page("index.html" if request.get("ingress") or os.environ.get("JARVIS_OPEN") == "1" else "hud.html")


@routes.get("/hud")
async def hud(_: web.Request) -> web.Response:
    return page("hud.html")


@routes.get("/fernbedienung")
async def remote(_: web.Request) -> web.Response:
    return page("fernbedienung.html")


@routes.get("/static/{name}")
async def static(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    if not re.match(r"^[a-z0-9_-]+\.(js|css|svg)$", name) or not (STATIC / name).exists():
        raise web.HTTPNotFound()
    return page(name)


@routes.get("/api/ping")
async def api_ping(_: web.Request) -> web.Response:
    return web.json_response({"jarvis": True})


@routes.post("/api/koppeln")
async def api_pair(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except ValueError:
        raise Fail("JSON erwartet")
    token = request.app["access"].pair(str(data.get("code") or ""), str(data.get("name") or "Beamer"))
    return web.json_response({"token": token})


async def host_addresses(app: web.Application) -> list[str]:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        return []
    try:
        async with app["http"].get(f"{SUPERVISOR}/network/info", headers={"Authorization": f"Bearer {token}"},
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
            info = (await resp.json()).get("data", {})
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return []
    out = []
    for iface in info.get("interfaces", []):
        for addr in (iface.get("ipv4") or {}).get("address") or []:
            ip = addr.split("/")[0]
            if not ip.startswith(("127.", "172.30.", "172.17.")):
                out.append(ip)
    return out


@routes.get("/api/einrichtung")
async def api_setup(request: web.Request) -> web.Response:
    if not request.get("ingress") and os.environ.get("JARVIS_OPEN") != "1":
        raise Fail("Nur in Home Assistant", 403)
    access: Access = request.app["access"]
    return web.json_response({"code": access.data["code"], "port": PORT, "adressen": await host_addresses(request.app),
                              "geraete": [{"name": d["name"], "seit": d["seit"]} for d in access.data["geraete"]],
                              "apk": APK_URL, "anrede": ANREDE, "zustand": request.app["hub"].state["modus"]})


@routes.post("/api/einrichtung/code")
async def api_new_code(request: web.Request) -> web.Response:
    if not request.get("ingress") and os.environ.get("JARVIS_OPEN") != "1":
        raise Fail("Nur in Home Assistant", 403)
    return web.json_response({"code": request.app["access"].new_code()})


@routes.delete("/api/einrichtung/geraet/{i}")
async def api_remove_device(request: web.Request) -> web.Response:
    if not request.get("ingress") and os.environ.get("JARVIS_OPEN") != "1":
        raise Fail("Nur in Home Assistant", 403)
    request.app["access"].remove(int(request.match_info["i"]))
    return web.json_response({"ok": True})


# -- start -----------------------------------------------------------------------------------------------------------------
async def warm_up(app: web.Application) -> None:
    """Load the models in the background so the first question is quick."""
    for name, fn in (("Stimme", app["voice"].load), ("Spracherkennung", app["ears"].load)):
        try:
            await asyncio.to_thread(fn)
            log.info("%s bereit", name)
        except Exception as err:  # noqa: BLE001
            log.warning("%s nicht geladen: %s", name, err)


async def on_startup(app: web.Application) -> None:
    (DATA / "audio").mkdir(parents=True, exist_ok=True)
    app["http"] = aiohttp.ClientSession()
    app["access"] = Access(DATA / "jarvis.json")
    app["hub"] = Hub()
    app["ears"] = speech.Ears(str(OPT.get("spracherkennung") or "base"))
    app["voice"] = speech.Voice(str(OPT.get("stimme") or "de_DE-thorsten-medium"), float(OPT.get("sprechtempo") or 1.0))
    app["warm"] = asyncio.create_task(warm_up(app))
    log.info("Jarvis bereit auf Port %d – Kopplungscode %s (in Home Assistant unter Jarvis)", PORT, app["access"].data["code"])


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()


def make_app() -> web.Application:
    app = web.Application(middlewares=[guard], client_max_size=16 * 1024 * 1024)
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    socket.setdefaulttimeout(None)
    # IPv4 only: the master and Home Assistant check callers by their IPv4 address.
    web.run_app(make_app(), host="0.0.0.0", port=PORT, print=None, access_log=None)
