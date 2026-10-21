"""Everything is kept in one SQLite file in the add-on's /data folder (part of Home Assistant backups)."""

import hashlib
import json
import secrets
import sqlite3
import string
import time
from pathlib import Path

DEFAULT_TAGS = [
    # id, name, parent, icon
    ("alkohol", "Alkohol", None, "🍷"),
    ("bier", "Bier", "alkohol", "🍺"),
    ("wein", "Wein & Sekt", "alkohol", "🥂"),
    ("schnaps", "Vodka & Schnaps", "alkohol", "🥃"),
    ("fleisch", "Fleisch & Wurst", None, "🥩"),
    ("tabak", "Zigaretten & Tabak", None, "🚬"),
]
CODE_LETTERS = "".join(c for c in string.ascii_uppercase if c not in "IO") + "23456789"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
  id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, destination TEXT NOT NULL,
  start TEXT, end TEXT, lat REAL, lon REAL, place TEXT, wishes TEXT DEFAULT '', currency TEXT DEFAULT 'EUR',
  spots TEXT, spots_at REAL, ranking TEXT, ranking_at REAL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS members (
  id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, name TEXT NOT NULL,
  token TEXT UNIQUE NOT NULL, owner INTEGER DEFAULT 0, answers TEXT DEFAULT '{}', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS tags (
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, id TEXT NOT NULL, name TEXT NOT NULL,
  parent TEXT, icon TEXT DEFAULT '🏷️', sort INTEGER DEFAULT 0, PRIMARY KEY (trip_id, id));
CREATE TABLE IF NOT EXISTS stays (
  id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, url TEXT,
  data TEXT DEFAULT '{}', manual TEXT DEFAULT '{}', near TEXT, added_by INTEGER, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS votes (
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, kind TEXT NOT NULL, ref TEXT NOT NULL,
  member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE, PRIMARY KEY (kind, ref, member_id));
CREATE TABLE IF NOT EXISTS receipts (
  id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, payer INTEGER,
  store TEXT DEFAULT '', date TEXT DEFAULT '', currency TEXT DEFAULT 'EUR', total REAL, image TEXT,
  status TEXT DEFAULT 'ok', note TEXT DEFAULT '', added_by INTEGER, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY, receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
  name TEXT NOT NULL, qty REAL DEFAULT 1, price REAL NOT NULL, tags TEXT DEFAULT '[]', people TEXT DEFAULT '[]',
  unsure INTEGER DEFAULT 0, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS polls (
  id INTEGER PRIMARY KEY, trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE, question TEXT NOT NULL,
  kind TEXT DEFAULT '', multi INTEGER DEFAULT 1, closed INTEGER DEFAULT 0, created_by INTEGER, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS poll_options (
  id INTEGER PRIMARY KEY, poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE, text TEXT NOT NULL,
  added_by INTEGER, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS poll_votes (
  option_id INTEGER NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
  member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE, PRIMARY KEY (option_id, member_id));
CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY, provider TEXT NOT NULL, sub TEXT NOT NULL, email TEXT DEFAULT '', name TEXT DEFAULT '',
  created REAL NOT NULL, UNIQUE (provider, sub));
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, created REAL NOT NULL, used REAL);
"""
SESSION_DAYS = 180


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(SCHEMA)
        if "account_id" not in {c["name"] for c in self.q("PRAGMA table_info(members)")}:     # added in 1.2.0
            self.db.execute("ALTER TABLE members ADD COLUMN account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL")

    def q(self, sql: str, *args) -> list[dict]:
        return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def one(self, sql: str, *args) -> dict | None:
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def run(self, sql: str, *args) -> int:
        return self.db.execute(sql, args).lastrowid

    # -- trips & members ---------------------------------------------------------------------------
    def new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_LETTERS) for _ in range(6))
            if not self.one("SELECT 1 FROM trips WHERE code = ?", code):
                return code

    def create_trip(self, name: str, destination: str, start: str, end: str, owner: str, place: dict | None,
                    account_id: int | None = None) -> tuple[dict, str]:
        code = self.new_code()
        trip_id = self.run("INSERT INTO trips (code, name, destination, start, end, lat, lon, place, created) VALUES (?,?,?,?,?,?,?,?,?)",
                           code, name, destination, start, end, place and place["lat"], place and place["lon"],
                           place and place["name"], time.time())
        for i, (tid, tname, parent, icon) in enumerate(DEFAULT_TAGS):
            self.run("INSERT INTO tags (trip_id, id, name, parent, icon, sort) VALUES (?,?,?,?,?,?)", trip_id, tid, tname, parent, icon, i)
        token = self.add_member(trip_id, owner, owner=True, account_id=account_id)
        return self.trip(trip_id), token

    def add_member(self, trip_id: int, name: str, owner: bool = False, account_id: int | None = None) -> str:
        token = secrets.token_urlsafe(24)
        self.run("INSERT INTO members (trip_id, name, token, owner, account_id, created) VALUES (?,?,?,?,?,?)",
                 trip_id, name, token_hash(token), int(owner), account_id, time.time())
        return token

    def trip(self, trip_id: int) -> dict | None:
        return self.one("SELECT * FROM trips WHERE id = ?", trip_id)

    def trip_by_code(self, code: str) -> dict | None:
        return self.one("SELECT * FROM trips WHERE code = ?", code.strip().upper())

    def member_by_token(self, token: str) -> dict | None:
        return self.one("SELECT * FROM members WHERE token = ?", token_hash(token)) if token else None

    def members(self, trip_id: int) -> list[dict]:
        out = self.q("SELECT id, name, owner, answers FROM members WHERE trip_id = ? ORDER BY id", trip_id)
        for m in out:
            m["answers"] = json.loads(m["answers"] or "{}")
            m["owner"] = bool(m["owner"])
        return out

    def tags(self, trip_id: int) -> list[dict]:
        return self.q("SELECT id, name, parent, icon FROM tags WHERE trip_id = ? ORDER BY sort, name", trip_id)

    def update_trip(self, trip_id: int, **fields) -> None:
        for key, value in fields.items():
            self.run(f"UPDATE trips SET {key} = ? WHERE id = ?", value, trip_id)   # keys come from the server code only

    # -- votes ----------------------------------------------------------------------------------------
    def toggle_vote(self, trip_id: int, kind: str, ref: str, member_id: int) -> None:
        if self.one("SELECT 1 FROM votes WHERE kind = ? AND ref = ? AND member_id = ?", kind, ref, member_id):
            self.run("DELETE FROM votes WHERE kind = ? AND ref = ? AND member_id = ?", kind, ref, member_id)
        else:
            self.run("INSERT INTO votes (trip_id, kind, ref, member_id) VALUES (?,?,?,?)", trip_id, kind, ref, member_id)

    def votes(self, trip_id: int, kind: str) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        for v in self.q("SELECT ref, member_id FROM votes WHERE trip_id = ? AND kind = ?", trip_id, kind):
            out.setdefault(v["ref"], []).append(v["member_id"])
        return out

    # -- accounts -------------------------------------------------------------------------------------
    def sign_in(self, provider: str, sub: str, email: str, name: str) -> tuple[dict, str]:
        """The first sign-in registers the account. Returns the account and a new session token."""
        account = self.one("SELECT * FROM accounts WHERE provider = ? AND sub = ?", provider, sub)
        if not account:
            account_id = self.run("INSERT INTO accounts (provider, sub, email, name, created) VALUES (?,?,?,?,?)",
                                  provider, sub, email, name, time.time())
        else:
            account_id = account["id"]
            self.run("UPDATE accounts SET email = COALESCE(NULLIF(?, ''), email), name = COALESCE(NULLIF(?, ''), name) WHERE id = ?",
                     email, name, account_id)
        token = secrets.token_urlsafe(32)
        self.run("INSERT INTO sessions (token, account_id, created, used) VALUES (?,?,?,?)", token_hash(token), account_id, time.time(), time.time())
        return self.one("SELECT * FROM accounts WHERE id = ?", account_id), token

    def account_by_session(self, token: str) -> dict | None:
        if not token:
            return None
        row = self.one("SELECT accounts.*, sessions.used FROM sessions JOIN accounts ON accounts.id = sessions.account_id WHERE sessions.token = ?",
                       token_hash(token))
        if not row:
            return None
        if time.time() - (row["used"] or 0) > SESSION_DAYS * 86400:
            self.run("DELETE FROM sessions WHERE token = ?", token_hash(token))
            return None
        if time.time() - (row["used"] or 0) > 3600:
            self.run("UPDATE sessions SET used = ? WHERE token = ?", time.time(), token_hash(token))
        return row

    def sign_out(self, token: str) -> None:
        self.run("DELETE FROM sessions WHERE token = ?", token_hash(token))

    def account_trips(self, account_id: int) -> list[dict]:
        return self.q("SELECT trips.code, trips.name AS trip, trips.destination AS \"where\", members.name FROM members "
                      "JOIN trips ON trips.id = members.trip_id WHERE members.account_id = ? ORDER BY trips.created DESC", account_id)

    def member_by_account(self, code: str, account_id: int) -> dict | None:
        return self.one("SELECT members.* FROM members JOIN trips ON trips.id = members.trip_id WHERE trips.code = ? AND members.account_id = ?",
                        code.strip().upper(), account_id)

    # -- polls ----------------------------------------------------------------------------------------
    def add_poll(self, trip_id: int, question: str, kind: str, multi: bool, options: list[str], member_id: int) -> int:
        poll_id = self.run("INSERT INTO polls (trip_id, question, kind, multi, created_by, created) VALUES (?,?,?,?,?,?)",
                           trip_id, question, kind, int(multi), member_id, time.time())
        for text in options:
            self.run("INSERT INTO poll_options (poll_id, text, added_by, created) VALUES (?,?,?,?)", poll_id, text, member_id, time.time())
        return poll_id

    def polls(self, trip_id: int) -> list[dict]:
        out = self.q("SELECT id, question, kind, multi, closed, created_by FROM polls WHERE trip_id = ? ORDER BY closed, id DESC", trip_id)
        for p in out:
            p["multi"], p["closed"] = bool(p["multi"]), bool(p["closed"])
            p["options"] = self.q("SELECT id, text, added_by FROM poll_options WHERE poll_id = ? ORDER BY id", p["id"])
            for o in p["options"]:
                o["votes"] = [v["member_id"] for v in self.q("SELECT member_id FROM poll_votes WHERE option_id = ?", o["id"])]
        return out

    def toggle_poll_vote(self, poll: dict, option_id: int, member_id: int) -> None:
        if self.one("SELECT 1 FROM poll_votes WHERE option_id = ? AND member_id = ?", option_id, member_id):
            self.run("DELETE FROM poll_votes WHERE option_id = ? AND member_id = ?", option_id, member_id)
            return
        if not poll["multi"]:      # one vote per person: the new choice replaces the old one
            self.run("DELETE FROM poll_votes WHERE member_id = ? AND option_id IN (SELECT id FROM poll_options WHERE poll_id = ?)",
                     member_id, poll["id"])
        self.run("INSERT INTO poll_votes (option_id, member_id) VALUES (?,?)", option_id, member_id)

    # -- receipts ---------------------------------------------------------------------------------------
    def receipts(self, trip_id: int) -> list[dict]:
        out = self.q("SELECT * FROM receipts WHERE trip_id = ? ORDER BY created DESC", trip_id)
        for r in out:
            r["items"] = self.q("SELECT * FROM items WHERE receipt_id = ? ORDER BY sort, id", r["id"])
            for item in r["items"]:
                item["tags"] = json.loads(item["tags"] or "[]")
                item["people"] = json.loads(item["people"] or "[]")
                item["unsure"] = bool(item["unsure"])
        return out
