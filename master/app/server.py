"""Fabians-HA-Master: keeps every key and token in one place and is the bridge between the add-ons.

- Web page (Home Assistant sidebar): enter keys once, see which add-ons are connected.
- /api/keys     an add-on fetches its keys; it is recognised by its address, and gets only its own.
- /api/notify   iMessage to the owner (Inkbox) for every add-on – none of them needs the Inkbox key.
- /api/claude   Claude questions (e.g. Krypto-Trader) through the assistant's login.
- /api/tool/X/  the assistant reaches the other add-ons through here, without addresses or ports.

Keys are never shown again on the web page and never leave the master except to the add-on that uses them.
"""

import asyncio
import base64
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("master")

DATA = Path(os.environ.get("MASTER_DATA", "/data"))
STORE = DATA / "keys.json"
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("MASTER_PORT", "8090"))
SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor").rstrip("/")
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
INGRESS_IP = os.environ.get("MASTER_INGRESS_IP", "172.30.32.2")
INKBOX = os.environ.get("INKBOX_IMESSAGE_URL", "https://inkbox.ai/api/v1/imessage")
INKBOX_WHOAMI = os.environ.get("INKBOX_WHOAMI_URL", "https://inkbox.ai/api/whoami")
MAX_IMAGE = 8 * 1024 * 1024

# -- what the master keeps ------------------------------------------------------------------------
# group, key, label, secret, help, add-ons that get it
FIELDS = [
    ("iMessage (Inkbox)", "inkbox_api_key", "Inkbox-API-Key", True, "inkbox.ai → Einstellungen → API-Keys", ["assistent"]),
    ("iMessage (Inkbox)", "inkbox_identity", "Inkbox-Identität", False, "Name deiner Inkbox-Identität, ohne @", ["assistent"]),
    ("iMessage (Inkbox)", "phone", "Deine Handynummer", False, "Für Meldungen der Add-ons, z. B. +4917012345678", ["assistent"]),
    ("Claude", "claude_oauth_token", "Claude-Token", True, "Aus „claude setup-token“ – nicht nötig, wenn die claude.ai-Anmeldung importiert ist", ["assistent"]),
    ("Claude", "anthropic_api_key", "Anthropic-API-Key", True,
     "Für den Urlaubsplaner (Kassenzettel, Unterkünfte, Geheimtipps); beim Assistenten eine Alternative zum Token. Wird nach Verbrauch abgerechnet",
     ["assistent", "urlaub"]),
    ("Apple-Kalender", "icloud_apple_id", "Apple-ID", False,
     "E-Mail-Adresse deiner Apple-ID (die Karte fragt damit „Wo ist?“ nach einem frischen Standort)", ["assistent", "karte"]),
    ("Apple-Kalender", "icloud_app_password", "App-Passwort", True, "account.apple.com → Anmeldung und Sicherheit → App-Passwörter", ["assistent"]),
    ("eBay", "ebay_client_id", "Client-ID (App-ID)", False, "developer.ebay.com → Application Keys (Production)", ["assistent"]),
    ("eBay", "ebay_client_secret", "Client-Secret (Cert-ID)", True, "", ["assistent"]),
    ("eBay", "ebay_zip", "Postleitzahl", False, "Für Versandkosten und Entfernung", ["assistent"]),
    ("3D-Drucker (Bambu Lab)", "printer_ip", "IP-Adresse", False, "Drucker-Display → Einstellungen → Netzwerk", ["druck3d"]),
    ("3D-Drucker (Bambu Lab)", "printer_serial", "Seriennummer", False, "Drucker-Display → Einstellungen → Gerät", ["druck3d"]),
    ("3D-Drucker (Bambu Lab)", "printer_access_code", "Zugangscode (LAN)", True, "Drucker-Display → Einstellungen → Netzwerk → LAN-Modus", ["druck3d"]),
    ("Paketverfolgung", "paket_17track_key", "17TRACK-Schlüssel", True,
     "Kostenlos auf api.17track.net – verfolgt Pakete aller Paketdienste. Leer = Pakete werden nur gemerkt", ["assistent"]),
    ("Paketverfolgung", "paket_dhl_key", "DHL-Schlüssel", True,
     "Optional: developer.dhl.com → Shipment Tracking – Unified, für genauere DHL-Daten", ["assistent"]),
    ("Stundenplan 1 (WebUntis)", "untis1_name", "Name", False, "Frei wählbar, z. B. Fabian", ["assistent"]),
    ("Stundenplan 1 (WebUntis)", "untis1_server", "Server", False,
     "Adresse aus dem Browser beim WebUntis-Login (z. B. https://nessa.webuntis.com/WebUntis/?school=gym-musterstadt – dann bleibt Schule leer) oder nur der Server", ["assistent"]),
    ("Stundenplan 1 (WebUntis)", "untis1_school", "Schule", False, "Schulname, nur nötig, wenn er nicht in der Adresse steht", ["assistent"]),
    ("Stundenplan 1 (WebUntis)", "untis1_username", "Benutzername", False, "Deine WebUntis-Anmeldung", ["assistent"]),
    ("Stundenplan 1 (WebUntis)", "untis1_password", "Passwort", True, "Nur mit Untis-Passwort, nicht mit Microsoft-Login", ["assistent"]),
    ("Stundenplan 2 (WebUntis)", "untis2_name", "Name", False, "Frei wählbar, z. B. Fabian – leer lassen, wenn du nur einen Stundenplan hast", ["assistent"]),
    ("Stundenplan 2 (WebUntis)", "untis2_server", "Server", False,
     "Adresse aus dem Browser beim WebUntis-Login (z. B. https://nessa.webuntis.com/WebUntis/?school=gym-musterstadt – dann bleibt Schule leer) oder nur der Server", ["assistent"]),
    ("Stundenplan 2 (WebUntis)", "untis2_school", "Schule", False, "Schulname, nur nötig, wenn er nicht in der Adresse steht", ["assistent"]),
    ("Stundenplan 2 (WebUntis)", "untis2_username", "Benutzername", False, "Deine WebUntis-Anmeldung", ["assistent"]),
    ("Stundenplan 2 (WebUntis)", "untis2_password", "Passwort", True, "Nur mit Untis-Passwort, nicht mit Microsoft-Login", ["assistent"]),
    ("Krypto-Börse", "exchange_api_key", "API-Key", True, "Nur Handelsrecht, KEINE Auszahlungen erlauben", ["krypto"]),
    ("Krypto-Börse", "exchange_api_secret", "API-Secret", True, "", ["krypto"]),
    ("Krypto-Börse", "exchange_api_password", "API-Passphrase", True, "Nur bei manchen Börsen nötig", ["krypto"]),
    ("Zugangscodes", "access_code", "Downloader und Videos", True,
     "Wird nur aus dem Internet abgefragt (Tunnel). Lang wählen und für dich behalten. Leer = Internet gesperrt",
     ["downloader", "videodownloader"]),
    ("Zugangscodes", "games_code", "Spieleabend", True,
     "Für alle, die nicht über Home Assistant spielen (auch für die Bestenliste) – den darfst du an Freunde geben",
     ["spieleabend", "bestenliste"]),
    ("E-Mail (Spieleabend)", "smtp_host", "SMTP-Server", False,
     "Für Bestätigungscodes bei Registrierung und „Passwort vergessen“, z. B. smtp.gmail.com, smtp.web.de, smtp.gmx.net. Leer = Codes nur im Protokoll",
     ["spieleabend"]),
    ("E-Mail (Spieleabend)", "smtp_port", "Port", False, "Meist 587 (STARTTLS) oder 465 (SSL); leer = 587", ["spieleabend"]),
    ("E-Mail (Spieleabend)", "smtp_tls", "Verschlüsselung", False, "starttls (Port 587), ssl (Port 465) oder none; leer = starttls", ["spieleabend"]),
    ("E-Mail (Spieleabend)", "smtp_user", "Benutzer", False, "Meist deine E-Mail-Adresse", ["spieleabend"]),
    ("E-Mail (Spieleabend)", "smtp_password", "Passwort", True, "Bei Gmail und iCloud ein App-Passwort", ["spieleabend"]),
    ("E-Mail (Spieleabend)", "smtp_from", "Absender", False, "Leer = Benutzer", ["spieleabend"]),
]
FIELD = {f[1]: f for f in FIELDS}
# API keys, secrets and tokens never contain spaces: line breaks or quotes from copying are removed.
TOKEN_FIELD = re.compile(r"(_key|_secret|_token)$")
PHONE = re.compile(r"^\+[1-9][0-9]{6,14}$")

# The add-ons of this repository: name → title, internal port (for the bridge).
TOOLS = {
    "assistent": ("Fabians-HA-Assistent", 8093),
    "krypto": ("Fabians-HA-Krypto-Trader", 8094),
    "druck3d": ("Fabians-HA-3D-Druck", 8095),
    "videodownloader": ("Fabians-HA-Video-Downloader", 8097),
    "spieleabend": ("Fabians-HA-Spieleabend", 8098),
    "downloader": ("Fabians-HA-Downloader", 8099),
    "bestenliste": ("Fabians-HA-Bestenliste", 8091),
    "browser": ("Fabians-HA-Browser", 8096),
    "urlaub": ("Fabians-HA-Urlaub", 8100),
    "gedaechtnis": ("Fabians-HA-Gedächtnis", 8101),
    "karte": ("Fabians-HA-Karte", 8102),
}
# Without these an add-on cannot work at all (everything else is optional: Claude also works with an
# imported claude.ai login, the exchange keys are only needed for real money).
REQUIRED = {"assistent": ["inkbox_api_key", "inkbox_identity"],
            "druck3d": ["printer_ip", "printer_serial", "printer_access_code"]}
# Keys of the old single add-ons, for the one-click import: old slug ending → {old option: new key}.
IMPORT = {
    "inkbox_claude_gateway": {"inkbox_api_key": "inkbox_api_key", "inkbox_identity": "inkbox_identity",
                              "claude_oauth_token": "claude_oauth_token", "anthropic_api_key": "anthropic_api_key",
                              "icloud_apple_id": "icloud_apple_id", "icloud_app_password": "icloud_app_password",
                              "ebay_client_id": "ebay_client_id", "ebay_client_secret": "ebay_client_secret",
                              "ebay_zip": "ebay_zip", "ebay_notify_to": "phone",
                              "paket_17track_key": "paket_17track_key", "paket_dhl_key": "paket_dhl_key",
                              **{f"untis.{i}.{part}": f"untis{i + 1}_{part}" for i in (0, 1)
                                 for part in ("name", "server", "school", "username", "password")}},
    "druck3d": {"printer_ip": "printer_ip", "printer_serial": "printer_serial", "access_code": "printer_access_code",
                "inkbox_api_key": "inkbox_api_key", "imessage_to": "phone"},
    "krypto": {"api_key": "exchange_api_key", "api_secret": "exchange_api_secret", "api_password": "exchange_api_password",
               "inkbox_api_key": "inkbox_api_key", "imessage_to": "phone"},
    "downloader": {"inkbox_api_key": "inkbox_api_key", "imessage_to": "phone", "access_code": "access_code"},
    "videodownloader": {"access_code": "access_code"},
    "spieleabend": {"access_code": "games_code", **{f"smtp_{k}": f"smtp_{k}" for k in ("host", "port", "tls", "user", "password", "from")}},
    "bestenliste": {"access_code": "games_code"},
    "urlaub": {"anthropic_api_key": "anthropic_api_key"},
}


# -- key store ------------------------------------------------------------------------------------
class Store:
    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}
        # Keys saved before 1.2.0 may still contain a line break or quotes from copying.
        cleaned = {k: re.sub(r"\s+", "", str(v)).strip("\"'`") for k, v in self.data.items()
                   if k in FIELD and TOKEN_FIELD.search(k) and isinstance(v, str)}
        if any(self.data[k] != v for k, v in cleaned.items()):
            self.data.update(cleaned)
            self.save()
        if not self.data.get("bridge_key"):
            # Shared only between the master and the assistant's Claude bridge.
            self.data["bridge_key"] = secrets.token_urlsafe(32)
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def get(self, key: str) -> str:
        return str(self.data.get(key) or "")

    def for_tool(self, tool: str) -> dict:
        out = {k: self.get(k) for k, f in FIELD.items() if tool in f[5]}
        if tool == "assistent":
            out["bridge_key"] = self.get("bridge_key")
        return out

    def update(self, values: dict) -> list[str]:
        """Saves the given keys; raises ValueError (with a message for the page) for invalid values."""
        clean = {}
        for key, value in values.items():
            if key not in FIELD:
                continue
            value = " ".join(str(value or "").split()) if not FIELD[key][3] else str(value or "").strip()
            if TOKEN_FIELD.search(key):
                value = re.sub(r"\s+", "", value).strip("\"'`")
            if key == "phone" and value:
                value = re.sub(r"[\s/()-]", "", value)
                if value.startswith("00"):
                    value = "+" + value[2:]
                if not PHONE.match(value):
                    raise ValueError("Handynummer bitte im Format +4917012345678")
            if key == "inkbox_identity":
                value = value.lstrip("@")
            clean[key] = value
        changed = []
        for key, value in clean.items():
            if value != self.get(key):
                if value:
                    self.data[key] = value
                else:
                    self.data.pop(key, None)
                changed.append(key)
        if changed:
            self.save()
        return changed


def mask(value: str) -> str:
    return "•" * 6 + value[-3:] if len(value) > 8 else "•" * 6


# -- Home Assistant Supervisor --------------------------------------------------------------------
class Supervisor:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.prefix = self._own_prefix()
        self.ips: dict[str, str] = {}       # ip → tool name
        self.addons: dict[str, dict] = {}   # tool name → info
        self.refreshed = 0.0
        self.installed: dict[str, dict] = {}

    @staticmethod
    def _own_prefix() -> str:
        env = os.environ.get("MASTER_PREFIX")
        if env:
            return env
        host = socket.gethostname()
        return host.split("-", 1)[0] if "-" in host else "local"

    def host(self, tool: str) -> str:
        override = os.environ.get(f"MASTER_HOST_{tool.upper()}")
        return override or f"{self.prefix}-{tool}"

    async def call(self, method: str, path: str, body: dict | None = None) -> dict:
        if not SUPERVISOR_TOKEN:
            raise web.HTTPServiceUnavailable(text="Kein Zugriff auf den Supervisor")
        async with self.session.request(method, SUPERVISOR + path, json=body,
                                        headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 300 or not isinstance(data, dict):
                raise RuntimeError((data or {}).get("message") if isinstance(data, dict) else f"Supervisor {resp.status}")
            return data.get("data") or {}

    async def refresh(self, force: bool = False) -> bool:
        """Reloads which add-ons are installed and their addresses; False if the Supervisor failed."""
        if not force and time.time() - self.refreshed < 5:
            return True
        self.refreshed = time.time()
        try:
            installed = {a["slug"]: a for a in (await self.call("GET", "/addons")).get("addons", [])}
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, web.HTTPException) as err:
            log.warning("Supervisor nicht erreichbar: %s", err)
            self.ips = {}       # never answer from an outdated list
            return False
        ips, addons = {}, {}
        for tool in TOOLS:
            slug = f"{self.prefix}_{tool}"
            if slug not in installed:
                continue
            try:
                info = await self.call("GET", f"/addons/{slug}/info")
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as err:
                log.warning("Add-on %s: %s", slug, err)
                continue
            addons[tool] = {"slug": slug, "state": info.get("state"), "version": info.get("version")}
            if info.get("ip_address"):
                ips[info["ip_address"]] = tool
        self.ips, self.addons = ips, addons
        self.installed = installed
        return True

    async def caller(self, request: web.Request, fresh: bool = False) -> str | None:
        """Which add-on sent the request. Addresses can change when an add-on restarts, so the
        list is never older than 30 seconds – and always fresh before keys are handed out."""
        ip = request.remote or ""
        if fresh or time.time() - self.refreshed > 30:
            if not await self.refresh(force=True):
                return None
        elif ip not in self.ips:
            await self.refresh()
        return self.ips.get(ip)

    async def old_addons(self) -> list[dict]:
        """Installed single add-ons from the old repositories (other prefix), with their options."""
        await self.refresh(force=True)
        found = []
        for slug in self.installed:
            prefix, _, name = slug.partition("_")
            if prefix == self.prefix or name not in IMPORT:
                continue
            try:
                info = await self.call("GET", f"/addons/{slug}/info")
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as err:
                log.warning("Altes Add-on %s: %s", slug, err)
                continue
            found.append({"slug": slug, "name": info.get("name") or slug, "kind": name, "options": info.get("options") or {}})
        return found

    async def restart(self, tool: str) -> bool:
        info = self.addons.get(tool)
        if not info or info.get("state") != "started":
            return False
        try:
            await self.call("POST", f"/addons/{info['slug']}/restart")
            return True
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as err:
            log.warning("Neustart von %s fehlgeschlagen: %s", tool, err)
            return False


# -- helpers --------------------------------------------------------------------------------------
def fail(message: str, status: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=status)


async def body_of(request: web.Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


class RateLimit:
    def __init__(self, per_minute: int):
        self.per_minute, self.hits = per_minute, {}

    def ok(self, who: str) -> bool:
        now = time.time()
        hits = [t for t in self.hits.get(who, []) if now - t < 60]
        if len(hits) >= self.per_minute:
            return False
        self.hits[who] = hits + [now]
        return True


notify_limit = RateLimit(20)


async def send_imessage(app: web.Application, text: str, image: bytes | None = None, filename: str = "bild.jpg") -> str | None:
    """Sends the message; returns an error text or None."""
    store: Store = app["store"]
    key, to = store.get("inkbox_api_key"), store.get("phone")
    if not (key and to):
        return "iMessage ist im Master nicht eingerichtet (Inkbox-API-Key und Handynummer)"
    session: aiohttp.ClientSession = app["http"]
    headers = {"X-API-Key": key}
    payload: dict = {"to": to, "text": text[:4000]}
    try:
        if image:
            form = aiohttp.FormData()
            ctype = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
            form.add_field("file", image, filename=filename, content_type=ctype)
            async with session.post(f"{INKBOX}/media", data=form, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status < 300:
                    payload["media_urls"] = [(await resp.json(content_type=None))["media_url"]]
                else:
                    log.warning("Bild-Upload fehlgeschlagen: %s", resp.status)
        async with session.post(f"{INKBOX}/messages", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status >= 300:
                body = (await resp.text())[:300]
                log.warning("iMessage fehlgeschlagen: %s %s", resp.status, body)
                return inkbox_error(resp.status, body)
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError) as err:
        log.warning("iMessage fehlgeschlagen: %s", err)
        return "Inkbox nicht erreichbar"
    return None


def inkbox_error(status: int, body: str) -> str:
    """A message the person can act on, for an error answer from Inkbox."""
    try:
        detail = json.loads(body)
        detail = detail.get("detail") or detail.get("error") or detail.get("message") or ""
        if isinstance(detail, (dict, list)):
            detail = json.dumps(detail, ensure_ascii=False)
    except ValueError:
        detail = ""
    hint = {
        401: "Inkbox lehnt den API-Key ab – er ist falsch, abgelaufen oder gelöscht. Auf inkbox.ai → Einstellungen → "
             "API-Keys einen Key kopieren und hier unter „iMessage (Inkbox)“ neu eintragen",
        403: "Inkbox erlaubt das Senden an diese Nummer nicht (Kontaktregel oder Key ohne Rechte für die Identität)",
        404: "Für diese Nummer gibt es bei Inkbox noch keine iMessage-Verbindung – schreib der Inkbox-Identität "
             "einmal von deinem Handy aus",
        409: "Die iMessage-Verbindung ist noch nicht bereit – schreib der Inkbox-Identität einmal von deinem Handy aus",
        429: "Inkbox: Tageslimit für Nachrichten erreicht",
    }.get(status, f"Inkbox meldet Fehler {status}")
    return f"{hint} (Fehler {status}{': ' + str(detail)[:160] if detail else ''})"


async def check_inkbox_key(app: web.Application) -> str | None:
    """Asks Inkbox whether the saved key is valid; returns a problem or None."""
    key = app["store"].get("inkbox_api_key")
    if not key:
        return None
    try:
        async with app["http"].get(INKBOX_WHOAMI, headers={"X-API-Key": key}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status < 300:
                return None
            return inkbox_error(resp.status, (await resp.text())[:300])
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return None      # Inkbox not reachable: nothing to say about the key


# -- API for the other add-ons --------------------------------------------------------------------
routes = web.RouteTableDef()


async def require_tool(request: web.Request, fresh: bool = False) -> str:
    tool = await request.app["sv"].caller(request, fresh)
    if not tool:
        log.warning("Abgelehnt: Anfrage von %s ist kein Add-on dieses Repositorys", request.remote)
        raise web.HTTPForbidden(text=json.dumps({"error": "Nur für Fabians-HA-Add-ons"}), content_type="application/json")
    return tool


@routes.get("/api/keys")
async def api_keys(request: web.Request) -> web.Response:
    tool = await require_tool(request, fresh=True)
    log.info("Schlüssel an %s ausgegeben", TOOLS[tool][0])
    return web.json_response(request.app["store"].for_tool(tool))


@routes.get("/api/tools")
async def api_tools(request: web.Request) -> web.Response:
    await require_tool(request)
    sv: Supervisor = request.app["sv"]
    await sv.refresh()
    return web.json_response({t: info for t, info in sv.addons.items()})


@routes.post("/api/notify")
async def api_notify(request: web.Request) -> web.Response:
    tool = await require_tool(request)
    if not notify_limit.ok(tool):
        return fail("Zu viele Nachrichten – höchstens 20 pro Minute", 429)
    data = await body_of(request)
    text = str(data.get("text") or "").strip()
    image = None
    if data.get("image_b64"):
        try:
            image = base64.b64decode(str(data["image_b64"]), validate=True)
        except ValueError:
            return fail("Bild nicht lesbar")
        if len(image) > MAX_IMAGE:
            return fail("Bild zu groß")
    if not text and not image:
        return fail("Kein Text")
    error = await send_imessage(request.app, text, image, os.path.basename(str(data.get("filename") or "bild.jpg")))
    if error:
        return fail(error, 503)
    return web.json_response({"sent": True})


@routes.post("/api/claude")
async def api_claude(request: web.Request) -> web.Response:
    tool = await require_tool(request)
    if tool == "assistent":
        return fail("Der Assistent fragt Claude selbst")
    sv: Supervisor = request.app["sv"]
    if "assistent" not in sv.addons:
        await sv.refresh(force=True)
    if "assistent" not in sv.addons:
        return fail("Claude läuft über Fabians-HA-Assistent – bitte installieren und starten", 503)
    body = await request.read()
    if len(body) > 600_000:
        return fail("Anfrage zu groß")
    url = f"http://{sv.host('assistent')}:{TOOLS['assistent'][1]}/ask"
    try:
        async with request.app["http"].post(url, data=body, headers={"Content-Type": "application/json",
                                                                     "X-Bridge-Key": request.app["store"].get("bridge_key")},
                                            timeout=aiohttp.ClientTimeout(total=1000)) as resp:
            return web.Response(body=await resp.read(), status=resp.status, content_type="application/json")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return fail("Fabians-HA-Assistent nicht erreichbar – läuft er?", 503)


@routes.route("*", "/api/tool/{tool}/{path:.*}")
async def api_tool(request: web.Request) -> web.StreamResponse:
    """Bridge from the assistant to the other add-ons (status, downloads, printer, trader)."""
    caller = await require_tool(request)
    if caller != "assistent":
        return fail("Nur der Assistent nutzt die Brücke", 403)
    tool = request.match_info["tool"]
    if tool not in TOOLS or tool == "assistent":
        return fail("Unbekanntes Add-on", 404)
    sv: Supervisor = request.app["sv"]
    if tool not in sv.addons:
        await sv.refresh(force=True)
    if tool not in sv.addons:
        return fail(f"{TOOLS[tool][0]} ist nicht installiert", 503)
    url = f"http://{sv.host(tool)}:{TOOLS[tool][1]}/{request.match_info['path']}"
    headers = {k: v for k, v in request.headers.items() if k.lower() in ("content-type", "accept")}
    try:
        async with request.app["http"].request(request.method, url, params=request.query, data=await request.read(),
                                               headers=headers, timeout=aiohttp.ClientTimeout(total=900)) as resp:
            return web.Response(body=await resp.read(), status=resp.status,
                                content_type=resp.content_type or "application/octet-stream")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return fail(f"{TOOLS[tool][0]} nicht erreichbar – läuft es?", 503)


# -- web page (only through Home Assistant) -------------------------------------------------------
def require_ingress(request: web.Request) -> None:
    if os.environ.get("MASTER_UI_OPEN") != "1" and request.remote != INGRESS_IP:
        raise web.HTTPForbidden(text="Nur über Home Assistant")


@routes.get("/")
async def index(request: web.Request) -> web.Response:
    require_ingress(request)
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


async def state(app: web.Application) -> dict:
    store: Store = app["store"]
    sv: Supervisor = app["sv"]
    await sv.refresh(force=True)
    groups: dict[str, list] = {}
    for group, key, label, secret, help_text, tools in FIELDS:
        value = store.get(key)
        groups.setdefault(group, []).append({
            "key": key, "label": label, "secret": secret, "help": help_text, "set": bool(value),
            "value": "" if secret else value, "masked": mask(value) if secret and value else "",
            "tools": [TOOLS[t][0] for t in tools],
        })
    tools = []
    for name, (title, _) in TOOLS.items():
        info = sv.addons.get(name)
        needs = [FIELD[k][2] for k in REQUIRED.get(name, []) if not store.get(k)]
        tools.append({"name": name, "title": title, "installed": bool(info), "state": (info or {}).get("state"),
                      "version": (info or {}).get("version"), "missing": needs})
    return {"groups": [{"title": g, "fields": f} for g, f in groups.items()], "tools": tools,
            "imessage": bool(store.get("inkbox_api_key") and store.get("phone")), "supervisor": bool(SUPERVISOR_TOKEN)}


@routes.get("/ui/state")
async def ui_state(request: web.Request) -> web.Response:
    require_ingress(request)
    return web.json_response(await state(request.app))


async def restart_users(app: web.Application, changed: list[str]) -> list[str]:
    """Restart the running add-ons that use one of the changed keys, so they pick it up."""
    sv: Supervisor = app["sv"]
    users = sorted({t for k in changed for t in FIELD[k][5]})
    done = []
    for tool in users:
        if await sv.restart(tool):
            done.append(TOOLS[tool][0])
    return done


@routes.post("/ui/keys")
async def ui_keys(request: web.Request) -> web.Response:
    require_ingress(request)
    data = await body_of(request)
    try:
        changed = request.app["store"].update({k: v for k, v in data.items() if k in FIELD})
    except ValueError as err:
        return fail(str(err))
    if changed:
        log.info("Geändert: %s", ", ".join(FIELD[k][2] for k in changed))
    restarted = await restart_users(request.app, changed)
    warning = await check_inkbox_key(request.app) if "inkbox_api_key" in changed else None
    return web.json_response({**await state(request.app), "changed": len(changed), "restarted": restarted, "warning": warning})


@routes.post("/ui/import")
async def ui_import(request: web.Request) -> web.Response:
    """Takes over the keys from the old single add-ons (only fills empty fields)."""
    require_ingress(request)
    store: Store = request.app["store"]
    found = await request.app["sv"].old_addons()
    values: dict[str, str] = {}
    for addon in found:
        options = dict(addon["options"])
        for name, entries in addon["options"].items():     # lists (e.g. timetables) as "untis.0.name"
            if isinstance(entries, list):
                options.update({f"{name}.{i}.{k}": v for i, e in enumerate(entries) if isinstance(e, dict) for k, v in e.items()})
        for old, new in IMPORT[addon["kind"]].items():
            value = str(options.get(old) or "").strip()
            if value and not store.get(new) and new not in values:
                values[new] = value
    try:
        changed = store.update(values)
    except ValueError:
        values.pop("phone", None)      # an old, malformed number is simply left out
        changed = store.update(values)
    restarted = await restart_users(request.app, changed)
    return web.json_response({**await state(request.app), "imported": [FIELD[k][2] for k in changed],
                              "sources": [a["name"] for a in found], "restarted": restarted})


@routes.post("/ui/test")
async def ui_test(request: web.Request) -> web.Response:
    require_ingress(request)
    what = (await body_of(request)).get("what")
    if what == "imessage":
        error = await send_imessage(request.app, "✅ Test vom Fabians-HA-Master: iMessage funktioniert.")
        return web.json_response({"ok": not error, "message": error or "Nachricht gesendet – schau auf dein Handy."})
    if what == "claude":
        sv: Supervisor = request.app["sv"]
        url = f"http://{sv.host('assistent')}:{TOOLS['assistent'][1]}/ask"
        try:
            async with request.app["http"].post(url, json={"prompt": "Antworte nur mit: Hallo vom Assistenten", "max_turns": 1},
                                                headers={"X-Bridge-Key": request.app["store"].get("bridge_key")},
                                                timeout=aiohttp.ClientTimeout(total=120)) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return web.json_response({"ok": False, "message": "Fabians-HA-Assistent nicht erreichbar – läuft er?"})
        if resp.status != 200 or data.get("is_error"):
            return web.json_response({"ok": False, "message": str(data.get("error") or data.get("result") or "Fehler")[:300]})
        return web.json_response({"ok": True, "message": f"Claude antwortet: {str(data.get('result'))[:200]}"})
    return fail("Unbekannter Test")


# -- start ----------------------------------------------------------------------------------------
@web.middleware
async def security_headers(request: web.Request, handler):
    response = await handler(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


async def on_startup(app: web.Application) -> None:
    app["http"] = aiohttp.ClientSession(trust_env=False)
    app["sv"] = Supervisor(app["http"])
    await app["sv"].refresh(force=True)
    log.info("Bereit (Präfix %s, verbunden: %s)", app["sv"].prefix,
             ", ".join(TOOLS[t][0] for t in app["sv"].addons) or "noch keine Add-ons")


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()


def make_app() -> web.Application:
    app = web.Application(middlewares=[security_headers], client_max_size=12 * 1024 * 1024)
    app["store"] = Store(STORE)
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), port=PORT, access_log=None)
