"""Spieleabend add-on: multiplayer card games with a shared lobby, rooms and computer players."""

import asyncio
import hashlib
import hmac
from html import escape
import json
import logging
import os
import random
import secrets
import string
import time
from pathlib import Path

from aiohttp import WSMsgType, web

import farbrausch
import galgenraten
import imposter
import kritzelpost
import luegenbaron
import nochnie
import pferderennen
import punchline
import pyramide
import ringoffire
import schaetzmeister
import schnellmaler
import stapeljagd
import tiefpunkt
import trinklotto
import wahrheit
import werwuerde
import fabians_master
from common import RuleError

OPTIONS_FILE = Path("/data/options.json")
STATIC_DIR = Path(__file__).parent / "static"
PORT = int(os.environ.get("SPIELE_PORT", "8098"))
BOT_DELAY = float(os.environ.get("SPIELE_BOT_DELAY", "0.9"))
BOT_NAMES = ["Robo", "Karla", "Bitty", "Otto", "Zora", "Pixel", "Toni", "Mops"]
GAME_TTL = 6 * 3600  # remove games nobody has touched for this long

GAMES = {"stapeljagd": stapeljagd, "tiefpunkt": tiefpunkt, "kritzelpost": kritzelpost, "farbrausch": farbrausch, "schnellmaler": schnellmaler,
         "galgenraten": galgenraten, "imposter": imposter, "schaetzmeister": schaetzmeister, "werwuerde": werwuerde,
         "luegenbaron": luegenbaron, "punchline": punchline, "nochnie": nochnie, "wahrheit": wahrheit, "ringoffire": ringoffire,
         "trinklotto": trinklotto, "pyramide": pyramide, "pferderennen": pferderennen}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("spieleabend")


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except (OSError, ValueError):
        return {}


OPTIONS = load_options()
THEME = os.environ.get("SPIELE_THEME") or OPTIONS.get("theme") or "dark"
if THEME not in ("dark", "light"):
    THEME = "dark"
# Optional code that people outside Home Assistant enter once (e.g. when the games are on the internet).
# The access code comes from Fabians-HA-Master; without one, requests from the internet are refused.
ACCESS_CODE = str(os.environ["SPIELE_ACCESS_CODE"] if "SPIELE_ACCESS_CODE" in os.environ
                  else fabians_master.keys(wait=90).get("games_code") or "").strip()
CODE_COOKIE = "spieleabend_zugang"
CODE_TOKEN = hashlib.sha256(f"spieleabend:{ACCESS_CODE}".encode()).hexdigest() if ACCESS_CODE else ""
# Home Assistant's Ingress proxy: the person is already logged in to Home Assistant.
INGRESS_IPS = set((os.environ.get("SPIELE_INGRESS_IPS") or "172.30.32.2").split(","))
OPEN_PATHS = ("/static/", "/manifest.webmanifest", "/sw.js", "/__login")

# Limits against abuse once the games are reachable from the internet.
MAX_ROOMS = 40              # per game
MAX_SOCKETS_PER_IP = 30
MSG_RATE, MSG_BURST = 15.0, 60.0  # WebSocket messages per second (sustained, burst)
LOGIN_TRIES, LOGIN_WINDOW = 8, 900


class Hub:
    """All rooms of one game kind, the browsers connected to them and their bots."""

    def __init__(self, module) -> None:
        self.module = module
        self.games: dict = {}
        self.touched: dict[str, float] = {}
        # Each browser keeps a token; it maps to (room code, player id) so a reload rejoins.
        self.seats: dict[str, tuple[str, str]] = {}
        self.sockets: dict[web.WebSocketResponse, str] = {}
        self.bot_tasks: dict[str, asyncio.Task] = {}
        self.timers: dict[str, float] = {}  # room code -> deadline a timer task waits for
        self.timer_tasks: set[asyncio.Task] = set()  # keep references so tasks aren't collected

    # -- sending -------------------------------------------------------------
    @staticmethod
    async def send(ws: web.WebSocketResponse, message: dict) -> None:
        if not ws.closed:
            try:
                await ws.send_json(message)
            except (ConnectionError, RuntimeError):
                pass

    def open_games(self) -> list[dict]:
        return [
            {"code": g.code, "state": g.state, "players": [p.name for p in g.players],
             "full": len(g.players) >= self.module.MAX_PLAYERS}
            for g in self.games.values() if g.players
        ]

    async def send_view(self, ws: web.WebSocketResponse) -> None:
        token = self.sockets.get(ws)
        seat = self.seats.get(token)
        game = self.games.get(seat[0]) if seat else None
        if game and game.player(seat[1]):
            await self.send(ws, {"t": "game", "me": seat[1], "game": game.view_for(seat[1])})
        else:
            self.seats.pop(token, None)
            await self.send(ws, {"t": "lobby", "games": self.open_games()})

    async def broadcast(self, code: str | None = None) -> None:
        """Update every browser in room `code` and everyone in the lobby."""
        if code:
            self.touched[code] = time.time()
        for ws, token in list(self.sockets.items()):
            seat = self.seats.get(token)
            if seat is None or seat[0] == code:
                await self.send_view(ws)
        if code:
            self.schedule_bots(code)
            self.schedule_timer(code)

    # -- bots ----------------------------------------------------------------
    def schedule_bots(self, code: str) -> None:
        game = self.games.get(code)
        task = self.bot_tasks.get(code)
        if game and game.pending_bots() and (task is None or task.done()):
            self.bot_tasks[code] = asyncio.create_task(self.run_bots(code))

    async def run_bots(self, code: str) -> None:
        while True:
            await asyncio.sleep(BOT_DELAY)
            game = self.games.get(code)
            bots = game.pending_bots() if game else []
            if not bots:
                return
            try:
                game.bot_step(bots[0])
            except RuleError as err:  # should not happen; never let a bot freeze a room
                log.warning("Bot %s in %s: %s", bots[0].name, code, err)
                return
            await self.broadcast(code)

    # -- timers (games with a `deadline`) -------------------------------------
    def schedule_timer(self, code: str) -> None:
        game = self.games.get(code)
        deadline = getattr(game, "deadline", None) if game else None
        if deadline is None or self.timers.get(code) == deadline:
            return
        self.timers[code] = deadline
        task = asyncio.create_task(self.run_timer(code, deadline))
        self.timer_tasks.add(task)
        task.add_done_callback(self.timer_tasks.discard)

    async def run_timer(self, code: str, deadline: float) -> None:
        await asyncio.sleep(max(0.0, deadline - time.time()))
        game = self.games.get(code)
        # A newer deadline (next step) replaced this one: nothing to do.
        if game and getattr(game, "deadline", None) == deadline:
            game.on_deadline()
            await self.broadcast(code)

    # -- actions -------------------------------------------------------------
    def new_code(self) -> str:
        letters = string.ascii_uppercase.replace("O", "").replace("I", "")
        while True:
            code = "".join(random.choices(letters, k=4))
            if code not in self.games:
                return code

    def leave(self, token: str) -> str | None:
        seat = self.seats.pop(token, None)
        if not seat:
            return None
        code, player_id = seat
        game = self.games.get(code)
        if not game:
            return None
        player = game.player(player_id)
        if game.state == "playing" and player:
            # Keep the game going: a computer player takes over the seat.
            player.is_bot = True
            player.name += " (Bot)"
            game.note(f"{player.name} spielt jetzt für den Spieler weiter")
            if game.host_id == player_id:
                game.host_id = next((p.id for p in game.players if not p.is_bot), None)
        else:
            game.remove_player(player_id)
        if not any(not p.is_bot for p in game.players):
            self.games.pop(code, None)
            return None
        return code

    async def handle(self, ws: web.WebSocketResponse, token: str, msg: dict) -> None:
        kind = msg.get("t")
        seat = self.seats.get(token)
        game = self.games.get(seat[0]) if seat else None
        me = seat[1] if seat else None
        name = str(msg.get("name", "")).strip()[:20]

        if kind in ("create", "join"):
            if not name:
                raise RuleError("Bitte gib deinen Namen ein")
            if seat:
                self.leave(token)
            if kind == "create":
                if len(self.games) >= MAX_ROOMS:
                    raise RuleError("Gerade gibt es zu viele Spiele – bitte später noch einmal versuchen")
                game = self.module.Game(self.new_code())
                game.configure(msg.get("settings") or {})
                self.games[game.code] = game
            else:
                game = self.games.get(str(msg.get("code", "")).strip().upper())
                if not game:
                    raise RuleError("Dieses Spiel gibt es nicht")
            player = game.new_player(name)
            game.add_player(player)
            self.seats[token] = (game.code, player.id)
            await self.broadcast(game.code)
            return

        if not game:
            if kind == "lobby":
                await self.send(ws, {"t": "lobby", "games": self.open_games()})
                return
            raise RuleError("Du bist in keinem Spiel")

        is_host = game.host_id == me
        if kind == "leave":
            code = self.leave(token)
            await self.broadcast(code)
            await self.send(ws, {"t": "lobby", "games": self.open_games()})
            return
        if kind == "add_bot":
            if not is_host:
                raise RuleError("Nur der Gastgeber kann Computer-Spieler hinzufügen")
            used = {p.name for p in game.players}
            bot_name = next((n for n in BOT_NAMES if n not in used), f"Bot {len(game.players) + 1}")
            if getattr(game, "NO_BOTS", False):
                raise RuleError("In diesem Spiel gibt es keine Computer-Spieler")
            game.add_player(game.new_player(bot_name, is_bot=True))
        elif kind == "kick":
            if not is_host or game.state != "lobby":
                raise RuleError("Nur der Gastgeber kann vor dem Start Spieler entfernen")
            target = game.player(str(msg.get("id")))
            if target and target.id != me:
                for other, (code, pid) in list(self.seats.items()):
                    if code == game.code and pid == target.id:
                        self.seats.pop(other)
                game.remove_player(target.id)
        elif kind == "settings":
            if not is_host or game.state != "lobby":
                raise RuleError("Nur der Gastgeber kann das ändern")
            game.configure(msg.get("settings") or {})
        elif kind == "start":
            if not is_host:
                raise RuleError("Nur der Gastgeber kann das Spiel starten")
            game.start()
        elif kind == "rematch":
            if not is_host or game.state != "finished":
                raise RuleError("Nur der Gastgeber kann eine neue Runde starten")
            game.start()
        else:
            live = game.act(me, msg, is_host)
            if live is not None:
                # A small live update (e.g. drawing strokes): send just that, not every full view.
                await self.broadcast_live(game.code, live)
                return
        await self.broadcast(game.code)

    async def broadcast_live(self, code: str, message: dict) -> None:
        self.touched[code] = time.time()
        for ws, token in list(self.sockets.items()):
            seat = self.seats.get(token)
            if seat and seat[0] == code:
                await self.send(ws, message)

    async def cleanup(self) -> None:
        now = time.time()
        for code in [c for c, t in self.touched.items() if now - t > GAME_TTL]:
            self.games.pop(code, None)
            self.touched.pop(code, None)
            self.timers.pop(code, None)
            for token in [t for t, s in self.seats.items() if s[0] == code]:
                self.seats.pop(token)
        await self.broadcast()


hubs = {kind: Hub(module) for kind, module in GAMES.items()}
routes = web.RouteTableDef()


def page(path: Path, root: str = "") -> web.Response:
    return html_response(path.read_text(encoding="utf-8"), root)


def html_response(html: str, root: str = "") -> web.Response:
    """Serve an HTML page; `root` is the relative way back to the start page ("" or "../")."""
    color = "#0b0a1f" if THEME == "dark" else "#eef2ff"
    head = f"""
  <link rel="manifest" href="{root}manifest.webmanifest">
  <meta name="theme-color" content="{color}">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="{'black-translucent' if THEME == 'dark' else 'default'}">
  <meta name="apple-mobile-web-app-title" content="Spieleabend">
  <link rel="apple-touch-icon" href="{root}static/icon-180.png">
  <link rel="icon" type="image/png" href="{root}static/icon-192.png">
  <script>
    if ("serviceWorker" in navigator && window.top === window && location.protocol === "https:")
      navigator.serviceWorker.register("{root}sw.js").catch(() => {{}});
  </script>
</head>"""
    html = html.replace("<html ", f'<html data-theme="{THEME}" ', 1)
    html = html.replace("</head>", head, 1).replace(
        'content="width=device-width, initial-scale=1, maximum-scale=1"',
        'content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover"', 1)
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


MANIFEST = {
    "name": "Spieleabend", "short_name": "Spieleabend", "lang": "de",
    "description": "Karten-, Zeichen-, Wort- und Partyspiele für den Spieleabend – zusammen spielen im Browser",
    "start_url": "./", "scope": "./", "display": "standalone", "orientation": "any",
    "background_color": "#0b0a1f" if THEME == "dark" else "#eef2ff",
    "theme_color": "#0b0a1f" if THEME == "dark" else "#eef2ff",
    "icons": [
        {"src": "static/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "static/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}


@routes.get("/manifest.webmanifest")
async def manifest(_: web.Request) -> web.Response:
    return web.json_response(MANIFEST, content_type="application/manifest+json")


@routes.get("/sw.js")
async def service_worker(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC_DIR / "sw.js", headers={"Cache-Control": "no-cache", "Content-Type": "text/javascript"})


# -- access code ---------------------------------------------------------------
def client_ip(request: web.Request) -> str:
    return (request.headers.get("Cf-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote or "?")


def via_ingress(request: web.Request) -> bool:
    return request.remote in INGRESS_IPS and "X-Ingress-Path" in request.headers


def has_access(request: web.Request) -> bool:
    if not ACCESS_CODE or via_ingress(request):
        return True
    return hmac.compare_digest(request.cookies.get(CODE_COOKIE, ""), CODE_TOKEN)


login_failures: dict[str, list[float]] = {}


def login_page(target: str, error: str = "", status: int = 401) -> web.Response:
    html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")
    html = html.replace("{{next}}", escape(target, quote=True))
    html = html.replace("{{error}}", error)
    response = html_response(html, "/")
    response.set_status(status)
    return response


def via_internet(request: web.Request) -> bool:
    """Cloudflare (tunnel or proxy) adds these headers to every request it forwards."""
    return "Cf-Ray" in request.headers or "Cf-Connecting-IP" in request.headers


@web.middleware
async def access_middleware(request: web.Request, handler):
    if not ACCESS_CODE and via_internet(request) and not via_ingress(request):
        # Safety net: reachable from the internet but nobody set a code – don't let everyone in.
        if request.path.startswith("/static/"):
            return await handler(request)
        return no_code_page()
    if has_access(request) or request.path.startswith(OPEN_PATHS):
        return await handler(request)
    if request.method == "GET" and ("text/html" in request.headers.get("Accept", "") or request.path.endswith("/")):
        return login_page(request.path_qs)
    raise web.HTTPUnauthorized(text="Zugangscode fehlt")


def no_code_page() -> web.Response:
    html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")
    start, end = html.index('<form'), html.index('</form>') + len('</form>')
    html = html[:start] + html[end:]
    html = html.replace("Gib den Zugangscode ein, den du bekommen hast.",
                        "Noch gesperrt: Im Spieleabend-Add-on muss zuerst ein Zugangscode gesetzt werden.")
    response = html_response(html, "/")
    response.set_status(403)
    return response


@routes.post("/__login")
async def login(request: web.Request) -> web.Response:
    form = await request.post()
    target = str(form.get("next") or "/")
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    if not ACCESS_CODE:
        raise web.HTTPSeeOther(target)
    ip, now = client_ip(request), time.time()
    tries = [t for t in login_failures.get(ip, []) if now - t < LOGIN_WINDOW]
    if len(tries) >= LOGIN_TRIES:
        login_failures[ip] = tries
        return login_page(target, "Zu viele Versuche – bitte in ein paar Minuten noch einmal.", 429)
    if not hmac.compare_digest(str(form.get("code", "")).strip().encode(), ACCESS_CODE.encode()):
        tries.append(now)
        login_failures[ip] = tries
        log.info("Falscher Zugangscode von %s", ip)
        return login_page(target, "Der Code stimmt nicht.")
    login_failures.pop(ip, None)
    secure = request.secure or request.headers.get("X-Forwarded-Proto") == "https" or "https" in request.headers.get("Cf-Visitor", "")
    response = web.Response(status=303, headers={"Location": target})
    response.set_cookie(CODE_COOKIE, CODE_TOKEN, max_age=365 * 86400, path="/", httponly=True, samesite="Lax", secure=secure)
    return response


@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return page(STATIC_DIR / "index.html")


@routes.get("/api/summary")
async def summary(_: web.Request) -> web.Response:
    data = {}
    for kind, hub in hubs.items():
        games = hub.open_games()
        data[kind] = {
            "open": sum(1 for g in games if g["state"] == "lobby" and not g["full"]),
            "playing": sum(1 for g in games if g["state"] == "playing"),
        }
    return web.json_response(data)


# Wortgitter is a single-player game that runs in the browser; the server only hands out the words.
WORDS_DIR = Path(__file__).parent / "data"


def word_list(name: str) -> list[str]:
    return [w.strip() for w in (WORDS_DIR / name).read_text(encoding="utf-8").splitlines()
            if w.strip() and not w.startswith("#")]


WORTGITTER = {"answers": word_list("wortgitter_loesungen.txt"), "valid": word_list("wortgitter_erlaubt.txt")}


@routes.get("/wortgitter")
async def wortgitter_redirect(_: web.Request) -> web.Response:
    raise web.HTTPFound("wortgitter/")


@routes.get("/wortgitter/")
async def wortgitter_page(_: web.Request) -> web.Response:
    return page(STATIC_DIR / "wortgitter" / "index.html", "../")


@routes.get("/wortgitter/woerter.json")
async def wortgitter_words(_: web.Request) -> web.Response:
    return web.json_response(WORTGITTER, headers={"Cache-Control": "max-age=86400"})


@routes.get("/{kind}")
async def no_slash(request: web.Request) -> web.Response:
    kind = request.match_info["kind"]
    if kind not in hubs:
        raise web.HTTPNotFound()
    raise web.HTTPFound(f"{kind}/")  # relative, so it also works behind Ingress


@routes.get("/{kind}/")
async def game_page(request: web.Request) -> web.Response:
    kind = request.match_info["kind"]
    if kind not in hubs:
        raise web.HTTPNotFound()
    return page(STATIC_DIR / kind / "index.html", "../")


@routes.get("/{kind}/ws")
async def websocket(request: web.Request) -> web.WebSocketResponse:
    hub = hubs.get(request.match_info["kind"])
    if not hub:
        raise web.HTTPNotFound()
    ip = client_ip(request)
    if sockets_per_ip.get(ip, 0) >= MAX_SOCKETS_PER_IP:
        raise web.HTTPTooManyRequests(text="Zu viele Verbindungen")
    ws = web.WebSocketResponse(heartbeat=25, max_msg_size=2 * 1024 * 1024)
    await ws.prepare(request)
    sockets_per_ip[ip] = sockets_per_ip.get(ip, 0) + 1
    token = None
    allowance, last = MSG_BURST, time.monotonic()
    try:
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue
            now = time.monotonic()
            allowance = min(MSG_BURST, allowance + (now - last) * MSG_RATE)
            last = now
            if allowance < 1:
                log.warning("Zu viele Nachrichten von %s – Verbindung getrennt", ip)
                await ws.close(code=1008, message=b"zu viele Nachrichten")
                break
            allowance -= 1
            try:
                data = json.loads(message.data)
            except ValueError:
                continue
            if token is None:
                # First message identifies the browser; an unknown token gets a fresh one.
                token = str(data.get("token") or "")
                if len(token) < 16:
                    token = secrets.token_urlsafe(16)
                hub.sockets[ws] = token
                await hub.send(ws, {"t": "hello", "token": token})
                await hub.send_view(ws)
                continue
            try:
                await hub.handle(ws, token, data)
            except RuleError as err:
                await hub.send(ws, {"t": "error", "msg": str(err)})
            except (TypeError, ValueError):
                await hub.send(ws, {"t": "error", "msg": "Ungültige Eingabe"})
    finally:
        hub.sockets.pop(ws, None)
        sockets_per_ip[ip] -= 1
        if not sockets_per_ip[ip]:
            sockets_per_ip.pop(ip)
    return ws


sockets_per_ip: dict[str, int] = {}


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(600)
        for hub in hubs.values():
            await hub.cleanup()


async def on_startup(app: web.Application) -> None:
    app["cleanup"] = asyncio.create_task(cleanup_loop())
    log.info("Spieleabend läuft auf Port %s%s", PORT, " (mit Zugangscode)" if ACCESS_CODE else "")
    if not ACCESS_CODE:
        log.info("Kein Zugangscode gesetzt: Aufrufe über Cloudflare werden abgewiesen, das Heimnetz ist offen.")


def main() -> None:
    app = web.Application(middlewares=[access_middleware])
    app.router.add_static("/static/", STATIC_DIR / "shared")
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    web.run_app(app, host=None, port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
