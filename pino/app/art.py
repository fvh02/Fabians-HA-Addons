"""Pino's paintings: the brain picks title, colours and style, the add-on paints it as SVG."""

import hashlib
import math
import random

STYLES = ["wellen", "kreise", "streifen", "punkte", "berge", "sterne", "spirale"]


def paint(title: str, colors: list[str], style: str, mood: str = "") -> str:
    rnd = random.Random(hashlib.sha1(f"{title}{style}{colors}".encode()).hexdigest())
    colors = [c for c in colors if isinstance(c, str) and len(c) == 7 and c.startswith("#")] or ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"]
    bg = colors[0]
    pick = lambda: rnd.choice(colors[1:] or colors)  # noqa: E731
    w, h = 400, 300
    shapes = []
    style = style if style in STYLES else rnd.choice(STYLES)
    if style == "wellen":
        for i in range(9):
            y = 40 + i * 30
            pts = " ".join(f"{x},{y + rnd.uniform(-18, 18):.0f}" for x in range(0, w + 50, 50))
            shapes.append(f'<polyline points="{pts}" fill="none" stroke="{pick()}" stroke-width="{rnd.randint(4, 14)}" stroke-linecap="round" opacity=".85"/>')
    elif style == "kreise":
        for _ in range(26):
            shapes.append(f'<circle cx="{rnd.randint(0, w)}" cy="{rnd.randint(0, h)}" r="{rnd.randint(8, 70)}" fill="{pick()}" opacity="{rnd.uniform(.35, .85):.2f}"/>')
    elif style == "streifen":
        x = 0
        while x < w:
            sw = rnd.randint(10, 50)
            shapes.append(f'<rect x="{x}" y="0" width="{sw}" height="{h}" fill="{pick()}" opacity="{rnd.uniform(.5, 1):.2f}" transform="rotate({rnd.uniform(-6, 6):.1f} {x} {h / 2})"/>')
            x += sw
    elif style == "punkte":
        for _ in range(240):
            shapes.append(f'<circle cx="{rnd.randint(0, w)}" cy="{rnd.randint(0, h)}" r="{rnd.randint(2, 7)}" fill="{pick()}"/>')
    elif style == "berge":
        for layer in range(4):
            base = 120 + layer * 45
            pts = [f"0,{h}"] + [f"{x},{base - rnd.randint(0, 90 - layer * 15)}" for x in range(0, w + 60, 60)] + [f"{w},{h}"]
            shapes.append(f'<polygon points="{" ".join(pts)}" fill="{pick()}" opacity="{.6 + layer * .1:.1f}"/>')
        shapes.insert(0, f'<circle cx="{rnd.randint(60, 340)}" cy="{rnd.randint(40, 90)}" r="28" fill="{pick()}"/>')
    elif style == "sterne":
        for _ in range(60):
            x, y, r = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(2, 9)
            shapes.append(f'<path d="M{x},{y - r} L{x + r / 3:.1f},{y - r / 3:.1f} L{x + r},{y} L{x + r / 3:.1f},{y + r / 3:.1f} L{x},{y + r} '
                          f'L{x - r / 3:.1f},{y + r / 3:.1f} L{x - r},{y} L{x - r / 3:.1f},{y - r / 3:.1f} Z" fill="{pick()}"/>')
    else:  # spirale
        cx, cy = w / 2, h / 2
        for i in range(120):
            a, r = i * 0.35, 2 + i * 1.3
            shapes.append(f'<circle cx="{cx + math.cos(a) * r:.0f}" cy="{cy + math.sin(a) * r * .75:.0f}" r="{3 + i / 18:.1f}" fill="{pick()}" opacity=".8"/>')
    safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:60]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<title>{safe}</title><rect width="{w}" height="{h}" fill="{bg}"/>{"".join(shapes)}'
            f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" fill="none" stroke="#3b2a18" stroke-width="8"/></svg>')
