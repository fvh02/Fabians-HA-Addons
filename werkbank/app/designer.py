"""How Claude designs parts: the rules for Werkbank scripts (shared by the assistant and the dashboard
chat) and the dashboard chat itself (Claude through Fabians-HA-Master, without tools)."""

import json
import re

import fabians_master

GUIDE = """# Werkbank-Skripte (FreeCAD 1.1, Python)

Ein Skript beschreibt ein druckbares Teil für den Bambu Lab P1S (Bauraum 256 × 256 × 256 mm). Einheit: mm.

```python
# Kurzbeschreibung des Teils (deutsch)
PARAMS = {
    "breite": {"wert": 80, "min": 30, "max": 200, "einheit": "mm", "info": "Außenbreite"},
    "wand":   {"wert": 2.4, "min": 1.2, "max": 6, "einheit": "mm", "info": "Wandstärke"},
    "loecher": {"wert": True, "info": "Schraublöcher"},
}

def build(p):
    b, w = p["breite"], p["wand"]
    teil = box(b, 40, 20).cut(box(b - 2 * w, 40 - 2 * w, 20, w, w, w))   # oben offene Schale
    return teil                       # oder {"unterteil": a, "deckel": b} für mehrere Teile
```

Regeln:
- PARAMS: jedes wichtige Maß als Parameter (wert, min, max, einheit, info) – der Besitzer kann sie im Dashboard
  per Schieberegler ändern, ohne dass neu konstruiert werden muss. Auch true/false und Zahlen ohne Einheit gehen.
- build(p) bekommt die Werte und gibt eine Part.Shape zurück, oder ein dict Name → Shape (jedes Teil wird einzeln
  gedruckt; Namen kurz, deutsch, ohne Leerzeichen).
- Jedes Teil liegt in Druckausrichtung: flache, große Seite unten auf z = 0, möglichst ohne Stützen druckbar.
- Verfügbar ohne Import: Part, App/FreeCAD, Vector, Rotation, Placement, math und diese Helfer:
  box(l, b, h, x=0, y=0, z=0) · zylinder(r, h, x=0, y=0, z=0, richtung=(0, 0, 1)) · kegel(r1, r2, h, x, y, z)
  kugel(r, x, y, z) · verschoben(s, x, y, z) · gedreht(s, winkel, achse=(0, 0, 1), zentrum=(0, 0, 0))
  profil([(x, y), …], hoehe) (geschlossenes Polygon in xy, nach z extrudiert)
  gerundet(s, r, auswahl=None) · gefast(s, r, auswahl=None)   (auswahl: Funktion edge → bool; schlägt das
  Runden fehl, kommt die Form unverändert zurück)
  rohr(r_aussen, r_innen, h, x, y, z) · langloch(l, b, h, x, y, z) (Langloch in x-Richtung, Mitte bei x, y)
- Imports nur: FreeCAD, Part, Mesh, MeshPart, BOPTools, math, itertools, functools, collections, random.
  Keine Dateien, kein Netzwerk, kein open/eval/exec. Nach cut/fuse ist .removeSplitter() oft hilfreich.
- Part-API: Part.makeBox, makeCylinder(r, h, pos, dir), makeCone, makeSphere, makeTorus, Part.makePolygon(punkte,
  True) → Part.Face(wire) → .extrude(Vector(0, 0, h)), face.revolve(Vector(), Vector(0, 0, 1), 360),
  shape.fuse/cut/common, shape.makeFillet(r, kanten), shape.makeChamfer(r, kanten), shape.makeThickness(...),
  shape.mirror(Vector(), Vector(1, 0, 0)), Part.makeCompound([...]).

Gut druckbar konstruieren:
- Wände mindestens 1,6 mm, für Festigkeit 2–3 mm. Böden 1,2–2 mm.
- Passungen: 0,3 mm Spiel pro Seite für Teile, die ineinander sollen; 0,15 mm für Klemmsitz.
- Löcher: M3 3,4 mm (Durchgang), M4 4,5 mm, Gewindeeinsatz M3 4,0 mm; Senkkopf M3 6,5 mm × 90°.
  Senkrechte Löcher drucken etwas kleiner: bei engen Passungen +0,2 mm.
- Überhänge höchstens 45°, Brücken höchstens ~30 mm. Untere Außenkanten 0,4–0,6 mm anfasen (Elefantenfuß),
  sichtbare Außenkanten runden (1–2 mm).
- Größer als 256 mm: in Teile aufteilen, mit Verbindung (Schwalbenschwanz, Stifte 5 mm in 5,3-mm-Löchern,
  Schrauben). Klemm-/Schnapphaken mindestens 1,5 mm dick, mit Spiel.
- Maße aus Fotos sind auf etwa 1–3 % genau: bei passgenauen Teilen großzügig Spiel geben oder erst ein kleines
  Probestück vorschlagen (z. B. nur die Ecke mit dem Ausschnitt).
- Kein Text/Gravur möglich (keine Schriften); stattdessen einfache Symbole aus Formen.
"""

HELPERS = '''
def box(l, b, h, x=0, y=0, z=0):
    return Part.makeBox(l, b, h, Vector(x, y, z))

def zylinder(r, h, x=0, y=0, z=0, richtung=(0, 0, 1)):
    return Part.makeCylinder(r, h, Vector(x, y, z), Vector(*richtung))

def kegel(r1, r2, h, x=0, y=0, z=0, richtung=(0, 0, 1)):
    return Part.makeCone(r1, r2, h, Vector(x, y, z), Vector(*richtung))

def kugel(r, x=0, y=0, z=0):
    return Part.makeSphere(r, Vector(x, y, z))

def verschoben(s, x=0, y=0, z=0):
    c = s.copy()
    c.translate(Vector(x, y, z))
    return c

def gedreht(s, winkel, achse=(0, 0, 1), zentrum=(0, 0, 0)):
    c = s.copy()
    c.rotate(Vector(*zentrum), Vector(*achse), winkel)
    return c

def profil(punkte, hoehe):
    pts = [Vector(x, y, 0) for x, y in punkte]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(Vector(0, 0, hoehe))

def gerundet(s, r, auswahl=None):
    kanten = [e for e in s.Edges if auswahl is None or auswahl(e)]
    try:
        return s.makeFillet(r, kanten) if kanten else s
    except Exception:
        return s

def gefast(s, r, auswahl=None):
    kanten = [e for e in s.Edges if auswahl is None or auswahl(e)]
    try:
        return s.makeChamfer(r, kanten) if kanten else s
    except Exception:
        return s

def rohr(r_aussen, r_innen, h, x=0, y=0, z=0):
    return zylinder(r_aussen, h, x, y, z).cut(zylinder(r_innen, h + 2, x, y, z - 1))

def langloch(l, b, h, x=0, y=0, z=0):
    r = b / 2
    mitte = box(max(l - b, 0.01), b, h, x - (l - b) / 2, y - r, z)
    return mitte.fuse(zylinder(r, h, x - (l - b) / 2, y, z)).fuse(zylinder(r, h, x + (l - b) / 2, y, z)).removeSplitter()
'''

CHAT_SCHEMA = {"type": "object", "properties": {
    "antwort": {"type": "string", "description": "German answer to the owner: what you built or what you need to know"},
    "skript": {"type": "string", "description": "the complete Werkbank script, or empty if you only ask or answer"},
    "name": {"type": "string", "description": "short German name of the part (only when it should change)"}},
    "required": ["antwort", "skript"]}


class DesignError(Exception):
    pass


def ask(prompt: str) -> dict:
    try:
        envelope = fabians_master.ask_claude({"prompt": prompt, "schema": CHAT_SCHEMA, "max_turns": 6}, timeout=960)
    except fabians_master.MasterError as err:
        raise DesignError(f"Claude nicht erreichbar: {str(err)[:300]}") from err
    if envelope.get("is_error"):
        raise DesignError(f"Claude-Fehler: {str(envelope.get('result'))[:300]}")
    result = envelope.get("structured_output")
    if not isinstance(result, dict):
        match = re.search(r"\{.*\}", str(envelope.get("result") or ""), re.S)
        try:
            result = json.loads(match.group(0)) if match else None
        except ValueError:
            result = None
    if not isinstance(result, dict):
        raise DesignError("Claude hat nicht verständlich geantwortet")
    return result


def prompt_for(project: dict, message: str, script: str, version: dict | None, error: str = "") -> str:
    measures = "\n".join(f"- {m['name']}: {m['wert_mm']} mm ({m.get('quelle', '')})" for m in project.get("masse", [])) or "(keine)"
    chat = "\n".join(f"{'Besitzer' if c['rolle'] == 'du' else 'Du'}: {c['text'][:800]}" for c in project["chat"][-12:]) or "(neu)"
    current = ""
    if script:
        stats = json.dumps({k: version.get(k) for k in ("gesamt", "teile", "werte")}, ensure_ascii=False)[:2500] if version else ""
        current = f"\nCurrent script (version {version['n'] if version else '?'}):\n```python\n{script}\n```\nResult: {stats}\n"
    retry = f"\nYOUR LAST SCRIPT FAILED – fix it and answer again with the full script:\n{error}\n" if error else ""
    return f"""You are the design engineer of "Werkbank", a FreeCAD add-on in the owner's Home Assistant. The owner
describes a part; you write a parametric FreeCAD script that the add-on runs, checks, renders and can send to the
Bambu Lab P1S 3D printer (printing only ever starts after the owner confirms). Answer in German.

{GUIDE}

Project: {project['name']}
Description: {project.get('beschreibung') or '(none)'}
Measurements (from photos with a reference sheet, or typed in):
{measures}
{current}
Conversation so far:
{chat}

The owner now says: {message}
{retry}
If important dimensions are missing and cannot be reasonably assumed, ask (empty "skript") – but prefer
sensible defaults as parameters, so the owner can adjust them. Otherwise return the complete script (not a diff).
In "antwort" say briefly what you built, which assumptions you made and which parameters can be changed."""
