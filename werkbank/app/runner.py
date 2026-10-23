"""Runs one Werkbank script with build123d and exports the result.

Called as: python runner.py  with WERKBANK_JOB=<folder>. The folder contains skript.py and params.json
(values that override the script's PARAMS). Writes result.json, modell.step and teile/<name>.stl.
The script gets the build123d names (without the ones that read or write files) and may only import a few
harmless modules.
"""

import builtins
import json
import math
import os
import re
import sys
import traceback
import types

import build123d as bd

JOB = os.environ["WERKBANK_JOB"]
BED = (256.0, 256.0, 256.0)          # Bambu Lab P1S build volume in mm
DENSITY = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21}
SAFE_MODULES = {"math", "itertools", "functools", "collections", "random", "copy", "dataclasses", "enum", "typing"}
BLOCKED = re.compile(r"^(import_|export_|Import|Export|Mesher|show|set_port|set_defaults)")

NAMES = {n: getattr(bd, n) for n in getattr(bd, "__all__", dir(bd)) if not n.startswith("_") and not BLOCKED.match(n)}
NAMES = {n: v for n, v in NAMES.items() if not isinstance(v, types.ModuleType)}
FACADE = types.ModuleType("build123d")       # what "import build123d" / "from build123d import *" gives a script
FACADE.__dict__.update(NAMES)
FACADE.__all__ = sorted(NAMES)
_real_import = builtins.__import__


def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "build123d":
        for n in fromlist or ():
            if n != "*" and n not in NAMES:
                raise ImportError(f"'{n}' aus build123d ist in Werkbank-Skripten nicht erlaubt")
        return FACADE
    if name.split(".")[0] not in SAFE_MODULES:
        raise ImportError(f"Import von '{name}' ist in Werkbank-Skripten nicht erlaubt")
    return _real_import(name, globals, locals, fromlist, level)


SAFE_BUILTINS = {k: getattr(builtins, k) for k in (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int", "isinstance", "len", "list",
    "map", "max", "min", "pow", "print", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    "ValueError", "Exception", "RuntimeError", "ZeroDivisionError", "True", "False", "None", "hasattr",
    "iter", "next", "slice", "frozenset", "type", "__build_class__", "object", "super", "KeyError", "IndexError",
    "TypeError", "NotImplementedError", "AssertionError", "staticmethod", "classmethod", "property", "issubclass")}
SAFE_BUILTINS["__import__"] = _import


def write(result: dict) -> None:
    with open(os.path.join(JOB, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)


def safe_name(name: str, i: int) -> str:
    name = re.sub(r"[^A-Za-z0-9äöüÄÖÜß_-]+", "-", str(name)).strip("-")[:40]
    return name or f"teil-{i + 1}"


def as_shape(value, name: str):
    if isinstance(value, bd.BuildPart):
        value = value.part
    if isinstance(value, (list, tuple)) and value and all(isinstance(v, bd.Shape) for v in value):
        value = bd.Compound(list(value))
    if not isinstance(value, bd.Shape):
        raise TypeError(f"build() muss ein build123d-Teil liefern, '{name}' ist {type(value).__name__}")
    return value


def as_parts(result) -> list[tuple[str, object]]:
    if isinstance(result, dict):
        items = list(result.items())
    elif isinstance(result, (list, tuple)):
        items = [(f"teil-{i + 1}", s) for i, s in enumerate(result)]
    else:
        items = [("modell", result)]
    parts = [(safe_name(name, i), as_shape(shape, name)) for i, (name, shape) in enumerate(items)]
    if not parts:
        raise ValueError("build() hat keine Teile geliefert")
    return parts


def valid(shape) -> bool:
    v = getattr(shape, "is_valid", True)
    return bool(v() if callable(v) else v)


def check(name: str, shape, material: str) -> dict:
    bb = shape.bounding_box()
    size = [round(bb.size.X, 2), round(bb.size.Y, 2), round(bb.size.Z, 2)]
    solids = shape.solids()
    volume = sum(s.volume for s in solids) if solids else 0.0
    info = {"name": name, "groesse_mm": size, "volumen_cm3": round(volume / 1000, 2),
            "gewicht_g": round(volume / 1000 * DENSITY.get(material, 1.24), 1), "koerper": len(solids),
            "gueltig": valid(shape), "warnungen": []}
    w = info["warnungen"]
    if not solids:
        w.append("Kein geschlossener Körper (nur Flächen oder Linien) – so nicht druckbar")
    if not info["gueltig"]:
        w.append("Die Geometrie ist fehlerhaft (nicht gültig)")
    if len(solids) > 1:
        w.append(f"Besteht aus {len(solids)} getrennten Körpern – gewollt?")
    dims = sorted(size)
    if dims[0] > BED[0] or dims[1] > BED[1] or dims[2] > BED[2]:
        w.append(f"Zu groß für die Druckplatte ({size[0]:.0f} × {size[1]:.0f} × {size[2]:.0f} mm, maximal 256 mm) – in Teile aufteilen")
    elif size[0] > BED[0] or size[1] > BED[1] or size[2] > BED[2]:
        w.append("Passt nur gedreht auf die Druckplatte")
    if 0 < dims[0] < 0.8:
        w.append(f"Sehr dünn ({dims[0]:.2f} mm) – unter 0,8 mm druckt nicht sauber")
    if volume and volume < 20:
        w.append("Sehr kleines Teil – prüfen, ob die Maße in mm sind")
    if solids and bb.min.Z < -0.05:
        w.append("Liegt nicht auf z = 0 – der Slicer legt es auf die Platte, Ausrichtung prüfen")
    return info


def main() -> None:
    try:
        with open(os.path.join(JOB, "params.json"), encoding="utf-8") as fh:
            settings = json.load(fh)
        material = str(settings.get("material") or "PLA").upper()
        source = open(os.path.join(JOB, "skript.py"), encoding="utf-8").read()
        env = {"__builtins__": SAFE_BUILTINS, "__name__": "werkbank", "math": math, **NAMES}
        exec(compile(source, "skript.py", "exec"), env)
        params = env.get("PARAMS") or {}
        if not isinstance(params, dict):
            raise TypeError("PARAMS muss ein dict sein")
        values = {}
        for key, spec in params.items():
            default = spec.get("wert") if isinstance(spec, dict) else spec
            value = settings.get("werte", {}).get(key, default)
            if isinstance(spec, dict) and isinstance(value, (int, float)) and not isinstance(value, bool):
                if spec.get("min") is not None:
                    value = max(spec["min"], value)
                if spec.get("max") is not None:
                    value = min(spec["max"], value)
            values[key] = value
        build = env.get("build")
        if not callable(build):
            raise NameError("Das Skript braucht eine Funktion build(p)")
        parts = as_parts(build(values))
        os.makedirs(os.path.join(JOB, "teile"), exist_ok=True)
        infos, shapes, names = [], [], set()
        for name, shape in parts:
            while name in names:
                name += "-2"
            names.add(name)
            infos.append(check(name, shape, material))
            shapes.append(shape)
            diag = shape.bounding_box().diagonal
            bd.export_stl(shape, os.path.join(JOB, "teile", f"{name}.stl"),
                          tolerance=max(0.01, min(0.1, diag / 3000)), angular_tolerance=0.2)
        compound = bd.Compound(shapes) if len(shapes) > 1 else shapes[0]
        bd.export_step(compound, os.path.join(JOB, "modell.step"))
        bb = compound.bounding_box()
        total = {"groesse_mm": [round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)],
                 "volumen_cm3": round(sum(i["volumen_cm3"] for i in infos), 2),
                 "gewicht_g": round(sum(i["gewicht_g"] for i in infos), 1)}
        spec = {k: (v if isinstance(v, dict) else {"wert": v}) for k, v in params.items()}
        write({"ok": True, "teile": infos, "gesamt": total, "params": spec, "werte": values, "material": material})
    except BaseException as err:  # noqa: BLE001 – every error goes back to Claude
        tb = traceback.extract_tb(err.__traceback__)
        line = next((f.lineno for f in reversed(tb) if f.filename == "skript.py"), None)
        write({"ok": False, "fehler": f"{err.__class__.__name__}: {err}"[:1500], "zeile": line})


main()
sys.exit(0)
