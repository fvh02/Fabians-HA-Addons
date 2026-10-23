"""Measuring from a photo: a sheet of paper (or a card) of known size lies in the picture.

1. The reference is found (the brightest large quadrilateral with the right proportions) – or its four
   corners are given by hand.
2. The photo is straightened onto the plane of the reference (homography), at a known scale (px per mm),
   with a millimetre grid. Distances in that picture are real distances – on that plane.
3. The object is looked for on or next to the reference; its outline gives length and width.
Objects that are tall (not flat) look a bit larger than they are, because their top is closer to the camera.
"""

import json
from pathlib import Path

import cv2
import numpy as np

REFERENCES = {
    "a4": ("DIN A4", 210.0, 297.0), "a5": ("DIN A5", 148.0, 210.0), "a3": ("DIN A3", 297.0, 420.0),
    "a6": ("DIN A6", 105.0, 148.0), "letter": ("US Letter", 215.9, 279.4),
    "karte": ("Scheckkarte", 53.98, 85.6),
}
MAX_SIDE = 2200          # px of the straightened picture
MARGIN_MM = 3.0


class MeasureError(Exception):
    pass


def reference_size(kind: str, custom: tuple[float, float] | None = None) -> tuple[str, float, float]:
    if custom:
        w, h = sorted(custom)
        return ("eigene Referenz", w, h)
    if kind not in REFERENCES:
        raise MeasureError("Unbekannte Referenz – a4, a5, a3, a6, letter, karte oder eigene Maße")
    return REFERENCES[kind]


def order_corners(pts: np.ndarray) -> np.ndarray:
    """Top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    c = pts.mean(0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    pts = pts[np.argsort(ang)]                        # clockwise from the left (image y points down)
    start = np.argmin(pts.sum(1))                     # smallest x+y = top left
    return np.roll(pts, -start, axis=0)


def find_reference(img: np.ndarray, ratio: float) -> np.ndarray | None:
    """The four corners of the reference (paper is usually the brightest big quadrilateral)."""
    h, w = img.shape[:2]
    small = 1000 / max(h, w)
    im = cv2.resize(img, None, fx=small, fy=small, interpolation=cv2.INTER_AREA) if small < 1 else img.copy()
    small = min(small, 1.0)
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    masks = []
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    masks.append(otsu)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    masks.append(((hsv[:, :, 1] < 60) & (hsv[:, :, 2] > np.percentile(hsv[:, :, 2], 60))).astype(np.uint8) * 255)
    edges = cv2.dilate(cv2.Canny(gray, 40, 120), np.ones((3, 3), np.uint8), iterations=2)
    masks.append(edges)
    best, best_score = None, 0.0
    area_img = im.shape[0] * im.shape[1]
    for mask in masks:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < area_img * 0.004:
                continue
            hull = cv2.convexHull(cnt)
            approx = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True)
            if len(approx) != 4:
                continue
            q = order_corners(approx.reshape(4, 2))
            sides = [np.linalg.norm(q[i] - q[(i + 1) % 4]) for i in range(4)]
            a, b = (sides[0] + sides[2]) / 2, (sides[1] + sides[3]) / 2
            r = min(a, b) / max(a, b)
            fit = 1 - min(1, abs(r - ratio) / ratio * 2.5)     # perspective changes the proportions a little
            score = area / area_img * (0.3 + fit) * (cv2.contourArea(q) / max(cv2.contourArea(hull), 1))
            if fit > 0.2 and score > best_score:
                best, best_score = q, score
    return None if best is None else best / small


def _pick(mask: np.ndarray, px_mm: float, max_area: float, edge: np.ndarray | None = None) -> tuple | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for cnt in contours:
        area = cv2.contourArea(cv2.convexHull(cnt))
        if area < (10 * px_mm) ** 2 or area > max_area:
            continue
        if edge is not None:     # reaches the edge of the photo: background or cut off, not the object
            one = np.zeros(mask.shape, np.uint8)
            cv2.drawContours(one, [cnt], -1, 255, -1)
            if np.any(one & edge):
                continue
        if best is None or area > best[0]:
            best = (area, cnt)
    return best


def _object_on(rect: np.ndarray, sheet_mask: np.ndarray, valid: np.ndarray, px_mm: float, inside: bool) -> dict | None:
    """The biggest thing that is not the reference: on it (darker or more colourful than the paper) or next
    to it (clearly different from the surface the paper lies on)."""
    gray = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY)
    k = int(MARGIN_MM * px_mm) * 2 + 1
    if inside:
        region = cv2.erode(sheet_mask, np.ones((k, k), np.uint8))
        paper = np.median(gray[region > 0]) if np.any(region) else 255
        hsv = cv2.cvtColor(rect, cv2.COLOR_BGR2HSV)
        mask = (((gray < paper - 35) | (hsv[:, :, 1] > 70)) & (region > 0)).astype(np.uint8) * 255
    else:
        region = cv2.erode(valid, np.ones((k * 3, k * 3), np.uint8))
        region[cv2.dilate(sheet_mask, np.ones((k, k), np.uint8)) > 0] = 0
        if not np.any(region):
            return None
        lab = cv2.cvtColor(cv2.GaussianBlur(rect, (7, 7), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
        surface = np.median(lab[region > 0], axis=0)
        dist = np.linalg.norm(lab - surface, axis=2)
        dist[region == 0] = 0
        level = max(25.0, float(np.percentile(dist[region > 0], 70)) * 1.5)
        mask = ((dist > level) & (region > 0)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    edge = None
    if not inside:
        edge = cv2.subtract(cv2.erode(valid, np.ones((k * 3, k * 3), np.uint8)),
                            cv2.erode(valid, np.ones((k * 3 + 6, k * 3 + 6), np.uint8)))
    best = _pick(mask, px_mm, float(np.count_nonzero(region)) * 0.6, edge)
    if best is None:
        return None
    cnt = best[1]
    (cx, cy), (rw, rh), angle = cv2.minAreaRect(cnt)
    x, y, bw, bh = cv2.boundingRect(cnt)
    return {"laenge_mm": round(float(max(rw, rh)) / px_mm, 1), "breite_mm": round(float(min(rw, rh)) / px_mm, 1),
            "achsen_mm": [round(bw / px_mm, 1), round(bh / px_mm, 1)], "winkel": round(float(angle), 1),
            "box": cv2.boxPoints(((cx, cy), (rw, rh), angle)).tolist(),
            "lage": "auf der Referenz" if inside else "neben der Referenz"}


def measure(image_bytes: bytes, kind: str, out: Path, corners: list | None = None,
            custom: tuple[float, float] | None = None) -> dict:
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise MeasureError("Das Bild lässt sich nicht lesen (JPEG oder PNG schicken)")
    h0, w0 = img.shape[:2]
    if max(h0, w0) > 4000:
        f = 4000 / max(h0, w0)
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        corners = [[x * f, y * f] for x, y in corners] if corners else None
    name, ref_w, ref_h = reference_size(kind, custom)
    found = np.array(corners, dtype=np.float32) if corners else find_reference(img, ref_w / ref_h)
    if found is None:
        cv2.imwrite(str(out / "original.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        raise MeasureError(f"{name} nicht gefunden – das Blatt ganz aufs Bild, mit Kontrast zum Untergrund "
                           "(z. B. auf einem dunklen Tisch), oder die vier Ecken im Dashboard antippen")
    q = order_corners(found)
    # long side of the reference along the longer side of the found quadrilateral
    s01, s12 = np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[1])
    rw, rh = (ref_h, ref_w) if s01 > s12 else (ref_w, ref_h)
    # first in mm, centred; then scaled to fit the whole photo into MAX_SIDE px
    dst_mm = np.array([[0, 0], [rw, 0], [rw, rh], [0, rh]], dtype=np.float32)
    H = cv2.getPerspectiveTransform(q.astype(np.float32), dst_mm)
    img_corners = np.array([[[0, 0]], [[img.shape[1], 0]], [[img.shape[1], img.shape[0]]], [[0, img.shape[0]]]], dtype=np.float32)
    projected = cv2.perspectiveTransform(img_corners, H).reshape(-1, 2)
    reach = max(2.5 * max(rw, rh), 400.0)      # strong perspective must not explode the picture
    lo = np.maximum(projected.min(0), [-reach, -reach])
    hi = np.minimum(projected.max(0), [rw + reach, rh + reach])
    px_mm = min(MAX_SIDE / max(hi - lo), 8.0)
    T = np.array([[px_mm, 0, -lo[0] * px_mm], [0, px_mm, -lo[1] * px_mm], [0, 0, 1]], dtype=np.float64)
    size = (int((hi[0] - lo[0]) * px_mm), int((hi[1] - lo[1]) * px_mm))
    rect = cv2.warpPerspective(img, T @ H, size, flags=cv2.INTER_LINEAR, borderValue=(40, 40, 40))
    valid = cv2.warpPerspective(np.full(img.shape[:2], 255, np.uint8), T @ H, size, flags=cv2.INTER_NEAREST)
    sheet = cv2.perspectiveTransform(dst_mm.reshape(-1, 1, 2), T.astype(np.float32)).reshape(-1, 2)
    sheet_mask = np.zeros(rect.shape[:2], np.uint8)
    cv2.fillConvexPoly(sheet_mask, sheet.astype(np.int32), 255)
    obj = _object_on(rect, sheet_mask, valid, px_mm, inside=True)
    if obj is None or obj["laenge_mm"] > max(rw, rh) - 2 * MARGIN_MM - 1:
        beside = _object_on(rect, sheet_mask, valid, px_mm, inside=False)
        obj = beside or obj
    clean = rect.copy()
    # overlay: grid every 10 mm (stronger every 50 mm), reference outline, object box with dimensions
    over = rect.copy()
    for mm in range(int(lo[0] // 10 * 10), int(hi[0]) + 1, 10):
        x = int((mm - lo[0]) * px_mm)
        cv2.line(over, (x, 0), (x, size[1]), (255, 255, 255) if mm % 50 else (0, 200, 255), 1 if mm % 50 else 2)
    for mm in range(int(lo[1] // 10 * 10), int(hi[1]) + 1, 10):
        y = int((mm - lo[1]) * px_mm)
        cv2.line(over, (0, y), (size[0], y), (255, 255, 255) if mm % 50 else (0, 200, 255), 1 if mm % 50 else 2)
    rect = cv2.addWeighted(over, 0.35, rect, 0.65, 0)
    cv2.polylines(rect, [sheet.astype(np.int32)], True, (0, 200, 255), 3)
    if obj:
        box = np.array(obj["box"], dtype=np.int32)
        cv2.polylines(rect, [box], True, (60, 220, 60), 3)
        label = f"{obj['laenge_mm']:.1f} x {obj['breite_mm']:.1f} mm"
        tx, ty = int(box[:, 0].min()), max(30, int(box[:, 1].min()) - 12)
        cv2.putText(rect, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(rect, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (60, 220, 60), 2, cv2.LINE_AA)
    cv2.putText(rect, f"Raster 10 mm (gelb 50 mm) - Referenz {name} {ref_w:g} x {ref_h:g} mm", (14, size[1] - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(str(out / "entzerrt.jpg"), rect, [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(str(out / "entzerrt-roh.jpg"), clean, [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(str(out / "original.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    result = {"referenz": name, "referenz_mm": [ref_w, ref_h], "px_pro_mm": round(px_mm, 4),
              "ursprung_mm": [round(float(lo[0]), 2), round(float(lo[1]), 2)], "bild_px": list(size),
              "ecken": q.tolist(), "objekt": obj,
              "hinweis": ("Gilt für flache Gegenstände bzw. die Ebene des Blatts. Hohe Gegenstände wirken etwas größer; "
                          "für genaue Maße senkrecht von oben fotografieren und mit dem Messschieber nachmessen.")}
    (out / "info.json").write_text(json.dumps(result, ensure_ascii=False))
    return result
