"""Player accounts: register with e-mail confirmation code, log in, reset the password by code.

Only logged-in players collect points and achievements in the Bestenliste. Data lives in the
add-on's private storage (/data/konten.sqlite3); passwords are stored as scrypt hashes, sessions and
codes only as SHA-256 hashes. The access code of the site stays in front of all of this.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from aiohttp import web

log = logging.getLogger("konten")

DATA = Path(os.environ.get("SPIELE_DATA", "/data"))
DB_FILE = DATA / "konten.sqlite3"
COOKIE = "spieleabend_konto"
SESSION_DAYS = 60
CODE_MINUTES = 30
CODE_TRIES = 5
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
NAME = re.compile(r"^[\wÄÖÜäöüß .'-]{2,20}$")


# -- mail ---------------------------------------------------------------------------------------
class Mail:
    def __init__(self, options: dict):
        self.host = str(options.get("smtp_host") or "").strip()
        self.port = int(options.get("smtp_port") or 587)
        self.user = str(options.get("smtp_user") or "").strip()
        self.password = str(options.get("smtp_password") or "")
        self.sender = str(options.get("smtp_from") or self.user).strip()
        self.tls = str(options.get("smtp_tls") or "starttls").lower()
        self.enabled = bool(self.host and self.sender)

    def _send(self, to: str, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = formataddr(("Spieleabend", self.sender))
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid(domain=self.sender.split("@")[-1] if "@" in self.sender else None)
        msg.set_content(text)
        context = ssl.create_default_context()
        if self.tls == "ssl":
            with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=20) as s:
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                if self.tls == "starttls":
                    s.starttls(context=context)
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(msg)

    async def send(self, to: str, subject: str, text: str) -> bool:
        if not self.enabled:
            # Without SMTP the code only goes to the add-on log, so the owner can pass it on.
            log.warning("Keine E-Mail eingerichtet – Nachricht an %s: %s\n%s", mask(to), subject, text)
            return False
        try:
            await asyncio.to_thread(self._send, to, subject, text)
            return True
        except (OSError, smtplib.SMTPException) as err:
            log.error("E-Mail an %s fehlgeschlagen: %s", mask(to), err)
            return False


def mask(email: str) -> str:
    name, _, domain = str(email).partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


# -- passwords and tokens -------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(test.hex(), digest)
    except (ValueError, TypeError):
        return False


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# -- database -------------------------------------------------------------------------------------
class Store:
    def __init__(self, path: Path = DB_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL; PRAGMA secure_delete=ON;
            CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL, email_key TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS codes (user_id TEXT NOT NULL, purpose TEXT NOT NULL, code_hash TEXT NOT NULL,
                expires REAL NOT NULL, tries INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, purpose));
        """)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def one(self, sql: str, args=()):
        return self.db.execute(sql, args).fetchone()

    def x(self, sql: str, args=()) -> None:
        with self.db:
            self.db.execute(sql, args)

    def by_email(self, email: str):
        return self.one("SELECT * FROM users WHERE email_key = ?", (email.strip().lower(),))

    def by_login(self, login: str):
        login = login.strip()
        return self.by_email(login) if "@" in login else self.one("SELECT * FROM users WHERE name_key = ?", (login.casefold(),))

    def by_session(self, token: str):
        if not token:
            return None
        return self.one("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires > ? "
                        "AND u.verified = 1", (sha(token), time.time()))

    def new_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.x("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        self.x("INSERT INTO sessions VALUES (?, ?, ?)", (sha(token), user_id, time.time() + SESSION_DAYS * 86400))
        return token

    def new_code(self, user_id: str, purpose: str) -> str:
        code = f"{secrets.randbelow(10 ** 6):06d}"
        self.x("INSERT OR REPLACE INTO codes VALUES (?, ?, ?, ?, 0)",
               (user_id, purpose, sha(f"{user_id}:{purpose}:{code}"), time.time() + CODE_MINUTES * 60))
        return code

    def use_code(self, user_id: str, purpose: str, code: str) -> bool:
        row = self.one("SELECT * FROM codes WHERE user_id = ? AND purpose = ?", (user_id, purpose))
        if not row or row["expires"] < time.time() or row["tries"] >= CODE_TRIES:
            return False
        if not hmac.compare_digest(row["code_hash"], sha(f"{user_id}:{purpose}:{re.sub(r'[^0-9]', '', code)}")):
            self.x("UPDATE codes SET tries = tries + 1 WHERE user_id = ? AND purpose = ?", (user_id, purpose))
            return False
        self.x("DELETE FROM codes WHERE user_id = ? AND purpose = ?", (user_id, purpose))
        return True


# -- web API --------------------------------------------------------------------------------------
class Limiter:
    def __init__(self) -> None:
        self.hits: dict[tuple, list[float]] = {}

    def check(self, ip: str, action: str, limit: int, window: float) -> None:
        now = time.time()
        hits = [t for t in self.hits.get((ip, action), []) if now - t < window]
        if len(hits) >= limit:
            raise web.HTTPTooManyRequests(text=json.dumps({"error": "Zu viele Versuche – bitte warte ein paar Minuten"}),
                                          content_type="application/json")
        self.hits[(ip, action)] = hits + [now]


class Accounts:
    """Routes under /api/konto/ – the page is /konto/."""

    def __init__(self, options: dict, client_ip, on_delete=None):
        self.store = Store()
        self.mail = Mail(options)
        self.client_ip = client_ip
        self.on_delete = on_delete
        self.limiter = Limiter()

    def name_taken(self, name: str) -> bool:
        return bool(self.store.one("SELECT 1 FROM users WHERE name_key = ? AND verified = 1", (" ".join(name.split()).casefold(),)))

    def user(self, request: web.Request):
        return self.store.by_session(request.cookies.get(COOKIE, ""))

    @staticmethod
    def public(user) -> dict | None:
        return {"id": user["id"], "name": user["name"], "email": mask(user["email"])} if user else None

    def login_response(self, request: web.Request, user) -> web.Response:
        response = web.json_response({"user": self.public(user)})
        secure = request.secure or request.headers.get("X-Forwarded-Proto") == "https"
        response.set_cookie(COOKIE, self.store.new_session(user["id"]), max_age=SESSION_DAYS * 86400, path="/",
                            httponly=True, samesite="Lax", secure=secure)
        return response

    @staticmethod
    def fail(message: str, status: int = 400, **extra) -> web.Response:
        return web.json_response({"error": message, **extra}, status=status)

    @staticmethod
    async def body(request: web.Request) -> dict:
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}

    async def send_code(self, user, purpose: str) -> bool:
        code = self.store.new_code(user["id"], purpose)
        if purpose == "verify":
            subject = f"Spieleabend: dein Bestätigungscode {code}"
            text = (f"Hallo {user['name']},\n\ndein Bestätigungscode für den Spieleabend lautet:\n\n    {code}\n\n"
                    f"Er gilt {CODE_MINUTES} Minuten. Wenn du dich nicht registriert hast, ignoriere diese E-Mail.\n")
        else:
            subject = f"Spieleabend: Code zum Zurücksetzen {code}"
            text = (f"Hallo {user['name']},\n\nmit diesem Code setzt du dein Passwort zurück:\n\n    {code}\n\n"
                    f"Er gilt {CODE_MINUTES} Minuten. Wenn du das nicht angefordert hast, ignoriere diese E-Mail – "
                    "dein Passwort bleibt dann wie es ist.\n")
        return await self.mail.send(user["email"], subject, text)

    # -- handlers ------------------------------------------------------------------------------
    async def me(self, request: web.Request) -> web.Response:
        return web.json_response({"user": self.public(self.user(request)), "mail": self.mail.enabled},
                                 headers={"Cache-Control": "no-store"})

    async def register(self, request: web.Request) -> web.Response:
        self.limiter.check(self.client_ip(request), "register", 6, 3600)
        data = await self.body(request)
        name = " ".join(str(data.get("name") or "").split())
        email = str(data.get("email") or "").strip().lower()
        password = str(data.get("password") or "")
        if not NAME.match(name):
            return self.fail("Der Name braucht 2 bis 20 Zeichen (Buchstaben, Zahlen, Leerzeichen)")
        if not EMAIL.match(email):
            return self.fail("Bitte gib eine gültige E-Mail-Adresse ein")
        if len(password) < 8:
            return self.fail("Das Passwort braucht mindestens 8 Zeichen")
        existing = self.store.by_email(email)
        if existing and existing["verified"]:
            return self.fail("Zu dieser E-Mail gibt es schon ein Konto – melde dich an oder setze das Passwort zurück")
        taken = self.store.one("SELECT id FROM users WHERE name_key = ?", (name.casefold(),))
        if taken and (not existing or taken["id"] != existing["id"]):
            return self.fail("Diesen Namen gibt es schon – bitte wähle einen anderen")
        if existing:      # registered before but never confirmed: start over
            self.store.x("UPDATE users SET name = ?, name_key = ?, pw = ? WHERE id = ?",
                         (name, name.casefold(), (await asyncio.to_thread(hash_password, password)), existing["id"]))
            user_id = existing["id"]
        else:
            user_id = secrets.token_hex(8)
            self.store.x("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                         (user_id, name, name.casefold(), email, email, (await asyncio.to_thread(hash_password, password)), time.time()))
        sent = await self.send_code(self.store.one("SELECT * FROM users WHERE id = ?", (user_id,)), "verify")
        log.info("Neues Konto: %s (%s)", name, mask(email))
        return web.json_response({"next": "verify", "email": email, "sent": sent})

    async def verify(self, request: web.Request) -> web.Response:
        self.limiter.check(self.client_ip(request), "verify", 20, 900)
        data = await self.body(request)
        user = self.store.by_email(str(data.get("email") or ""))
        if not user or not self.store.use_code(user["id"], "verify", str(data.get("code") or "")):
            return self.fail("Der Code stimmt nicht oder ist abgelaufen – fordere einen neuen an")
        self.store.x("UPDATE users SET verified = 1 WHERE id = ?", (user["id"],))
        return self.login_response(request, self.store.one("SELECT * FROM users WHERE id = ?", (user["id"],)))

    async def resend(self, request: web.Request) -> web.Response:
        self.limiter.check(self.client_ip(request), "resend", 5, 3600)
        data = await self.body(request)
        user = self.store.by_email(str(data.get("email") or ""))
        if user and not user["verified"]:
            await self.send_code(user, "verify")
        return web.json_response({"ok": True})

    async def login(self, request: web.Request) -> web.Response:
        self.limiter.check(self.client_ip(request), "login", 10, 900)
        data = await self.body(request)
        user = self.store.by_login(str(data.get("login") or ""))
        if not user or not await asyncio.to_thread(check_password, str(data.get("password") or ""), user["pw"]):
            return self.fail("Name/E-Mail oder Passwort stimmt nicht", 401)
        if not user["verified"]:
            await self.send_code(user, "verify")
            return self.fail("Bitte bestätige zuerst deine E-Mail – wir haben dir einen neuen Code geschickt", 403,
                             next="verify", email=user["email"])
        return self.login_response(request, user)

    async def logout(self, request: web.Request) -> web.Response:
        token = request.cookies.get(COOKIE, "")
        if token:
            self.store.x("DELETE FROM sessions WHERE token_hash = ?", (sha(token),))
        response = web.json_response({"ok": True})
        response.del_cookie(COOKIE, path="/")
        return response

    async def forgot(self, request: web.Request) -> web.Response:
        self.limiter.check(self.client_ip(request), "forgot", 5, 3600)
        data = await self.body(request)
        user = self.store.by_email(str(data.get("email") or ""))
        if user:
            await self.send_code(user, "reset")
        # Same answer either way: nobody can find out which addresses have an account.
        return web.json_response({"next": "reset", "email": str(data.get("email") or "").strip().lower()})

    async def reset(self, request: web.Request) -> web.Response:
        self.limiter.check(self.client_ip(request), "reset", 20, 900)
        data = await self.body(request)
        password = str(data.get("password") or "")
        if len(password) < 8:
            return self.fail("Das Passwort braucht mindestens 8 Zeichen")
        user = self.store.by_email(str(data.get("email") or ""))
        if not user or not self.store.use_code(user["id"], "reset", str(data.get("code") or "")):
            return self.fail("Der Code stimmt nicht oder ist abgelaufen – fordere einen neuen an")
        # The code came by e-mail, so the address is confirmed too.
        self.store.x("UPDATE users SET pw = ?, verified = 1 WHERE id = ?", ((await asyncio.to_thread(hash_password, password)), user["id"]))
        self.store.x("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        return self.login_response(request, self.store.one("SELECT * FROM users WHERE id = ?", (user["id"],)))

    async def change_password(self, request: web.Request) -> web.Response:
        user = self.user(request)
        if not user:
            return self.fail("Bitte melde dich an", 401)
        self.limiter.check(self.client_ip(request), "password", 10, 900)
        data = await self.body(request)
        if not await asyncio.to_thread(check_password, str(data.get("old") or ""), user["pw"]):
            return self.fail("Das aktuelle Passwort stimmt nicht")
        if len(str(data.get("new") or "")) < 8:
            return self.fail("Das neue Passwort braucht mindestens 8 Zeichen")
        self.store.x("UPDATE users SET pw = ? WHERE id = ?", ((await asyncio.to_thread(hash_password, str(data["new"]))), user["id"]))
        self.store.x("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user["id"], sha(request.cookies.get(COOKIE, ""))))
        return web.json_response({"ok": True})

    async def delete(self, request: web.Request) -> web.Response:
        user = self.user(request)
        if not user:
            return self.fail("Bitte melde dich an", 401)
        data = await self.body(request)
        if not await asyncio.to_thread(check_password, str(data.get("password") or ""), user["pw"]):
            return self.fail("Das Passwort stimmt nicht")
        for table, column in (("sessions", "user_id"), ("codes", "user_id"), ("users", "id")):
            self.store.x(f"DELETE FROM {table} WHERE {column} = ?", (user["id"],))
        if self.on_delete:
            await self.on_delete(user["id"])
        log.info("Konto gelöscht: %s", user["name"])
        response = web.json_response({"ok": True})
        response.del_cookie(COOKIE, path="/")
        return response

    def routes(self) -> list:
        return [web.get("/api/konto", self.me), web.post("/api/konto/register", self.register),
                web.post("/api/konto/verify", self.verify), web.post("/api/konto/resend", self.resend),
                web.post("/api/konto/login", self.login), web.post("/api/konto/logout", self.logout),
                web.post("/api/konto/forgot", self.forgot), web.post("/api/konto/reset", self.reset),
                web.post("/api/konto/password", self.change_password), web.post("/api/konto/delete", self.delete)]
