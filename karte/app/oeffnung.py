"""Opening hours from OpenStreetMap (the opening_hours tag): is it open now, until when, when next.

Covers the common forms – "24/7", "Mo-Fr 08:00-18:00; Sa 09:00-13:00; Su off",
"Tu-Su 12:00-14:30,17:30-22:00", times past midnight ("18:00-02:00") and "PH off". Anything more
special (months, weeks, sunrise …) is reported as not understood; the raw text is always returned.
"""

import re
from datetime import date, datetime

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
GERMAN = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\+?$")


class Unclear(Exception):
    pass


def _days(selector: str) -> set[int]:
    days: set[int] = set()
    for part in selector.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if a not in DAYS or b not in DAYS:
                raise Unclear(part)
            i, j = DAYS.index(a), DAYS.index(b)
            days.update(range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1)))
        elif part in DAYS:
            days.add(DAYS.index(part))
        elif part == "PH":
            continue        # public holidays: not known here
        else:
            raise Unclear(part)
    return days


def _times(text: str) -> list[tuple[int, int]]:
    spans = []
    for part in text.split(","):
        m = TIME.match(part.strip())
        if not m:
            raise Unclear(part)
        start = int(m[1]) * 60 + int(m[2])
        end = int(m[3]) * 60 + int(m[4])
        if end <= start:
            end += 24 * 60          # past midnight
        spans.append((start, end))
    return spans


def week(text: str) -> dict[int, list[tuple[int, int]]]:
    """Weekday (0 = Monday) → opening spans in minutes from that day's midnight."""
    text = " ".join(str(text or "").split())
    if not text:
        raise Unclear("leer")
    if text == "24/7":
        return {d: [(0, 24 * 60)] for d in range(7)}
    plan: dict[int, list[tuple[int, int]]] = {d: [] for d in range(7)}
    for rule in [r.strip() for r in text.split(";") if r.strip()]:
        rule = re.sub(r"\s*,\s*", ",", rule)
        m = re.match(r"^((?:(?:Mo|Tu|We|Th|Fr|Sa|Su|PH)(?:-(?:Mo|Tu|We|Th|Fr|Sa|Su))?,?)+)\s*(.*)$", rule)
        if m:
            days, rest = _days(m[1]), m[2].strip()
            if not days and "PH" in m[1]:
                continue
        else:
            days, rest = set(range(7)), rule
        if rest in ("off", "closed"):
            for d in days:
                plan[d] = []
            continue
        if rest == "24/7" or rest == "00:00-24:00":
            spans = [(0, 24 * 60)]
        else:
            spans = _times(rest)
        for d in days:
            plan[d] = spans        # a later rule replaces an earlier one for the same day
    return plan


def _fmt(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def status(text: str, now: datetime | None = None) -> dict:
    """Open now? Until when / from when – in German, ready to tell the person."""
    now = now or datetime.now()
    try:
        plan = week(text)
    except Unclear:
        return {"verstanden": False, "roh": text}
    minute = now.hour * 60 + now.minute
    today = now.weekday()
    # open spans that cover now: today's, or yesterday's that run past midnight
    for start, end in plan[today]:
        if start <= minute < end:
            return {"verstanden": True, "offen": True, "bis": _fmt(end), "roh": text,
                    "text": "durchgehend geöffnet" if (start, end) == (0, 1440) and all(plan[d] == [(0, 1440)] for d in range(7))
                    else f"geöffnet bis {_fmt(end)} Uhr" + (" (nach Mitternacht)" if end > 1440 else "")}
    for start, end in plan[(today - 1) % 7]:
        if end > 1440 and minute < end - 1440:
            return {"verstanden": True, "offen": True, "bis": _fmt(end), "roh": text, "text": f"geöffnet bis {_fmt(end)} Uhr"}
    for offset in range(0, 8):
        day = (today + offset) % 7
        for start, _ in sorted(plan[day]):
            if offset == 0 and start <= minute:
                continue
            when = "heute" if offset == 0 else "morgen" if offset == 1 else GERMAN[day]
            return {"verstanden": True, "offen": False, "ab": f"{when} {_fmt(start)}", "roh": text,
                    "text": f"geschlossen – öffnet {when} um {_fmt(start)} Uhr"}
    return {"verstanden": True, "offen": False, "roh": text, "text": "laut Öffnungszeiten immer geschlossen"}


def today_text(text: str, day: date | None = None) -> str:
    try:
        plan = week(text)
    except Unclear:
        return ""
    spans = plan[(day or date.today()).weekday()]
    return ", ".join(f"{_fmt(a)}–{_fmt(b)}" for a, b in spans) if spans else "geschlossen"


def _selftest() -> None:
    t = datetime(2026, 10, 20, 12, 0)          # a Tuesday
    assert status("Mo-Fr 08:00-18:00; Sa 09:00-13:00; Su off", t)["text"] == "geöffnet bis 18:00 Uhr"
    assert status("Mo-Fr 08:00-11:00", t)["text"] == "geschlossen – öffnet morgen um 08:00 Uhr"
    assert status("Tu-Su 18:00-02:00", datetime(2026, 10, 21, 1, 0))["offen"] is True
    assert status("24/7", t)["text"] == "durchgehend geöffnet"
    assert status("Mo-Sa 10:00-20:00; PH off", datetime(2026, 10, 25, 12, 0))["text"].startswith("geschlossen – öffnet morgen")
    assert status("Mo-Fr 07:00-12:00,13:00-18:00", datetime(2026, 10, 20, 12, 30))["text"] == "geschlossen – öffnet heute um 13:00 Uhr"
    assert status("Jan-Mar Mo-Fr 08:00-12:00", t)["verstanden"] is False
    assert today_text("Mo-Fr 08:00-18:00; Sa 09:00-13:00", date(2026, 10, 24)) == "09:00–13:00"


if __name__ == "__main__":
    _selftest()
    print("ok")
