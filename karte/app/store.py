"""Places, visits, menu items and photos in one SQLite file in /data (part of Home Assistant backups)."""

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, address TEXT DEFAULT '',
  kind TEXT DEFAULT 'restaurant', cuisine TEXT DEFAULT '', osm_id TEXT, osm TEXT DEFAULT '{}',
  from_menu TEXT DEFAULT '{}', online TEXT DEFAULT '{}', checked_at REAL, check_state TEXT DEFAULT '',
  note TEXT DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY, place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE, at REAL NOT NULL,
  ordered TEXT DEFAULT '[]', total REAL, rating REAL, note TEXT DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS dishes (
  id INTEGER PRIMARY KEY, place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  section TEXT DEFAULT '', name TEXT NOT NULL, price REAL, description TEXT DEFAULT '', seen REAL NOT NULL,
  UNIQUE (place_id, name));
CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY, place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL, file TEXT NOT NULL, kind TEXT DEFAULT 'foto',
  created REAL NOT NULL);
"""
JSON_COLS = ("osm", "from_menu", "online")


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

    # -- places -----------------------------------------------------------------------------------
    @staticmethod
    def _place(row: dict | None) -> dict | None:
        if row:
            for col in JSON_COLS:
                row[col] = json.loads(row.get(col) or "{}")
        return row

    def place(self, place_id: int) -> dict | None:
        return self._place(self.one("SELECT * FROM places WHERE id = ?", place_id))

    def place_by_osm(self, osm_id: str) -> dict | None:
        return self._place(self.one("SELECT * FROM places WHERE osm_id = ?", osm_id)) if osm_id else None

    def places(self) -> list[dict]:
        rows = self.q("""SELECT p.*, COUNT(v.id) AS visits, MAX(v.at) AS last_visit, AVG(v.rating) AS rating
                         FROM places p LEFT JOIN visits v ON v.place_id = p.id GROUP BY p.id ORDER BY last_visit DESC""")
        return [self._place(r) for r in rows]

    def add_place(self, **fields) -> int:
        now = time.time()
        for col in JSON_COLS:
            fields[col] = json.dumps(fields.get(col) or {}, ensure_ascii=False)
        cols = ", ".join(fields) + ", created, updated"
        return self.run(f"INSERT INTO places ({cols}) VALUES ({', '.join('?' * (len(fields) + 2))})",
                        *fields.values(), now, now)

    def update_place(self, place_id: int, **fields) -> None:
        for key, value in fields.items():   # keys come from the server code only
            if key in JSON_COLS:
                value = json.dumps(value or {}, ensure_ascii=False)
            self.run(f"UPDATE places SET {key} = ?, updated = ? WHERE id = ?", value, time.time(), place_id)

    def delete_place(self, place_id: int) -> list[str]:
        files = [p["file"] for p in self.q("SELECT file FROM photos WHERE place_id = ?", place_id)]
        self.run("DELETE FROM places WHERE id = ?", place_id)
        return files

    # -- visits, menu, photos ---------------------------------------------------------------------
    def add_visit(self, place_id: int, at: float, ordered: list, total, rating, note: str) -> int:
        return self.run("INSERT INTO visits (place_id, at, ordered, total, rating, note, created) VALUES (?,?,?,?,?,?,?)",
                        place_id, at, json.dumps(ordered, ensure_ascii=False), total, rating, note, time.time())

    def visits(self, place_id: int) -> list[dict]:
        rows = self.q("SELECT * FROM visits WHERE place_id = ? ORDER BY at DESC", place_id)
        for r in rows:
            r["ordered"] = json.loads(r["ordered"] or "[]")
            r["photos"] = [p["id"] for p in self.q("SELECT id FROM photos WHERE visit_id = ? ORDER BY id", r["id"])]
        return rows

    def rate_visit(self, visit_id: int, rating: float | None, note: str | None) -> None:
        if rating is not None:
            self.run("UPDATE visits SET rating = ? WHERE id = ?", rating, visit_id)
        if note is not None:
            self.run("UPDATE visits SET note = ? WHERE id = ?", note, visit_id)

    def save_dishes(self, place_id: int, dishes: list[dict]) -> int:
        now, n = time.time(), 0
        for d in dishes:
            self.run("""INSERT INTO dishes (place_id, section, name, price, description, seen) VALUES (?,?,?,?,?,?)
                        ON CONFLICT (place_id, name) DO UPDATE SET section = excluded.section,
                        price = COALESCE(excluded.price, dishes.price), description = excluded.description, seen = excluded.seen""",
                     place_id, d.get("section", ""), d["name"], d.get("price"), d.get("description", ""), now)
            n += 1
        return n

    def dishes(self, place_id: int) -> list[dict]:
        return self.q("SELECT section, name, price, description, seen FROM dishes WHERE place_id = ? ORDER BY section, id", place_id)

    def add_photo(self, place_id: int, visit_id: int | None, file: str, kind: str) -> int:
        return self.run("INSERT INTO photos (place_id, visit_id, file, kind, created) VALUES (?,?,?,?,?)",
                        place_id, visit_id, file, kind, time.time())

    def photo(self, photo_id: int) -> dict | None:
        return self.one("SELECT * FROM photos WHERE id = ?", photo_id)

    def photos(self, place_id: int) -> list[dict]:
        return self.q("SELECT id, visit_id, kind FROM photos WHERE place_id = ? ORDER BY id DESC", place_id)
