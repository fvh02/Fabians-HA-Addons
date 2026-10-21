"""Urlaubsplaner: plan a trip together – accommodations, spots nearby, and shared shopping costs.

One person creates the trip and gets a code; everyone else joins with the code. Each browser keeps a
secret token per trip, which the API expects in the X-Token header. With an account (Sign in with Apple
or Google) the trips are on every device: then X-Account carries the session and X-Code the trip.
"""

import asyncio
import html
import io
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

import aiohttp
from aiohttp import web
from PIL import Image, ImageOps, UnidentifiedImageError

import airbnb
import fabians_master
import geo
import split
from ai import AI, AIError
from login import PROVIDERS, Login, LoginError
from store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("urlaub")

DATA = Path(os.environ.get("URLAUB_DATA", "/data"))
OPTIONS_FILE = Path(os.environ.get("URLAUB_OPTIONS", DATA / "options.json"))
STATIC = Path(__file__).parent / "static"
PORT = int(os.environ.get("URLAUB_PORT", "8100"))
MAX_IMAGE = 15 * 1024 * 1024
MAX_MEMBERS = 30


def load_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except (OSError, ValueError):
        return {}


OPTIONS = load_options()
store = Store(DATA / "urlaub.sqlite3")
# The keys come from Fabians-HA-Master: the Anthropic API key (the same the assistant can use) and the
# Google / Apple sign-in. URLAUB_KEYS (JSON) replaces the master for tests.
KEYS = json.loads(os.environ["URLAUB_KEYS"]) if "URLAUB_KEYS" in os.environ else fabians_master.keys(wait=90)
API_KEY = os.environ.get("ANTHROPIC_API_KEY", KEYS.get("anthropic_api_key"))
login = Login(KEYS)
ai = AI(str(API_KEY or "").strip(),
        str(OPTIONS.get("model") or "claude-opus-5-5").strip())
routes = web.RouteTableDef()
locks: dict[tuple[int, str], asyncio.Lock] = {}
join_attempts: dict[str, list[float]] = {}


class Fail(web.HTTPException):
    """A JSON error with a German message for the page."""
    def __init__(self, status: int, message: str):
        self.status_code = status
        super().__init__(text=json.dumps({"error": message}), content_type="application/json")


def lock(trip_id: int, what: str) -> asyncio.Lock:
    return locks.setdefault((trip_id, what), asyncio.Lock())


def client_ip(request: web.Request) -> str:
    return request.headers.get("Cf-Connecting-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or ""


async def body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        raise Fail(400, "Ungültige Anfrage")
    if not isinstance(data, dict):
        raise Fail(400, "Ungültige Anfrage")
    return data


def text(data: dict, key: str, limit: int, required: bool = False) -> str:
    value = re.sub(r"\s+", " ", str(data.get(key) or "")).strip()[:limit]
    if required and not value:
        raise Fail(400, {"name": "Bitte gib deinen Namen ein", "trip": "Bitte gib dem Urlaub einen Namen",
                         "destination": "Wohin geht es? Bitte ein Ziel eingeben"}.get(key, f"{key} fehlt"))
    return value


def date(data: dict, key: str) -> str:
    value = str(data.get(key) or "").strip()
    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else ""


def dates(data: dict) -> tuple[str, str]:
    start, end = date(data, "start"), date(data, "end")
    if start and end and end < start:
        raise Fail(400, "Das Ende liegt vor dem Anfang – bitte die Daten prüfen")
    return start, end


def account(request: web.Request) -> dict | None:
    return store.account_by_session(request.headers.get("X-Account", ""))


def me(request: web.Request) -> tuple[dict, dict]:
    member = store.member_by_token(request.headers.get("X-Token", ""))
    if not member and request.headers.get("X-Code"):
        acc = account(request)
        member = acc and store.member_by_account(request.headers["X-Code"], acc["id"])
    if not member:
        raise Fail(401, "Du bist (nicht mehr) Teil dieses Urlaubs – bitte mit dem Code neu beitreten")
    trip = store.trip(member["trip_id"])
    return trip, member


def owner_only(member: dict) -> None:
    if not member["owner"]:
        raise Fail(403, "Das darf nur, wer den Urlaub erstellt hat")


# -- pages ----------------------------------------------------------------------------------------------
@routes.get("/")
async def index(_: web.Request) -> web.Response:
    return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


# -- trips & people --------------------------------------------------------------------------------------
@routes.post("/api/trips")
async def create_trip(request: web.Request) -> web.Response:
    data = await body(request)
    name, owner = text(data, "trip", 60, True), text(data, "name", 30, True)
    destination = text(data, "destination", 120)
    start, end = dates(data)
    place = None
    if destination:
        try:
            async with aiohttp.ClientSession() as session:
                place = await geo.geocode(session, destination)
        except geo.GeoError as err:
            log.info("Ziel nicht gefunden: %s", err)
    acc = account(request)
    trip, token = store.create_trip(name, destination, start, end, owner, place, acc and acc["id"])
    if not destination:
        store.add_poll(trip["id"], "Wo geht's hin?", "ziel", True, [], store.member_by_token(token)["id"])
    log.info("Neuer Urlaub %s (%s) nach %s", trip["code"], name, destination or "(Ziel offen)")
    return web.json_response({"code": trip["code"], "token": token, "found": bool(place) or not destination})


@routes.post("/api/join")
async def join(request: web.Request) -> web.Response:
    ip, now = client_ip(request), time.time()
    tries = [t for t in join_attempts.get(ip, []) if now - t < 600]
    if len(tries) >= 20:
        raise Fail(429, "Zu viele Versuche – bitte in ein paar Minuten noch einmal")
    data = await body(request)
    trip = store.trip_by_code(text(data, "code", 10))
    if not trip:
        join_attempts[ip] = tries + [now]
        raise Fail(404, "Zu diesem Code gibt es keinen Urlaub")
    acc = account(request)
    if acc and (mine := store.member_by_account(trip["code"], acc["id"])):
        return web.json_response({"code": trip["code"], "token": "", "name": mine["name"]})     # already in it
    name = text(data, "name", 30, True)
    members = store.members(trip["id"])
    if len(members) >= MAX_MEMBERS:
        raise Fail(409, "Dieser Urlaub ist voll")
    if any(m["name"].casefold() == name.casefold() for m in members):
        raise Fail(409, f"„{name}“ ist schon dabei – bitte einen anderen Namen wählen")
    token = store.add_member(trip["id"], name, account_id=acc and acc["id"])
    return web.json_response({"code": trip["code"], "token": token, "name": name})


@routes.get("/api/trip")
async def get_trip(request: web.Request) -> web.Response:
    trip, member = me(request)
    return web.json_response(state(trip, member))


def state(trip: dict, member: dict) -> dict:
    members, tags = store.members(trip["id"]), store.tags(trip["id"])
    tagmap = {t["id"]: t for t in tags}
    receipts = store.receipts(trip["id"])
    for r in receipts:
        r["image"] = bool(r["image"])
    money = split.balances(members, tagmap, receipts)
    stays = store.q("SELECT id, url, data, manual, near, added_by FROM stays WHERE trip_id = ? ORDER BY id", trip["id"])
    for s in stays:
        s["data"], s["manual"] = json.loads(s["data"] or "{}"), json.loads(s["manual"] or "{}")
        s["near"] = json.loads(s["near"]) if s["near"] else None
    return {
        "trip": {k: trip[k] for k in ("code", "name", "destination", "start", "end", "lat", "lon", "place", "wishes", "currency")},
        "me": {"id": member["id"], "owner": bool(member["owner"])},
        "ai": ai.ready,
        "members": members, "tags": tags, "stays": stays,
        "ranking": json.loads(trip["ranking"]) if trip["ranking"] else None, "ranking_at": trip["ranking_at"],
        "spots": json.loads(trip["spots"]) if trip["spots"] else None, "spots_at": trip["spots_at"],
        "votes": {"stay": store.votes(trip["id"], "stay"), "spot": store.votes(trip["id"], "spot")},
        "polls": store.polls(trip["id"]),
        "receipts": receipts, "money": money, "settle": split.settle(money["net"]),
    }


@routes.patch("/api/trip")
async def edit_trip(request: web.Request) -> web.Response:
    trip, member = me(request)
    data = await body(request)
    fields = {}
    if "wishes" in data:
        fields["wishes"] = text(data, "wishes", 400)
    if "currency" in data:
        fields["currency"] = (text(data, "currency", 3) or "EUR").upper()
    if any(k in data for k in ("trip", "destination", "start", "end")):
        owner_only(member)
        if "trip" in data:
            fields["name"] = text(data, "trip", 60, True)
        if "start" in data:
            fields["start"], fields["end"] = dates(data)
        if "destination" in data and text(data, "destination", 120, True) != trip["destination"]:
            fields["destination"] = text(data, "destination", 120, True)
            try:
                async with aiohttp.ClientSession() as session:
                    place = await geo.geocode(session, fields["destination"])
            except geo.GeoError as err:
                raise Fail(502, str(err))
            if not place:
                raise Fail(404, f"„{fields['destination']}“ wurde auf der Karte nicht gefunden")
            fields.update(lat=place["lat"], lon=place["lon"], place=place["name"], spots=None, spots_at=None)
    store.update_trip(trip["id"], **fields)
    return web.json_response(state(store.trip(trip["id"]), member))


@routes.delete("/api/trip")
async def delete_trip(request: web.Request) -> web.Response:
    """Deletes the whole trip for everyone: people, accommodations, votes, receipts and their photos."""
    trip, member = me(request)
    owner_only(member)
    store.run("DELETE FROM trips WHERE id = ?", trip["id"])
    shutil.rmtree(DATA / "belege" / str(trip["id"]), ignore_errors=True)
    log.info("Urlaub %s (%s) gelöscht", trip["code"], trip["name"])
    return web.json_response({"deleted": True})


@routes.patch("/api/members/{id}")
async def edit_member(request: web.Request) -> web.Response:
    trip, member = me(request)
    target = store.one("SELECT * FROM members WHERE id = ? AND trip_id = ?", int(request.match_info["id"]), trip["id"])
    if not target:
        raise Fail(404, "Diese Person gibt es nicht")
    if target["id"] != member["id"]:
        owner_only(member)
    data = await body(request)
    if "name" in data:
        store.run("UPDATE members SET name = ? WHERE id = ?", text(data, "name", 30, True), target["id"])
    if isinstance(data.get("answers"), dict):
        tag_ids = {t["id"] for t in store.tags(trip["id"])}
        answers = json.loads(target["answers"] or "{}")
        for key, value in data["answers"].items():
            if key in tag_ids:
                if value is None:
                    answers.pop(key, None)
                else:
                    answers[key] = bool(value)
        store.run("UPDATE members SET answers = ? WHERE id = ?", json.dumps(answers), target["id"])
    return web.json_response(state(trip, member))


@routes.delete("/api/members/{id}")
async def remove_member(request: web.Request) -> web.Response:
    trip, member = me(request)
    target_id = int(request.match_info["id"])
    if target_id != member["id"]:
        owner_only(member)
    elif member["owner"]:
        raise Fail(400, "Wer den Urlaub erstellt hat, kann ihn nicht verlassen")
    store.run("DELETE FROM members WHERE id = ? AND trip_id = ? AND owner = 0", target_id, trip["id"])
    store.run("UPDATE receipts SET payer = NULL WHERE trip_id = ? AND payer = ?", trip["id"], target_id)
    if target_id == member["id"]:
        return web.json_response({"left": True})
    return web.json_response(state(trip, member))


@routes.post("/api/tags")
async def add_tag(request: web.Request) -> web.Response:
    trip, member = me(request)
    data = await body(request)
    name = text(data, "name", 30)
    if not name:
        raise Fail(400, "Bitte einen Namen für die Kategorie eingeben")
    tag_id = re.sub(r"[^a-z0-9]+", "-", name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")).strip("-")[:30] or "kategorie"
    existing = {t["id"] for t in store.tags(trip["id"])}
    if tag_id in existing:
        raise Fail(409, f"„{name}“ gibt es schon")
    parent = str(data.get("parent") or "") or None
    if parent and parent not in existing:
        parent = None
    icon = text(data, "icon", 4) or "🏷️"
    store.run("INSERT INTO tags (trip_id, id, name, parent, icon, sort) VALUES (?,?,?,?,?,?)", trip["id"], tag_id, name, parent, icon, 100)
    return web.json_response(state(trip, member))


@routes.delete("/api/tags/{id}")
async def remove_tag(request: web.Request) -> web.Response:
    trip, member = me(request)
    owner_only(member)
    tag_id = request.match_info["id"]
    store.run("DELETE FROM tags WHERE trip_id = ? AND id = ?", trip["id"], tag_id)
    store.run("UPDATE tags SET parent = NULL WHERE trip_id = ? AND parent = ?", trip["id"], tag_id)
    return web.json_response(state(trip, member))


@routes.post("/api/vote")
async def vote(request: web.Request) -> web.Response:
    trip, member = me(request)
    data = await body(request)
    kind = data.get("kind")
    if kind not in ("stay", "spot"):
        raise Fail(400, "Ungültige Anfrage")
    store.toggle_vote(trip["id"], kind, str(data.get("ref"))[:40], member["id"])
    return web.json_response(state(trip, member))


# -- accounts -------------------------------------------------------------------------------------------
def public_base(request: web.Request) -> str | None:
    """The add-on's own HTTPS address when it is opened through the tunnel; sign-in only works there."""
    https = request.headers.get("X-Forwarded-Proto", "").lower() == "https" or '"https"' in request.headers.get("Cf-Visitor", "")
    host = request.headers.get("X-Forwarded-Host") or request.host
    if not https or not re.fullmatch(r"[A-Za-z0-9.-]+(:\d+)?", host or ""):
        return None
    return f"https://{host}"


@routes.get("/api/account")
async def get_account(request: web.Request) -> web.Response:
    acc = account(request)
    return web.json_response({
        "account": acc and {"name": acc["name"], "email": acc["email"], "provider": PROVIDERS[acc["provider"]]["title"]},
        "trips": store.account_trips(acc["id"]) if acc else [],
        "providers": login.available() if public_base(request) else [],
        "configured": login.available(),
    })


@routes.post("/api/account/link")
async def link_account(request: web.Request) -> web.Response:
    """Adds a trip this browser joined without an account to the account."""
    acc = account(request)
    if not acc:
        raise Fail(401, "Bitte zuerst anmelden")
    member = store.member_by_token(request.headers.get("X-Token", ""))
    if not member:
        raise Fail(404, "Diesen Urlaub gibt es auf diesem Gerät nicht mehr")
    trip = store.trip(member["trip_id"])
    other = store.member_by_account(trip["code"], acc["id"])
    if other and other["id"] != member["id"]:
        raise Fail(409, f"Du bist in „{trip['name']}“ schon als {other['name']} dabei")
    if member["account_id"] and member["account_id"] != acc["id"]:
        raise Fail(409, f"{member['name']} in „{trip['name']}“ gehört schon zu einem anderen Konto")
    store.run("UPDATE members SET account_id = ? WHERE id = ?", acc["id"], member["id"])
    return web.json_response({"ok": True})


@routes.post("/api/account/logout")
async def logout(request: web.Request) -> web.Response:
    store.sign_out(request.headers.get("X-Account", ""))
    return web.json_response({"ok": True})


@routes.delete("/api/account")
async def delete_account(request: web.Request) -> web.Response:
    """Deletes the account; the trips stay, the person just is no longer linked to them."""
    acc = account(request)
    if not acc:
        raise Fail(401, "Bitte zuerst anmelden")
    store.run("UPDATE members SET account_id = NULL WHERE account_id = ?", acc["id"])
    store.run("DELETE FROM accounts WHERE id = ?", acc["id"])
    log.info("Konto %s gelöscht", acc["id"])
    return web.json_response({"ok": True})


LOGIN_COOKIE = "urlaub_login"


def login_page(message: str = "", token: str = "", status: int = 200) -> web.Response:
    """End of the sign-in: hands the session to the page (same origin) or shows what went wrong."""
    if token:
        script = f"try {{ localStorage.setItem('urlaub-account', {json.dumps(json.dumps(token))}); }} catch (e) {{}} location.replace('/');"
        page = f"<!doctype html><meta charset=utf-8><title>Angemeldet</title><script>{script}</script>"
    else:
        page = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Anmeldung</title>"
                "<body style='font-family:system-ui;max-width:420px;margin:15vh auto;padding:0 20px;text-align:center'>"
                f"<h2>Anmeldung nicht möglich</h2><p>{html.escape(message)}</p>"
                "<p><a href='/'>Zurück zum Urlaubsplaner</a></p>")
    resp = web.Response(text=page, content_type="text/html", status=status,
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    resp.del_cookie(LOGIN_COOKIE, path="/auth")
    return resp


@routes.get("/auth/{provider}")
async def auth_start(request: web.Request) -> web.Response:
    provider, base = request.match_info["provider"], public_base(request)
    if not base:
        return login_page("Die Anmeldung geht nur über die Internet-Adresse des Urlaubsplaners (https, Cloudflare Tunnel).", status=400)
    try:
        url, state = login.start(provider, f"{base}/auth/{provider}/callback")
    except LoginError as err:
        return login_page(str(err), status=400)
    resp = web.HTTPFound(url)
    # SameSite=None: Apple sends the answer as a cross-site POST.
    resp.set_cookie(LOGIN_COOKIE, state, path="/auth", max_age=600, secure=True, httponly=True, samesite="None")
    raise resp


@routes.route("*", "/auth/{provider}/callback")
async def auth_callback(request: web.Request) -> web.Response:
    provider = request.match_info["provider"]
    if provider not in PROVIDERS or request.method not in ("GET", "POST"):
        raise Fail(404, "Unbekannte Anmeldung")
    params = dict(request.query)
    if request.method == "POST":
        params.update({k: str(v) for k, v in (await request.post()).items()})
    if params.get("error"):
        return login_page("Die Anmeldung wurde abgebrochen." if "cancel" in params["error"] or params["error"] == "access_denied"
                          else f"{PROVIDERS[provider]['title']} meldet: {params['error']}", status=400)
    try:
        who = await login.finish(provider, params.get("state", ""), request.cookies.get(LOGIN_COOKIE, ""), params.get("code", ""), params.get("user", ""))
    except LoginError as err:
        return login_page(str(err), status=400)
    acc, token = store.sign_in(**who)
    log.info("Anmeldung mit %s: Konto %s", PROVIDERS[provider]["title"], acc["id"])
    return login_page(token=token)


# -- polls ----------------------------------------------------------------------------------------------
MAX_POLLS, MAX_OPTIONS = 20, 30


def own_poll(trip: dict, poll_id: int) -> dict:
    poll = store.one("SELECT * FROM polls WHERE id = ? AND trip_id = ?", poll_id, trip["id"])
    if not poll:
        raise Fail(404, "Diese Abstimmung gibt es nicht mehr")
    return poll


def option_texts(values, existing: list[str] = ()) -> list[str]:
    seen, out = {e.casefold() for e in existing}, []
    for value in values if isinstance(values, list) else []:
        option = re.sub(r"\s+", " ", str(value or "")).strip()[:60]
        if option and option.casefold() not in seen:
            seen.add(option.casefold())
            out.append(option)
    return out


@routes.post("/api/polls")
async def add_poll(request: web.Request) -> web.Response:
    trip, member = me(request)
    data = await body(request)
    question = text(data, "question", 100)
    if not question:
        raise Fail(400, "Bitte eine Frage eingeben")
    if len(store.q("SELECT id FROM polls WHERE trip_id = ?", trip["id"])) >= MAX_POLLS:
        raise Fail(409, "Es gibt schon sehr viele Abstimmungen – bitte erst alte löschen")
    kind = "ziel" if data.get("kind") == "ziel" else ""
    store.add_poll(trip["id"], question, kind, bool(data.get("multi", True)), option_texts(data.get("options"))[:MAX_OPTIONS], member["id"])
    return web.json_response(state(trip, member))


@routes.post("/api/polls/{id}/options")
async def add_poll_option(request: web.Request) -> web.Response:
    trip, member = me(request)
    poll = own_poll(trip, int(request.match_info["id"]))
    if poll["closed"]:
        raise Fail(409, "Diese Abstimmung ist schon beendet")
    data = await body(request)
    existing = [o["text"] for o in store.q("SELECT text FROM poll_options WHERE poll_id = ?", poll["id"])]
    new = option_texts([data.get("text")], existing)
    if not new:
        raise Fail(409, "Diese Antwort gibt es schon") if text(data, "text", 60) else Fail(400, "Bitte eine Antwort eingeben")
    if len(existing) >= MAX_OPTIONS:
        raise Fail(409, "Mehr Antworten passen nicht in diese Abstimmung")
    option_id = store.run("INSERT INTO poll_options (poll_id, text, added_by, created) VALUES (?,?,?,?)", poll["id"], new[0], member["id"], time.time())
    store.toggle_poll_vote(poll, option_id, member["id"])     # whoever suggests something votes for it
    return web.json_response(state(trip, member))


@routes.post("/api/polls/{id}/vote")
async def poll_vote(request: web.Request) -> web.Response:
    trip, member = me(request)
    poll = own_poll(trip, int(request.match_info["id"]))
    if poll["closed"]:
        raise Fail(409, "Diese Abstimmung ist schon beendet")
    data = await body(request)
    option = store.one("SELECT id FROM poll_options WHERE id = ? AND poll_id = ?", int(data.get("option")), poll["id"])
    if not option:
        raise Fail(404, "Diese Antwort gibt es nicht mehr")
    store.toggle_poll_vote(poll, option["id"], member["id"])
    return web.json_response(state(trip, member))


@routes.patch("/api/polls/{id}")
async def edit_poll(request: web.Request) -> web.Response:
    trip, member = me(request)
    poll = own_poll(trip, int(request.match_info["id"]))
    if poll["created_by"] != member["id"]:
        owner_only(member)
    data = await body(request)
    if "closed" in data:
        store.run("UPDATE polls SET closed = ? WHERE id = ?", int(bool(data["closed"])), poll["id"])
    return web.json_response(state(trip, member))


@routes.delete("/api/polls/{id}")
async def remove_poll(request: web.Request) -> web.Response:
    trip, member = me(request)
    poll = own_poll(trip, int(request.match_info["id"]))
    if poll["created_by"] != member["id"]:
        owner_only(member)
    store.run("DELETE FROM polls WHERE id = ?", poll["id"])
    return web.json_response(state(trip, member))


@routes.delete("/api/poll-options/{id}")
async def remove_poll_option(request: web.Request) -> web.Response:
    trip, member = me(request)
    option = store.one("SELECT poll_options.* FROM poll_options JOIN polls ON polls.id = poll_options.poll_id "
                       "WHERE poll_options.id = ? AND polls.trip_id = ?", int(request.match_info["id"]), trip["id"])
    if not option:
        raise Fail(404, "Diese Antwort gibt es nicht mehr")
    if option["added_by"] != member["id"]:
        owner_only(member)
    store.run("DELETE FROM poll_options WHERE id = ?", option["id"])
    return web.json_response(state(trip, member))


# -- accommodations -------------------------------------------------------------------------------------
MANUAL_KEYS = {"titel": str, "preis_gesamt": float, "naechte": int, "gaeste": int, "schlafzimmer": float, "betten": float,
               "baeder": float, "bewertung": float, "adresse": str, "notiz": str}


def manual_fields(data: dict) -> dict:
    out = {}
    for key, cast in MANUAL_KEYS.items():
        if key in data and data[key] not in (None, ""):
            try:
                out[key] = cast(str(data[key]).replace(",", ".")) if cast is not str else str(data[key])[:300]
            except ValueError:
                raise Fail(400, f"Bitte bei „{key}“ eine Zahl eingeben")
    return out


@routes.post("/api/stays")
async def add_stay(request: web.Request) -> web.Response:
    trip, member = me(request)
    data = await body(request)
    url = airbnb.clean_url(str(data.get("url") or ""))
    manual = manual_fields(data.get("manual") or {})
    if not url and not manual.get("titel"):
        raise Fail(400, "Bitte einen Link einfügen oder die Unterkunft von Hand beschreiben")
    if store.one("SELECT 1 FROM stays WHERE trip_id = ? AND url = ?", trip["id"], url) and url:
        raise Fail(409, "Diese Unterkunft ist schon in der Liste")
    info: dict = {}
    near = None
    async with aiohttp.ClientSession() as session:
        if url:
            info = await airbnb.fetch(session, url)
        point = await locate(session, info, manual)
        if point:
            info["lat"], info["lon"] = point
            try:
                centre = (trip["lat"], trip["lon"]) if trip["lat"] is not None else None
                near = await geo.surroundings(session, *point, centre)
            except geo.GeoError as err:
                log.info("Umgebung nicht abrufbar: %s", err)
    store.run("INSERT INTO stays (trip_id, url, data, manual, near, added_by, created) VALUES (?,?,?,?,?,?,?)",
              trip["id"], url, json.dumps(info, ensure_ascii=False), json.dumps(manual, ensure_ascii=False),
              json.dumps(near) if near else None, member["id"], time.time())
    return web.json_response(state(trip, member))


async def locate(session: aiohttp.ClientSession, info: dict, manual: dict) -> tuple[float, float] | None:
    if manual.get("adresse"):
        try:
            place = await geo.geocode(session, manual["adresse"])
            if place:
                return place["lat"], place["lon"]
        except geo.GeoError:
            pass
    if info.get("lat") is not None:
        return info["lat"], info["lon"]
    return None


@routes.patch("/api/stays/{id}")
async def edit_stay(request: web.Request) -> web.Response:
    trip, member = me(request)
    stay = store.one("SELECT * FROM stays WHERE id = ? AND trip_id = ?", int(request.match_info["id"]), trip["id"])
    if not stay:
        raise Fail(404, "Diese Unterkunft gibt es nicht mehr")
    data = await body(request)
    manual = {**json.loads(stay["manual"] or "{}"), **manual_fields(data.get("manual") or {})}
    for key, value in (data.get("manual") or {}).items():
        if value in (None, "") and key in manual:
            manual.pop(key)
    near = stay["near"]
    if manual.get("adresse") != json.loads(stay["manual"] or "{}").get("adresse"):
        async with aiohttp.ClientSession() as session:
            point = await locate(session, json.loads(stay["data"] or "{}"), manual)
            if point:
                try:
                    centre = (trip["lat"], trip["lon"]) if trip["lat"] is not None else None
                    near = json.dumps(await geo.surroundings(session, *point, centre))
                except geo.GeoError:
                    pass
    store.run("UPDATE stays SET manual = ?, near = ? WHERE id = ?", json.dumps(manual, ensure_ascii=False), near, stay["id"])
    return web.json_response(state(trip, member))


@routes.delete("/api/stays/{id}")
async def remove_stay(request: web.Request) -> web.Response:
    trip, member = me(request)
    store.run("DELETE FROM stays WHERE id = ? AND trip_id = ?", int(request.match_info["id"]), trip["id"])
    return web.json_response(state(trip, member))


@routes.post("/api/stays/rank")
async def rank_stays(request: web.Request) -> web.Response:
    trip, member = me(request)
    stays = store.q("SELECT id, url, data, manual, near FROM stays WHERE trip_id = ? ORDER BY id", trip["id"])
    if len(stays) < 2:
        raise Fail(400, "Füge mindestens zwei Unterkünfte hinzu, damit es etwas zu vergleichen gibt")
    members = store.members(trip["id"])
    listing = []
    for s in stays:
        data, manual = json.loads(s["data"] or "{}"), json.loads(s["manual"] or "{}")
        data.pop("bild", None)
        data.pop("fehler", None)
        entry = {"id": s["id"], **data, **manual, "umgebung": json.loads(s["near"]) if s["near"] else "unbekannt"}
        if manual.get("preis_gesamt"):
            nights = manual.get("naechte") or nights_of(trip) or 1
            entry["preis_pro_person_und_nacht"] = round(manual["preis_gesamt"] / max(1, len(members)) / nights, 2)
        listing.append(entry)
    info = {"ziel": trip["place"] or trip["destination"], "von": trip["start"], "bis": trip["end"], "naechte": nights_of(trip),
            "personen": len(members), "wuensche": trip["wishes"]}
    async with lock(trip["id"], "rank"):
        try:
            result = await ai.rank_stays(info, listing)
        except AIError as err:
            raise Fail(502, str(err))
    ids = {s["id"] for s in stays}
    result["bewertungen"] = [b for b in result.get("bewertungen", []) if b.get("id") in ids]
    result["top3"] = [t for t in result.get("top3", []) if t.get("id") in ids][:3]
    store.update_trip(trip["id"], ranking=json.dumps(result, ensure_ascii=False), ranking_at=time.time())
    return web.json_response(state(store.trip(trip["id"]), member))


def nights_of(trip: dict) -> int | None:
    try:
        a, b = (time.strptime(trip[k], "%Y-%m-%d") for k in ("start", "end"))
        return max(1, round((time.mktime(b) - time.mktime(a)) / 86400))
    except (TypeError, ValueError):
        return None


# -- spots ------------------------------------------------------------------------------------------------
@routes.post("/api/spots")
async def find_spots(request: web.Request) -> web.Response:
    trip, member = me(request)
    data = await body(request)
    if "wishes" in data:
        store.update_trip(trip["id"], wishes=text(data, "wishes", 400))
        trip = store.trip(trip["id"])
    if trip["lat"] is None:
        raise Fail(400, "Das Urlaubsziel wurde auf der Karte nicht gefunden – bitte das Ziel genauer angeben")
    radius = min(40.0, max(3.0, float(data.get("radius") or 15)))
    async with lock(trip["id"], "spots"):
        async with aiohttp.ClientSession() as session:
            try:
                candidates = await geo.spot_candidates(session, trip["lat"], trip["lon"], radius)
            except geo.GeoError as err:
                raise Fail(502, str(err))
        if len(candidates) < 3:
            raise Fail(404, "In der Umgebung wurden kaum Orte gefunden – vielleicht den Umkreis vergrößern")
        info = {"ziel": trip["place"] or trip["destination"], "von": trip["start"], "bis": trip["end"],
                "personen": len(store.members(trip["id"]))}
        try:
            result = await ai.pick_spots(info, candidates, trip["wishes"] or "")
        except AIError as err:
            raise Fail(502, str(err))
    by_id = {c["id"]: c for c in candidates}
    spots = []
    for s in result.get("spots", []):
        c = by_id.get(s.get("id"))
        if c:      # only real places from the candidate list
            spots.append({**s, "lat": c["lat"], "lon": c["lon"], "km": c["km"], "name": c["name"],
                          "wiki": c.get("info", {}).get("wikipedia", "")})
    store.update_trip(trip["id"], spots=json.dumps(spots, ensure_ascii=False), spots_at=time.time())
    return web.json_response(state(store.trip(trip["id"]), member))


# -- receipts -----------------------------------------------------------------------------------------------
def receipt_dir(trip_id: int) -> Path:
    path = DATA / "belege" / str(trip_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalise_image(raw: bytes) -> bytes:
    """Upright JPEG, at most 2000 px – small enough for Claude, sharp enough for small print."""
    try:
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise Fail(400, "Das Bild konnte nicht gelesen werden – bitte ein Foto als JPG oder PNG schicken")
    img.thumbnail((2000, 2000))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


@routes.post("/api/receipts")
async def add_receipt(request: web.Request) -> web.Response:
    trip, member = me(request)
    members = store.members(trip["id"])
    ids = {m["id"] for m in members}
    if request.content_type.startswith("multipart/"):
        reader = await request.multipart()
        raw, payer = b"", member["id"]
        async for part in reader:
            if part.name == "image":
                while chunk := await part.read_chunk(256 * 1024):
                    raw += chunk
                    if len(raw) > MAX_IMAGE:
                        raise Fail(413, "Das Bild ist zu groß (höchstens 15 MB)")
            elif part.name == "payer":
                value = (await part.text()).strip()
                payer = int(value) if value.isdigit() and int(value) in ids else payer
        if not raw:
            raise Fail(400, "Kein Bild empfangen")
        image = await asyncio.to_thread(normalise_image, raw)
        try:
            data = await ai.read_receipt(image, "image/jpeg", store.tags(trip["id"]))
        except AIError as err:
            raise Fail(502, str(err))
        if not data.get("ist_kassenzettel") or not data.get("artikel"):
            raise Fail(422, "Auf dem Bild war kein Kassenzettel zu erkennen – bitte noch einmal fotografieren (gerade, ganzer Bon, gutes Licht)")
        receipt_id = store.run("INSERT INTO receipts (trip_id, payer, store, date, currency, total, added_by, created) VALUES (?,?,?,?,?,?,?,?)",
                               trip["id"], payer, str(data.get("laden", ""))[:80], str(data.get("datum", ""))[:10],
                               (str(data.get("waehrung") or trip["currency"] or "EUR"))[:3].upper(),
                               data.get("summe"), member["id"], time.time())
        path = receipt_dir(trip["id"]) / f"{receipt_id}.jpg"
        path.write_bytes(image)
        store.run("UPDATE receipts SET image = ? WHERE id = ?", path.name, receipt_id)
        tag_ids = {t["id"] for t in store.tags(trip["id"])}
        for i, item in enumerate(data["artikel"]):
            store.run("INSERT INTO items (receipt_id, name, qty, price, tags, unsure, sort) VALUES (?,?,?,?,?,?,?)",
                      receipt_id, str(item.get("name") or "?")[:80], item.get("menge") or 1, round(float(item.get("preis") or 0), 2),
                      json.dumps([t for t in item.get("merkmale", []) if t in tag_ids]), int(bool(item.get("unsicher"))), i)
    else:
        # entered by hand: a name and an amount (e.g. "Tanken 60 €")
        data = await body(request)
        try:
            amount = round(float(str(data.get("amount", "")).replace(",", ".")), 2)
        except ValueError:
            raise Fail(400, "Bitte einen Betrag eingeben")
        payer = data.get("payer") if data.get("payer") in ids else member["id"]
        title = text(data, "title", 80) or "Ausgabe"
        receipt_id = store.run("INSERT INTO receipts (trip_id, payer, store, currency, total, added_by, created) VALUES (?,?,?,?,?,?,?)",
                               trip["id"], payer, title, trip["currency"] or "EUR", amount, member["id"], time.time())
        store.run("INSERT INTO items (receipt_id, name, qty, price, tags) VALUES (?,?,?,?,?)", receipt_id, title, 1, amount,
                  json.dumps([t for t in data.get("tags") or [] if isinstance(t, str)]))
    return web.json_response({**state(trip, member), "new_receipt": receipt_id})


def own_receipt(trip: dict, receipt_id: int) -> dict:
    receipt = store.one("SELECT * FROM receipts WHERE id = ? AND trip_id = ?", receipt_id, trip["id"])
    if not receipt:
        raise Fail(404, "Diesen Kassenzettel gibt es nicht mehr")
    return receipt


@routes.get("/api/receipts/{id}/bild")
async def receipt_image(request: web.Request) -> web.StreamResponse:
    member = store.member_by_token(request.query.get("t", ""))
    if not member:
        _, member = me(request)
    receipt = own_receipt(store.trip(member["trip_id"]), int(request.match_info["id"]))
    if not receipt["image"]:
        raise Fail(404, "Kein Bild")
    return web.FileResponse(receipt_dir(member["trip_id"]) / receipt["image"], headers={"Cache-Control": "private, max-age=86400"})


@routes.patch("/api/receipts/{id}")
async def edit_receipt(request: web.Request) -> web.Response:
    trip, member = me(request)
    receipt = own_receipt(trip, int(request.match_info["id"]))
    data = await body(request)
    ids = {m["id"] for m in store.members(trip["id"])}
    if "payer" in data and data["payer"] in ids:
        store.run("UPDATE receipts SET payer = ? WHERE id = ?", data["payer"], receipt["id"])
    if "store" in data:
        store.run("UPDATE receipts SET store = ? WHERE id = ?", text(data, "store", 80), receipt["id"])
    return web.json_response(state(trip, member))


@routes.delete("/api/receipts/{id}")
async def remove_receipt(request: web.Request) -> web.Response:
    trip, member = me(request)
    receipt = own_receipt(trip, int(request.match_info["id"]))
    if receipt["image"]:
        (receipt_dir(trip["id"]) / receipt["image"]).unlink(missing_ok=True)
    store.run("DELETE FROM receipts WHERE id = ?", receipt["id"])
    return web.json_response(state(trip, member))


@routes.post("/api/receipts/{id}/items")
async def add_item(request: web.Request) -> web.Response:
    trip, member = me(request)
    receipt = own_receipt(trip, int(request.match_info["id"]))
    store.run("INSERT INTO items (receipt_id, name, qty, price, sort) VALUES (?,?,?,?,?)", receipt["id"], "Neuer Artikel", 1, 0, 999)
    return web.json_response(state(trip, member))


@routes.patch("/api/items/{id}")
async def edit_item(request: web.Request) -> web.Response:
    trip, member = me(request)
    item = store.one("SELECT items.* FROM items JOIN receipts ON receipts.id = items.receipt_id WHERE items.id = ? AND receipts.trip_id = ?",
                     int(request.match_info["id"]), trip["id"])
    if not item:
        raise Fail(404, "Diesen Artikel gibt es nicht mehr")
    data = await body(request)
    if "name" in data:
        store.run("UPDATE items SET name = ? WHERE id = ?", text(data, "name", 80) or "?", item["id"])
    if "price" in data:
        try:
            store.run("UPDATE items SET price = ? WHERE id = ?", round(float(str(data["price"]).replace(",", ".")), 2), item["id"])
        except ValueError:
            raise Fail(400, "Bitte einen Preis eingeben")
    if isinstance(data.get("tags"), list):
        tag_ids = {t["id"] for t in store.tags(trip["id"])}
        store.run("UPDATE items SET tags = ?, people = '[]', unsure = 0 WHERE id = ?",
                  json.dumps([t for t in data["tags"] if t in tag_ids]), item["id"])
    if isinstance(data.get("people"), list):
        ids = {m["id"] for m in store.members(trip["id"])}
        store.run("UPDATE items SET people = ? WHERE id = ?", json.dumps([p for p in data["people"] if p in ids]), item["id"])
    return web.json_response(state(trip, member))


@routes.delete("/api/items/{id}")
async def remove_item(request: web.Request) -> web.Response:
    trip, member = me(request)
    store.run("DELETE FROM items WHERE id = ? AND receipt_id IN (SELECT id FROM receipts WHERE trip_id = ?)",
              int(request.match_info["id"]), trip["id"])
    return web.json_response(state(trip, member))


# -- app --------------------------------------------------------------------------------------------------
@web.middleware
async def errors(request: web.Request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except (ValueError, KeyError, TypeError) as err:
        log.warning("Ungültige Anfrage %s: %s", request.path, err)
        raise Fail(400, "Ungültige Anfrage")


def main() -> None:
    app = web.Application(middlewares=[errors], client_max_size=MAX_IMAGE + 1024 * 1024)
    app.add_routes(routes)
    app.router.add_static("/static/", STATIC)
    log.info("Anmeldung: %s", ", ".join(PROVIDERS[p]["title"] for p in login.available()) or "nicht eingerichtet (Schlüssel im Fabians-HA-Master)")
    if not ai.ready:
        log.warning("Kein Anthropic-API-Key gesetzt: Kassenzettel, Unterkunft-Vergleich und Geheimtipps sind aus")
    log.info("Urlaubsplaner läuft auf Port %s (Modell %s)", PORT, ai.model)
    web.run_app(app, port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
