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
"""


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

    def create_trip(self, name: str, destination: str, start: str, end: str, owner: str, place: dict | None) -> tuple[dict, str]:
        code = self.new_code()
        trip_id = self.run("INSERT INTO trips (code, name, destination, start, end, lat, lon, place, created) VALUES (?,?,?,?,?,?,?,?,?)",
                           code, name, destination, start, end, place and place["lat"], place and place["lon"],
                           place and place["name"], time.time())
        for i, (tid, tname, parent, icon) in enumerate(DEFAULT_TAGS):
            self.run("INSERT INTO tags (trip_id, id, name, parent, icon, sort) VALUES (?,?,?,?,?,?)", trip_id, tid, tname, parent, icon, i)
        token = self.add_member(trip_id, owner, owner=True)
        return self.trip(trip_id), token

    def add_member(self, trip_id: int, name: str, owner: bool = False) -> str:
        token = secrets.token_urlsafe(24)
        self.run("INSERT INTO members (trip_id, name, token, owner, created) VALUES (?,?,?,?,?)",
                 trip_id, name, token_hash(token), int(owner), time.time())
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
