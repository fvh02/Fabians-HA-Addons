"""Runs one Werkbank script inside FreeCAD (freecadcmd) and exports the result.

Called as: freecadcmd runner.py  with WERKBANK_JOB=<folder>. The folder contains skript.py and
params.json (values that override the script's PARAMS). Writes result.json, modell.step and
teile/<name>.stl. Everything the script may use is passed in; imports are limited to an allow-list.
"""

import builtins
import json
import math
import os
import re
import sys
import traceback

import FreeCAD
import MeshPart
import Part

JOB = os.environ["WERKBANK_JOB"]
BED = (256.0, 256.0, 256.0)          # Bambu Lab P1S build volume in mm
DENSITY = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21}
ALLOWED = {"FreeCAD", "App", "Part", "Mesh", "MeshPart", "BOPTools", "BOPTools.SplitFeatures", "math", "itertools",
           "functools", "collections", "random", "Sketcher"}
_real_import = builtins.__import__


def _import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in {a.split(".")[0] for a in ALLOWED} and not name.startswith("_"):
        raise ImportError(f"Import von '{name}' ist in Werkbank-Skripten nicht erlaubt")
    return _real_import(name, globals, locals, fromlist, level)


SAFE_BUILTINS = {k: getattr(builtins, k) for k in (
    "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float", "int", "isinstance", "len", "list",
    "map", "max", "min", "pow", "print", "range", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
    "ValueError", "Exception", "RuntimeError", "ZeroDivisionError", "True", "False", "None", "hasattr", "getattr",
    "iter", "next", "slice", "frozenset", "type", "__build_class__", "object", "super", "KeyError", "IndexError",
    "TypeError", "NotImplementedError", "AssertionError")}
SAFE_BUILTINS["__import__"] = _import


def write(result: dict) -> None:
    with open(os.path.join(JOB, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)


def safe_name(name: str, i: int) -> str:
    name = re.sub(r"[^A-Za-z0-9äöüÄÖÜß_-]+", "-", str(name)).strip("-")[:40]
    return name or f"teil-{i + 1}"


def as_parts(result) -> list[tuple[str, "Part.Shape"]]:
    if isinstance(result, dict):
        items = list(result.items())
    elif isinstance(result, (list, tuple)):
        items = [(f"teil-{i + 1}", s) for i, s in enumerate(result)]
    else:
        items = [("modell", result)]
    parts = []
    for i, (name, shape) in enumerate(items):
        if not isinstance(shape, Part.Shape):
            raise TypeError(f"build() muss Part.Shape liefern, '{name}' ist {type(shape).__name__}")
        parts.append((safe_name(name, i), shape))
    if not parts:
        raise ValueError("build() hat keine Teile geliefert")
    return parts


def check(name: str, shape, material: str) -> dict:
    bb = shape.BoundBox
    solids = shape.Solids
    size = [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)]
    volume = sum(s.Volume for s in solids) if solids else 0.0
    info = {"name": name, "groesse_mm": size, "volumen_cm3": round(volume / 1000, 2),
            "gewicht_g": round(volume / 1000 * DENSITY.get(material, 1.24), 1), "koerper": len(solids),
            "gueltig": bool(shape.isValid()), "warnungen": []}
    w = info["warnungen"]
    if not solids:
        w.append("Kein geschlossener Körper (nur Flächen oder Kanten) – so nicht druckbar")
    if not info["gueltig"]:
        w.append("Die Geometrie ist fehlerhaft (isValid = False)")
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
    return info


def main() -> None:
    material = "PLA"
    try:
        with open(os.path.join(JOB, "params.json"), encoding="utf-8") as fh:
            settings = json.load(fh)
        material = str(settings.get("material") or "PLA").upper()
        source = open(os.path.join(JOB, "skript.py"), encoding="utf-8").read()
        env = {"__builtins__": SAFE_BUILTINS, "__name__": "werkbank", "FreeCAD": FreeCAD, "App": FreeCAD, "Part": Part,
               "Vector": FreeCAD.Vector, "Rotation": FreeCAD.Rotation, "Placement": FreeCAD.Placement, "math": math}
        helpers = os.path.join(JOB, "helfer.py")
        if os.path.exists(helpers):
            exec(compile(open(helpers, encoding="utf-8").read(), "helfer.py", "exec"), env)
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
        infos, shapes = [], []
        names = set()
        for name, shape in parts:
            while name in names:
                name += "-2"
            names.add(name)
            infos.append(check(name, shape, material))
            shapes.append(shape)
            bb = shape.BoundBox
            deflection = max(0.02, min(0.2, bb.DiagonalLength / 1500))
            mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=deflection, AngularDeflection=0.35, Relative=False)
            mesh.write(os.path.join(JOB, "teile", f"{name}.stl"))
            infos[-1]["dreiecke"] = mesh.CountFacets
        Part.makeCompound(shapes).exportStep(os.path.join(JOB, "modell.step"))
        bb = Part.makeCompound(shapes).BoundBox
        total = {"groesse_mm": [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)],
                 "volumen_cm3": round(sum(i["volumen_cm3"] for i in infos), 2),
                 "gewicht_g": round(sum(i["gewicht_g"] for i in infos), 1)}
        spec = {k: (v if isinstance(v, dict) else {"wert": v}) for k, v in params.items()}
        write({"ok": True, "teile": infos, "gesamt": total, "params": spec, "werte": values, "material": material})
    except BaseException as err:  # noqa: BLE001 – every error goes back to Claude
        tb = traceback.extract_tb(err.__traceback__)
        line = next((f.lineno for f in reversed(tb) if f.filename == "skript.py"), None)
        write({"ok": False, "fehler": f"{err.__class__.__name__}: {err}"[:1500], "zeile": line,
               "trace": "".join(traceback.format_exception_only(type(err), err))[-1500:]})


main()
sys.exit(0)
