"""Preview pictures of a model without a graphics card: the STL triangles are shaded and drawn back to
front (painter's algorithm) with Pillow. One picture with three views and the dimensions."""

import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

COLORS = [(46, 125, 79), (59, 130, 246), (234, 88, 12), (147, 51, 234), (202, 138, 4), (220, 38, 38), (13, 148, 136)]
BG = (244, 246, 243)
MAX_TRIANGLES = 120_000


def read_stl(path: Path) -> np.ndarray:
    """Triangles as array (n, 3, 3) in mm, from a binary or ASCII STL."""
    data = path.read_bytes()
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        if 84 + n * 50 == len(data):
            rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
            return rec["v"].astype(np.float64)
    verts = [list(map(float, line.split()[1:4])) for line in data.decode(errors="ignore").splitlines()
             if line.strip().startswith("vertex")]
    return np.array(verts, dtype=np.float64).reshape(-1, 3, 3)


FONT_DIRS = [Path(sys.prefix) / "fonts", Path("/opt/conda/fonts"), Path("/usr/share/fonts/truetype/dejavu")]


def font(size: int):
    """A font with umlauts and ×; the image brings DejaVu (fonts-dejavu-core)."""
    for folder in FONT_DIRS:
        for name in ("Ubuntu-R.ttf", "DejaVuSans.ttf"):
            if (folder / name).exists():
                return ImageFont.truetype(str(folder / name), size)
    return ImageFont.load_default(size=size)


def view_matrix(azimuth: float, elevation: float) -> np.ndarray:
    """Rotation that looks at the model from the given direction (z up)."""
    a, e = np.radians(azimuth), np.radians(elevation)
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    # camera looks along -y after rotation; screen x = world x', screen y = world z'
    return rx @ rz


def draw_view(parts: list[np.ndarray], azimuth: float, elevation: float, size: tuple[int, int], label: str) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, BG)
    d = ImageDraw.Draw(img)
    rot = view_matrix(azimuth, elevation)
    allv = np.concatenate([p.reshape(-1, 3) for p in parts])
    center = (allv.min(0) + allv.max(0)) / 2
    rotated = [((p.reshape(-1, 3) - center) @ rot.T).reshape(-1, 3, 3) for p in parts]
    pts = np.concatenate([r.reshape(-1, 3) for r in rotated])
    scale = min((w - 60) / max(np.ptp(pts[:, 0]), 1e-6), (h - 70) / max(np.ptp(pts[:, 2]), 1e-6))
    light = np.array([-0.45, -0.75, 0.5])      # from upper left, in front (the camera looks along +y)
    light /= np.linalg.norm(light)
    tris, shades, colors = [], [], []
    for i, r in enumerate(rotated):
        if len(r) > MAX_TRIANGLES:
            r = r[:: int(np.ceil(len(r) / MAX_TRIANGLES))]
        n = np.cross(r[:, 1] - r[:, 0], r[:, 2] - r[:, 0])
        length = np.linalg.norm(n, axis=1)
        ok = length > 1e-12
        r, n = r[ok], n[ok] / length[ok, None]
        facing = n[:, 1] < 0            # towards the camera (camera at -y)
        r, n = r[facing], n[facing]
        tris.append(r)
        shades.append(0.35 + 0.65 * np.clip(n @ light, 0, 1))
        colors.append(np.full(len(r), i % len(COLORS)))
    if tris:
        r, s, c = np.concatenate(tris), np.concatenate(shades), np.concatenate(colors)
        depth = r[:, :, 1].mean(1)
        order = np.argsort(-depth)            # far (large y) first
        sx = w / 2 + r[:, :, 0] * scale
        sy = h / 2 + 10 - r[:, :, 2] * scale
        for k in order:
            base = COLORS[c[k]]
            f = min(1.0, max(0.25, s[k]))
            col = tuple(int(v * f) for v in base)
            poly = [(sx[k, 0], sy[k, 0]), (sx[k, 1], sy[k, 1]), (sx[k, 2], sy[k, 2])]
            d.polygon(poly, fill=col, outline=col)
    d.text((12, 8), label, fill=(60, 66, 60), font=font(18))
    return img


def preview(stls: list[Path], title: str, info: dict, out: Path) -> Path:
    parts = [read_stl(p) for p in stls]
    parts = [p for p in parts if len(p)]
    canvas = Image.new("RGB", (1400, 1050), (255, 255, 255))
    if parts:
        canvas.paste(draw_view(parts, -35, 28, (900, 700), "Schräg"), (0, 0))
        canvas.paste(draw_view(parts, 0, 0, (500, 350), "Vorne"), (900, 0))
        canvas.paste(draw_view(parts, 0, 89.9, (500, 350), "Oben"), (900, 350))
        canvas.paste(draw_view(parts, 90, 0, (500, 350), "Seite"), (900, 700))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 700, 900, 1050), fill=(250, 251, 249))
    d.text((24, 716), title[:60], fill=(25, 35, 25), font=font(34))
    g = info.get("gesamt", {})
    size = g.get("groesse_mm") or [0, 0, 0]
    lines = [f"Größe: {size[0]:g} × {size[1]:g} × {size[2]:g} mm (B × T × H)",
             f"Material: ca. {g.get('gewicht_g', 0):g} g {info.get('material', 'PLA')} · {g.get('volumen_cm3', 0):g} cm³"]
    teile = info.get("teile", [])
    if len(teile) > 1:
        lines.append(f"{len(teile)} Teile: " + ", ".join(f"{t['name']} ({t['groesse_mm'][0]:g}×{t['groesse_mm'][1]:g}×{t['groesse_mm'][2]:g})" for t in teile)[:110])
    warnings = [w for t in teile for w in t.get("warnungen", [])]
    y = 770
    for line in lines:
        d.text((24, y), line, fill=(50, 60, 50), font=font(24))
        y += 36
    for wtext in warnings[:3]:
        d.text((24, y), "Achtung: " + wtext[:80], fill=(180, 83, 9), font=font(20))
        y += 30
    d.line((900, 0, 900, 1050), fill=(225, 229, 222), width=2)
    d.line((900, 350, 1400, 350), fill=(225, 229, 222), width=2)
    d.line((900, 700, 1400, 700), fill=(225, 229, 222), width=2)
    d.line((0, 700, 900, 700), fill=(225, 229, 222), width=2)
    canvas.save(out, "PNG", optimize=True)
    return out
