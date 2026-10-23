"""Projects, versions, photos and measurements – everything as files in /data.

/data/projekte/<id>/projekt.json   name, description, chat, measurements, versions
/data/projekte/<id>/v<n>/          skript.py, modell.step, teile/*.stl, vorschau.png, druck.(stl|zip)
/data/fotos/<id>/                  original.jpg, entzerrt.jpg, entzerrt-roh.jpg, info.json
"""

import json
import re
import secrets
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

ID = re.compile(r"^[a-z0-9]{6,16}$")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class NotFound(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.projects = root / "projekte"
        self.photos = root / "fotos"
        self.projects.mkdir(parents=True, exist_ok=True)
        self.photos.mkdir(parents=True, exist_ok=True)

    # -- projects -------------------------------------------------------------------------------------------
    def path(self, pid: str) -> Path:
        if not ID.match(str(pid)):
            raise NotFound("Unbekanntes Projekt")
        return self.projects / pid

    def get(self, pid: str) -> dict:
        try:
            return json.loads((self.path(pid) / "projekt.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            raise NotFound("Projekt nicht gefunden") from err

    def save(self, p: dict) -> None:
        p["geaendert"] = now_iso()
        folder = self.path(p["id"])
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / "projekt.tmp"
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(folder / "projekt.json")

    def create(self, name: str, description: str = "", by: str = "dashboard") -> dict:
        pid = secrets.token_hex(4)
        p = {"id": pid, "name": (name or "Neues Teil").strip()[:80], "beschreibung": description.strip()[:3000],
             "erstellt": now_iso(), "von": by, "versionen": [], "chat": [], "masse": [], "fotos": [], "material": "PLA"}
        self.save(p)
        return p

    def list(self) -> list[dict]:
        out = []
        for f in self.projects.glob("*/projekt.json"):
            try:
                p = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            last = p["versionen"][-1] if p["versionen"] else None
            out.append({"id": p["id"], "name": p["name"], "geaendert": p.get("geaendert"), "versionen": len(p["versionen"]),
                        "groesse_mm": (last or {}).get("gesamt", {}).get("groesse_mm"), "letzte": last and last["n"]})
        return sorted(out, key=lambda p: p.get("geaendert") or "", reverse=True)

    def delete(self, pid: str) -> None:
        folder = self.path(pid)
        if folder.exists():
            shutil.rmtree(folder)

    def version(self, p: dict, n: int | None = None) -> dict:
        if not p["versionen"]:
            raise NotFound("Noch keine Version – erst konstruieren")
        if n is None:
            ok = [v for v in p["versionen"] if v.get("ok")]
            return ok[-1] if ok else p["versionen"][-1]
        for v in p["versionen"]:
            if v["n"] == int(n):
                return v
        raise NotFound(f"Version {n} gibt es nicht")

    def vdir(self, pid: str, n: int) -> Path:
        return self.path(pid) / f"v{int(n)}"

    def next_version(self, p: dict) -> int:
        return max([v["n"] for v in p["versionen"]] + [0]) + 1

    def add_version(self, p: dict, n: int, result: dict, by: str, note: str) -> dict:
        folder = self.vdir(p["id"], n)
        stls = sorted((folder / "teile").glob("*.stl"))
        if len(stls) == 1:
            shutil.copy(stls[0], folder / "druck.stl")
            print_file = "druck.stl"
        else:
            with zipfile.ZipFile(folder / "druck.zip", "w", zipfile.ZIP_DEFLATED) as z:
                for f in stls:
                    z.write(f, f.name)
            print_file = "druck.zip"
        v = {"n": n, "erstellt": now_iso(), "von": by, "notiz": note[:500], "ok": True, "token": secrets.token_hex(16),
             "teile": result["teile"], "gesamt": result["gesamt"], "params": result.get("params", {}),
             "werte": result.get("werte", {}), "material": result.get("material", "PLA"), "druckdatei": print_file,
             "warnungen": [w for t in result["teile"] for w in t.get("warnungen", [])]}
        p["versionen"].append(v)
        self.save(p)
        return v

    def by_token(self, token: str) -> tuple[dict, dict] | None:
        if not re.match(r"^[0-9a-f]{32}$", token):
            return None
        for f in self.projects.glob("*/projekt.json"):
            p = json.loads(f.read_text(encoding="utf-8"))
            for v in p["versionen"]:
                if v.get("token") == token:
                    return p, v
        return None

    def chat(self, p: dict, role: str, text: str, **extra) -> None:
        p["chat"].append({"rolle": role, "text": text[:6000], "zeit": now_iso(), **extra})
        del p["chat"][:-200]

    # -- photos -------------------------------------------------------------------------------------------------
    def photo_dir(self, fid: str) -> Path:
        if not ID.match(str(fid)):
            raise NotFound("Unbekanntes Foto")
        return self.photos / fid

    def new_photo(self) -> tuple[str, Path]:
        fid = secrets.token_hex(5)
        folder = self.photos / fid
        folder.mkdir(parents=True)
        return fid, folder

    def photo(self, fid: str) -> dict:
        folder = self.photo_dir(fid)
        try:
            info = json.loads((folder / "info.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            info = {}
        meta = {}
        if (folder / "meta.json").exists():
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        return {"id": fid, **meta, **info, "entzerrt": (folder / "entzerrt.jpg").exists()}

    def photo_meta(self, fid: str, **values) -> dict:
        folder = self.photo_dir(fid)
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8")) if (folder / "meta.json").exists() else {}
        meta.update(values)
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return meta

    def clean_photos(self, days: int = 60) -> None:
        cutoff = time.time() - days * 86400
        used = {f for p in self.list() for f in self.get(p["id"]).get("fotos", [])}
        for folder in self.photos.iterdir():
            if folder.is_dir() and folder.name not in used and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
