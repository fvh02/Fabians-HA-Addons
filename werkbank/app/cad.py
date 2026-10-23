"""Running Werkbank scripts in FreeCAD, safely: a quick check of the code, then freecadcmd in its own
process with a time and memory limit, as an unprivileged user, in a fresh folder."""

import ast
import json
import logging
import os
import pwd
import resource
import shutil
import subprocess
import tempfile
from pathlib import Path

from designer import HELPERS

log = logging.getLogger("cad")

FREECADCMD = os.environ.get("WERKBANK_FREECAD", "freecadcmd")
RUNNER = Path(__file__).parent / "runner.py"
TIMEOUT = int(os.environ.get("WERKBANK_TIMEOUT", "180"))
MEMORY = int(os.environ.get("WERKBANK_MEMORY_MB", "2500")) * 1024 * 1024
ALLOWED_IMPORTS = {"FreeCAD", "App", "Part", "Mesh", "MeshPart", "BOPTools", "math", "itertools", "functools",
                   "collections", "random", "Sketcher"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "input", "breakpoint",
                   "getattr", "setattr", "delattr", "memoryview", "help", "exit", "quit"}
MAX_SCRIPT = 60_000


class ScriptError(Exception):
    pass


def check_source(source: str) -> None:
    """Reject anything a CAD script never needs (files, processes, network, introspection tricks)."""
    if len(source) > MAX_SCRIPT:
        raise ScriptError("Das Skript ist zu lang")
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        raise ScriptError(f"Syntaxfehler in Zeile {err.lineno}: {err.msg}") from err
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                if n.split(".")[0] not in ALLOWED_IMPORTS:
                    raise ScriptError(f"Import von '{n}' ist nicht erlaubt (nur FreeCAD, Part, Mesh, math …)")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ScriptError(f"'{node.id}' ist in Werkbank-Skripten nicht erlaubt")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ScriptError(f"Zugriff auf '{node.attr}' ist nicht erlaubt")
    if not any(isinstance(n, ast.FunctionDef) and n.name == "build" for n in tree.body):
        raise ScriptError("Das Skript braucht eine Funktion build(p)")


def _limits(uid: int | None):
    def apply():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT + 30, TIMEOUT + 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (300 * 1024 * 1024, 300 * 1024 * 1024))
        if uid is not None:
            os.setgid(uid)
            os.setuid(uid)
    return apply


def _sandbox_user() -> int | None:
    if os.getuid() != 0:
        return None
    try:
        return pwd.getpwnam(os.environ.get("WERKBANK_USER", "nobody")).pw_uid
    except KeyError:
        return None


def run(source: str, values: dict, material: str, target: Path) -> dict:
    """Builds the model; on success the files end up in target (modell.step, teile/*.stl)."""
    check_source(source)
    work = Path(tempfile.mkdtemp(prefix="werkbank-"))
    try:
        (work / "skript.py").write_text(source, encoding="utf-8")
        (work / "helfer.py").write_text(HELPERS, encoding="utf-8")
        (work / "params.json").write_text(json.dumps({"werte": values or {}, "material": material}), encoding="utf-8")
        uid = _sandbox_user()
        if uid is not None:
            os.chown(work, uid, uid)
            os.chmod(work, 0o700)
            for f in work.iterdir():
                os.chown(f, uid, uid)
        env = {"PATH": os.environ.get("PATH", ""), "WERKBANK_JOB": str(work), "HOME": str(work), "LANG": "C.UTF-8",
               "QT_QPA_PLATFORM": "offscreen"}
        try:
            proc = subprocess.run([FREECADCMD, str(RUNNER)], cwd=work, env=env, capture_output=True, text=True,
                                  timeout=TIMEOUT, preexec_fn=_limits(uid), stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as err:
            raise ScriptError(f"FreeCAD hat länger als {TIMEOUT} Sekunden gerechnet – Modell vereinfachen") from err
        except FileNotFoundError as err:
            raise ScriptError("FreeCAD ist nicht installiert") from err
        try:
            result = json.loads((work / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            tail = (proc.stderr or proc.stdout or "").strip()[-600:]
            raise ScriptError(f"FreeCAD ist abgestürzt (zu wenig Speicher oder fehlerhafte Geometrie). {tail}")
        if not result.get("ok"):
            line = f" (Zeile {result['zeile']})" if result.get("zeile") else ""
            raise ScriptError(f"{result.get('fehler')}{line}")
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy(work / "modell.step", target / "modell.step")
        if (target / "teile").exists():
            shutil.rmtree(target / "teile")
        shutil.copytree(work / "teile", target / "teile")
        (target / "skript.py").write_text(source, encoding="utf-8")
        return result
    finally:
        shutil.rmtree(work, ignore_errors=True)
