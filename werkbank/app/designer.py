"""How Claude designs parts: the rules for Werkbank scripts (build123d), shared by the assistant and the
dashboard chat, and the dashboard chat itself (Claude through Fabians-HA-Master, without tools)."""

import json
import re

import fabians_master

GUIDE = """# Werkbank-Skripte (Python mit build123d 0.13)

Ein Skript beschreibt ein druckbares Teil für den Bambu Lab P1S (Bauraum 256 × 256 × 256 mm). Einheit: mm.
Alle build123d-Namen (Box, Cylinder, Pos, Rot, fillet, …) sind schon da – kein Import nötig.

```python
# Kurzbeschreibung des Teils (deutsch)
PARAMS = {
    "laenge": {"wert": 80, "min": 30, "max": 200, "einheit": "mm", "info": "Außenlänge"},
    "breite": {"wert": 50, "min": 20, "max": 200, "einheit": "mm", "info": "Außenbreite"},
    "hoehe":  {"wert": 30, "min": 10, "max": 150, "einheit": "mm", "info": "Höhe"},
    "wand":   {"wert": 2.4, "min": 1.2, "max": 6, "einheit": "mm", "info": "Wandstärke"},
    "loecher": {"wert": True, "info": "Schraublöcher im Boden"},
}

def build(p):
    l, b, h, w = p["laenge"], p["breite"], p["hoehe"], p["wand"]
    schale = Box(l, b, h, align=(Align.CENTER, Align.CENTER, Align.MIN))            # steht auf z = 0
    schale = fillet(schale.edges().filter_by(Axis.Z), radius=4)                       # senkrechte Kanten runden
    schale = offset(schale, amount=-w, openings=schale.faces().sort_by(Axis.Z)[-1])   # aushöhlen, oben offen
    if p["loecher"]:
        for x in (-l / 2 + 10, l / 2 - 10):
            schale -= Pos(x, 0, 0) * Cylinder(1.7, 2 * w, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return schale              # oder {"unterteil": a, "deckel": d} für mehrere Teile
```

Regeln:
- PARAMS: jedes wichtige Maß als Parameter (wert, min, max, einheit, info). Der Besitzer kann sie im Dashboard per
  Schieberegler ändern, ohne neue Konstruktion. Auch true/false geht.
- build(p) bekommt die Werte und gibt ein Teil zurück – oder ein dict Name → Teil (jedes wird einzeln gedruckt;
  Namen kurz, deutsch, ohne Leerzeichen). BuildPart-Objekte gehen auch (es zählt .part).
- Jedes Teil liegt in Druckausrichtung: große flache Seite unten auf z = 0, möglichst ohne Stützen druckbar.
  Mehrere Teile nebeneinander platzieren (Pos), nicht übereinander.
- Erlaubte Imports: build123d, math, itertools, functools, collections, random, copy. Keine Dateien (import_*/export_*
  sind gesperrt), kein Netzwerk, kein open/eval/exec, keine __dunder__-Attribute.

build123d (Algebra-Stil, empfohlen):
- Körper: Box(l, b, h), Cylinder(r, h), Cone(r_unten, r_oben, h), Sphere(r), Torus(R, r).
  align=(Align.CENTER, Align.CENTER, Align.MIN) setzt den Körper auf z = 0 (Standard: um den Ursprung zentriert).
- Platzieren: Pos(x, y, z) * teil, Rot(0, 0, 45) * teil (Grad um x, y, z).
- Verknüpfen: a + b (vereinigen), a - b (abziehen), a & b (Schnitt). Mehrere Löcher:
  teil -= [Pos(x, y, 0) * Cylinder(1.7, 10) for x, y in punkte]
- Kanten: fillet(kanten, radius=…), chamfer(kanten, length=…). Auswahl: teil.edges().filter_by(Axis.Z) (senkrechte),
  teil.edges().group_by(Axis.Z)[-1] (oberste), teil.edges().group_by(Axis.Z)[0] (unterste),
  teil.faces().sort_by(Axis.Z)[-1] (Deckfläche). Runden scheitert bei zu großen Radien – dann kleiner wählen.
- Aushöhlen: offset(teil, amount=-wand, openings=fläche) – Schale mit offener Fläche.
- 2D → 3D: Rectangle(l, b), RectangleRounded(l, b, r), Circle(r), Ellipse(rx, ry), RegularPolygon(r, n),
  SlotCenterToCenter(abstand, breite), Polygon((x, y), …), Text("Fabian", font_size=8); dann extrude(skizze, amount=h).
  Auf anderer Ebene: Plane.XZ * Rectangle(…). Drehkörper: revolve(Plane.XZ * skizze, axis=Axis.Z).
- Schrift: Gravur = teil - Pos(x, y, h - 0.6) * extrude(Text("…", font_size=6), amount=1); erhabene Schrift
  mindestens 0,6 mm hoch, Buchstaben ≥ 5 mm.
- Spiegeln: mirror(teil, about=Plane.YZ). Builder-Stil (with BuildPart() as bp: …) geht auch; dann bp.part zurückgeben.

Gut druckbar konstruieren:
- Wände mindestens 1,6 mm, für Festigkeit 2–3 mm. Böden 1,2–2 mm.
- Passungen: 0,3 mm Spiel pro Seite für Teile, die ineinander sollen; 0,15 mm für Klemmsitz.
- Löcher: M3 3,4 mm (Durchgang), M4 4,5 mm, Gewindeeinsatz M3 4,0 mm; Senkkopf M3 6,5 mm × 90°.
  Senkrechte Löcher drucken etwas kleiner: bei engen Passungen +0,2 mm.
- Überhänge höchstens 45°, Brücken höchstens ~30 mm. Untere Außenkanten 0,4–0,6 mm anfasen (Elefantenfuß),
  sichtbare Außenkanten runden (1–2 mm).
- Größer als 256 mm: in Teile aufteilen, mit Verbindung (Schwalbenschwanz, Stifte 5 mm in 5,3-mm-Löchern,
  Schrauben). Schnapphaken mindestens 1,5 mm dick, mit Spiel.
- Maße aus Fotos sind auf etwa 1–3 % genau: bei passgenauen Teilen großzügig Spiel geben oder erst ein kleines
  Probestück vorschlagen (z. B. nur die Ecke mit dem Ausschnitt).
"""

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
    return f"""You are the design engineer of "Werkbank", a CAD add-on (Python, build123d) in the owner's Home Assistant.
The owner describes a part; you write a parametric build123d script that the add-on runs, checks, renders and can
send to the Bambu Lab P1S 3D printer (printing only ever starts after the owner confirms). Answer in German.

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
