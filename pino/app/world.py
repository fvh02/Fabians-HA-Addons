"""Pino's world: a square grid with buildings on it.

A building type says how a building looks (simple 3D shapes), how big it is and what Pino can do inside
(activities with effects on his needs and an optional action like reading Wikipedia). The built-in types
are always there; new ones come from the building creator (Claude). Placed buildings are instances of a
type with a position and rotation. Pino walks on free cells (A*) to the door in front of a building.
"""

import heapq
import json
import re
import secrets
from pathlib import Path

SIZE = 32  # cells per side
NEEDS = ["durst", "hunger", "muedigkeit", "langeweile", "neugier"]
NEED_NAMES = {"durst": "Durst", "hunger": "Hunger", "muedigkeit": "Müdigkeit", "langeweile": "Langeweile",
              "neugier": "Neugier"}
ACTIONS = {
    "keine": "nur die Wirkung auf die Bedürfnisse",
    "frei": "Pino erlebt etwas, das zur Beschreibung passt, und erzählt davon (kann Interessen wecken)",
    "schlafen": "schlafen (nachts bis zum Morgen)",
    "tagebuch": "Tagebuch schreiben und über den Tag nachdenken",
    "wikipedia": "einen Wikipedia-Artikel zu einem seiner Interessen lesen",
    "youtube": "auf YouTube nach Videos zu einem Interesse suchen",
    "github": "auf GitHub Projekte zu einem Interesse ansehen",
    "werkstatt": "an einer eigenen Webseite bauen (Claude)",
    "malen": "ein Bild malen",
}
SHAPES = ["box", "cylinder", "cone", "sphere"]
FRONT = {0: (0, 1), 90: (1, 0), 180: (0, -1), 270: (-1, 0)}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _p(shape, pos, size, color, rot=0):
    return {"shape": shape, "pos": pos, "size": size, "color": color, "rot": rot}


def _act(id_, name, minutes, effects, action="keine", prompt=""):
    return {"id": id_, "name": name, "minutes": minutes, "effects": effects, "action": action, "prompt": prompt}


# Coordinates of parts: x/z in cells from the footprint centre, y up; front (door) is +z.
BUILTIN = [
    {"id": "nest", "name": "Nest", "emoji": "🪺", "size": [2, 2], "description": "Pinos Zuhause zum Schlafen.",
     "parts": [_p("cylinder", [0, 0.25, 0], [1.8, 0.5, 1.8], "#8b6b3e"), _p("cone", [0, 0.95, 0], [2.0, 0.9, 2.0], "#5c4327"),
               _p("box", [0, 0.3, 0.9], [0.5, 0.6, 0.05], "#3b2a18")],
     "activities": [_act("schlafen", "Schlafen", 480, {"muedigkeit": -100}, "schlafen", "Pino schläft im Nest."),
                    _act("tagebuch", "Tagebuch schreiben", 20, {"langeweile": -15}, "tagebuch", "Pino schreibt Tagebuch.")]},
    {"id": "starbucks", "name": "Starbucks", "emoji": "☕", "size": [2, 2], "description": "Kaffee gegen Durst und Müdigkeit.",
     "parts": [_p("box", [0, 0.7, 0], [1.9, 1.4, 1.9], "#efe6d6"), _p("box", [0, 1.5, 0], [2.0, 0.2, 2.0], "#00704a"),
               _p("cylinder", [0, 1.85, 0.6], [0.5, 0.5, 0.05], "#00704a", 0), _p("box", [0, 0.45, 0.96], [0.5, 0.9, 0.05], "#5a3d24")],
     "activities": [_act("kaffee", "Kaffee trinken", 20, {"durst": -50, "muedigkeit": -25}, "keine", "Pino trinkt einen Kaffee."),
                    _act("kakao", "Heiße Schokolade", 15, {"durst": -40, "langeweile": -10}, "keine", "Pino trinkt Kakao.")]},
    {"id": "imbiss", "name": "Imbiss", "emoji": "🍜", "size": [2, 2], "description": "Hier gibt es Essen.",
     "parts": [_p("box", [0, 0.6, 0], [1.8, 1.2, 1.8], "#f2c14e"), _p("box", [0, 1.3, 0.3], [2.0, 0.15, 1.6], "#d1495b"),
               _p("box", [0, 0.45, 0.91], [0.5, 0.9, 0.05], "#6b4226")],
     "activities": [_act("essen", "Würmer und Beeren essen", 30, {"hunger": -60}, "keine", "Pino isst."),
                    _act("snack", "Kleiner Snack", 10, {"hunger": -25}, "keine", "Pino nascht etwas.")]},
    {"id": "internetcafe", "name": "Internetcafé", "emoji": "💻", "size": [2, 2],
     "description": "Hier kommt Pino ins Internet: Wikipedia, YouTube und GitHub.",
     "parts": [_p("box", [0, 0.8, 0], [1.9, 1.6, 1.9], "#4a6fa5"), _p("box", [0, 1.7, 0], [2.0, 0.2, 2.0], "#2b3a55"),
               _p("box", [0, 1.1, 0.96], [1.2, 0.5, 0.05], "#9ad1ff"), _p("box", [0.55, 0.45, 0.96], [0.45, 0.9, 0.05], "#24324a")],
     "activities": [_act("wikipedia", "Auf Wikipedia lesen", 30, {"neugier": -40, "langeweile": -20}, "wikipedia"),
                    _act("youtube", "YouTube-Videos suchen", 30, {"neugier": -30, "langeweile": -30}, "youtube"),
                    _act("github", "GitHub-Projekte ansehen", 30, {"neugier": -35, "langeweile": -15}, "github")]},
    {"id": "werkstatt", "name": "Werkstatt", "emoji": "🛠️", "size": [2, 3],
     "description": "Hier baut Pino eigene Webseiten über seine Interessen.",
     "parts": [_p("box", [0, 0.8, 0], [1.9, 1.6, 2.8], "#a0522d"), _p("box", [0, 1.75, 0], [2.1, 0.3, 3.0], "#5b2c11"),
               _p("box", [0, 0.6, 1.41], [0.9, 1.2, 0.05], "#3b1f0e"), _p("cylinder", [0.6, 2.1, -0.8], [0.3, 0.6, 0.3], "#777777")],
     "activities": [_act("webseite", "An einer Webseite bauen", 45, {"langeweile": -45, "neugier": -10}, "werkstatt")]},
    {"id": "atelier", "name": "Atelier", "emoji": "🎨", "size": [2, 2], "description": "Hier malt Pino Bilder.",
     "parts": [_p("box", [0, 0.7, 0], [1.8, 1.4, 1.8], "#f4f1de"), _p("cone", [0, 1.75, 0], [1.6, 0.7, 1.6], "#e07a5f"),
               _p("box", [0, 0.45, 0.91], [0.5, 0.9, 0.05], "#3d405b"), _p("box", [-0.5, 1.0, 0.91], [0.4, 0.4, 0.05], "#81b29a")],
     "activities": [_act("malen", "Ein Bild malen", 40, {"langeweile": -50}, "malen")]},
    {"id": "park", "name": "Park", "emoji": "🌳", "size": [3, 3], "description": "Spazieren und nachdenken.",
     "parts": [_p("box", [0, 0.03, 0], [2.9, 0.06, 2.9], "#6a994e"), _p("cylinder", [-0.8, 0.5, -0.8], [0.2, 1.0, 0.2], "#6f4e37"),
               _p("sphere", [-0.8, 1.3, -0.8], [1.0, 1.0, 1.0], "#386641"), _p("box", [0.6, 0.25, 0.6], [1.0, 0.1, 0.35], "#9c6644"),
               _p("cylinder", [0.9, 0.08, -0.6], [0.9, 0.08, 0.9], "#5fa8d3")],
     "activities": [_act("spazieren", "Spazieren gehen", 20, {"langeweile": -25, "muedigkeit": 5}, "frei",
                         "Pino spaziert durch den Park und beobachtet, was um ihn herum passiert."),
                    _act("nachdenken", "Auf der Bank nachdenken", 15, {"langeweile": -15, "neugier": 10}, "frei",
                         "Pino sitzt auf der Bank und denkt über seine Interessen nach.")]},
    {"id": "baum", "name": "Baum", "emoji": "🌲", "size": [1, 1], "description": "Deko.", "decor": True,
     "parts": [_p("cylinder", [0, 0.35, 0], [0.18, 0.7, 0.18], "#6f4e37"), _p("cone", [0, 1.1, 0], [0.8, 1.2, 0.8], "#2d6a4f")],
     "activities": []},
    {"id": "teich", "name": "Teich", "emoji": "💧", "size": [2, 2], "description": "Deko.", "decor": True,
     "parts": [_p("cylinder", [0, 0.04, 0], [1.9, 0.08, 1.9], "#48cae4"), _p("cylinder", [0, 0.02, 0], [2.0, 0.04, 2.0], "#adb5bd")],
     "activities": []},
]
START_LAYOUT = [("nest", 6, 6, 0), ("starbucks", 12, 6, 0), ("imbiss", 18, 6, 0), ("internetcafe", 6, 14, 0),
                ("werkstatt", 12, 14, 0), ("atelier", 18, 14, 0), ("park", 24, 9, 0),
                ("baum", 4, 22, 0), ("baum", 9, 24, 0), ("baum", 26, 20, 0), ("teich", 20, 22, 0)]


class WorldError(Exception):
    pass


# -- validating building types (they may come from Claude) ------------------------------------------------
def _num(value, lo, hi, default):
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _text(value, limit) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def clean_type(raw: dict, type_id: str) -> dict:
    """A building type from Claude, checked and clamped so it can never break the world."""
    if not isinstance(raw, dict):
        raise WorldError("Ungültiger Gebäudetyp")
    w = int(_num((raw.get("size") or [2, 2])[0], 1, 4, 2))
    d = int(_num((raw.get("size") or [2, 2])[1] if len(raw.get("size") or []) > 1 else 2, 1, 4, 2))
    parts = []
    for p in (raw.get("parts") or [])[:40]:
        if not isinstance(p, dict) or p.get("shape") not in SHAPES:
            continue
        pos = (list(p.get("pos") or []) + [0, 0, 0])[:3]
        size = (list(p.get("size") or []) + [1, 1, 1])[:3]
        color = str(p.get("color") or "#cccccc")
        parts.append({"shape": p["shape"],
                      "pos": [_num(pos[0], -w / 2, w / 2, 0), _num(pos[1], 0, 6, 0.5), _num(pos[2], -d / 2, d / 2, 0)],
                      "size": [_num(size[0], 0.02, w, 1), _num(size[1], 0.02, 6, 1), _num(size[2], 0.02, d, 1)],
                      "color": color if HEX.match(color) else "#cccccc", "rot": _num(p.get("rot"), -180, 180, 0)})
    if not parts:
        parts = [_p("box", [0, 0.6, 0], [w * 0.9, 1.2, d * 0.9], "#cccccc")]
    decor = bool(raw.get("decor"))
    activities = []
    for i, a in enumerate((raw.get("activities") or [])[:6]):
        if not isinstance(a, dict) or decor:
            continue
        effects = {}
        for need, value in (a.get("effects") or {}).items():
            if need in NEEDS:
                effects[need] = int(_num(value, -100, 50, 0))
        action = a.get("action") if a.get("action") in ACTIONS else "frei"
        activities.append({"id": re.sub(r"[^a-z0-9_]", "", str(a.get("id") or "").lower())[:24] or f"a{i}",
                           "name": _text(a.get("name"), 40) or f"Aktivität {i + 1}",
                           "minutes": int(_num(a.get("minutes"), 5, 600, 20)), "effects": effects, "action": action,
                           "prompt": _text(a.get("prompt"), 400)})
    if not activities and not decor:
        decor = True
    ids = set()
    for a in activities:  # activity ids must be unique within the type
        while a["id"] in ids:
            a["id"] += "x"
        ids.add(a["id"])
    return {"id": type_id, "name": _text(raw.get("name"), 30) or "Gebäude", "emoji": _text(raw.get("emoji"), 4) or "🏠",
            "size": [w, d], "description": _text(raw.get("description"), 300), "parts": parts,
            "activities": activities, "decor": decor, "custom": True,
            "request": _text(raw.get("request"), 1000)}


# -- the world ----------------------------------------------------------------------------------------------
class World:
    def __init__(self, file: Path):
        self.file = file
        self.custom: dict[str, dict] = {}
        self.buildings: list[dict] = []
        self.version = 0
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.file.read_text())
            self.custom = {t["id"]: t for t in data.get("custom", [])}
            self.buildings = data.get("buildings", [])
        except (OSError, ValueError):
            self.custom = {}
            self.buildings = []
            for type_id, x, z, rot in START_LAYOUT:
                try:
                    self.place(type_id, x, z, rot, save=False)
                except WorldError:
                    pass
            self.save()

    def save(self) -> None:
        self.version += 1
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"custom": list(self.custom.values()), "buildings": self.buildings}, ensure_ascii=False))
        tmp.replace(self.file)

    # -- types -------------------------------------------------------------------------------------------
    def types(self) -> dict[str, dict]:
        return {**{t["id"]: t for t in BUILTIN}, **self.custom}

    def type_of(self, building: dict) -> dict | None:
        return self.types().get(building["type"])

    def add_type(self, raw: dict, type_id: str | None = None) -> dict:
        type_id = type_id or "eigen_" + secrets.token_hex(3)
        if type_id in {t["id"] for t in BUILTIN}:
            raise WorldError("Eingebaute Gebäude können nicht geändert werden")
        t = clean_type(raw, type_id)
        old = self.custom.get(type_id)
        if old and t["size"] != old["size"]:
            # A different size could overlap neighbours: placed buildings of this type keep the old size.
            for b in self.buildings:
                if b["type"] == type_id:
                    try:
                        self.check_free(b["x"], b["z"], self.footprint_size(t, b["rot"]), ignore=b["id"])
                    except WorldError:
                        t["size"] = old["size"]
                        break
        self.custom[type_id] = t
        self.save()
        return t

    def delete_type(self, type_id: str) -> None:
        if type_id not in self.custom:
            raise WorldError("Nur selbst erstellte Gebäude können gelöscht werden")
        if any(b["type"] == type_id for b in self.buildings):
            raise WorldError("Das Gebäude steht noch in der Welt – erst dort entfernen")
        del self.custom[type_id]
        self.save()

    # -- placing ------------------------------------------------------------------------------------------
    @staticmethod
    def footprint_size(t: dict, rot: int) -> tuple[int, int]:
        w, d = t["size"]
        return (d, w) if rot in (90, 270) else (w, d)

    def cells(self, b: dict) -> list[tuple[int, int]]:
        t = self.type_of(b)
        if not t:
            return []
        w, d = self.footprint_size(t, b["rot"])
        return [(b["x"] + i, b["z"] + j) for i in range(w) for j in range(d)]

    def door(self, b: dict) -> tuple[int, int] | None:
        """The cell in front of the door (outside the building), where Pino enters and leaves."""
        t = self.type_of(b)
        if not t or t.get("decor"):
            return None
        w, d = self.footprint_size(t, b["rot"])
        x, z = b["x"], b["z"]
        return {0: (x + w // 2, z + d), 180: (x + w // 2, z - 1), 90: (x + w, z + d // 2), 270: (x - 1, z + d // 2)}[b["rot"]]

    def blocked(self, ignore: str | None = None) -> set[tuple[int, int]]:
        return {c for b in self.buildings if b["id"] != ignore for c in self.cells(b)}

    def doors(self, ignore: str | None = None) -> set[tuple[int, int]]:
        return {d for b in self.buildings if b["id"] != ignore and (d := self.door(b))}

    def check_free(self, x: int, z: int, size: tuple[int, int], ignore: str | None = None, door=None) -> None:
        w, d = size
        if x < 0 or z < 0 or x + w > SIZE or z + d > SIZE:
            raise WorldError("Passt nicht in die Welt")
        cells = {(x + i, z + j) for i in range(w) for j in range(d)}
        if cells & self.blocked(ignore):
            raise WorldError("Dort steht schon etwas")
        if cells & self.doors(ignore):
            raise WorldError("Das versperrt die Tür eines anderen Gebäudes")
        if door is not None:
            if not (0 <= door[0] < SIZE and 0 <= door[1] < SIZE):
                raise WorldError("Die Tür zeigt aus der Welt hinaus – drehen")
            if door in self.blocked(ignore):
                raise WorldError("Vor der Tür steht etwas – drehen oder verschieben")

    def place(self, type_id: str, x: int, z: int, rot: int = 0, save: bool = True, ignore: str | None = None) -> dict:
        t = self.types().get(type_id)
        if not t:
            raise WorldError("Unbekannter Gebäudetyp")
        rot = int(rot) % 360
        if rot not in FRONT:
            raise WorldError("Drehung nur in 90°-Schritten")
        b = {"id": ignore or "g_" + secrets.token_hex(4), "type": type_id, "x": int(x), "z": int(z), "rot": rot}
        self.check_free(b["x"], b["z"], self.footprint_size(t, rot), ignore=ignore, door=self.door(b))
        if ignore:
            self.buildings = [o for o in self.buildings if o["id"] != ignore]
        self.buildings.append(b)
        if save:
            self.save()
        return b

    def move(self, building_id: str, x: int, z: int, rot: int) -> dict:
        b = self.get(building_id)
        return self.place(b["type"], x, z, rot, ignore=b["id"])

    def remove(self, building_id: str) -> None:
        self.get(building_id)
        self.buildings = [b for b in self.buildings if b["id"] != building_id]
        self.save()

    def get(self, building_id: str) -> dict:
        for b in self.buildings:
            if b["id"] == building_id:
                return b
        raise WorldError("Gebäude nicht gefunden")

    # -- walking -------------------------------------------------------------------------------------------
    def path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        """Shortest walk over free cells (8 directions, no corner cutting); [] if there is none."""
        blocked = self.blocked()
        if goal in blocked:
            return []
        start = start if start not in blocked else self.nearest_free(start)
        if start == goal:
            return [start]
        best = {start: 0.0}
        came: dict = {}
        heap = [(0.0, start)]
        while heap:
            _, cur = heapq.heappop(heap)
            if cur == goal:
                path = [cur]
                while cur in came:
                    cur = came[cur]
                    path.append(cur)
                return path[::-1]
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (cur[0] + dx, cur[1] + dz)
                if not (0 <= nxt[0] < SIZE and 0 <= nxt[1] < SIZE) or nxt in blocked:
                    continue
                if dx and dz and ((cur[0] + dx, cur[1]) in blocked or (cur[0], cur[1] + dz) in blocked):
                    continue
                cost = best[cur] + (1.414 if dx and dz else 1.0)
                if cost < best.get(nxt, 1e9):
                    best[nxt], came[nxt] = cost, cur
                    heapq.heappush(heap, (cost + abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1]), nxt))
        return []

    def nearest_free(self, cell: tuple[int, int]) -> tuple[int, int]:
        blocked = self.blocked()
        for r in range(SIZE):
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    c = (cell[0] + dx, cell[1] + dz)
                    if 0 <= c[0] < SIZE and 0 <= c[1] < SIZE and c not in blocked:
                        return c
        return cell

    def public(self) -> dict:
        return {"size": SIZE, "version": self.version, "types": list(self.types().values()),
                "buildings": [{**b, "door": self.door(b)} for b in self.buildings]}
