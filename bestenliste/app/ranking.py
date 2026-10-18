"""Monthly rankings and achievements, computed from the stored game results.

Everything is derived by replaying the results in order, so a deleted result changes the numbers
consistently. A result counts when at least two people (not computer players) played it to the end;
points and achievements only go to players who were logged in with their Spieleabend account.
"""

import time
from datetime import datetime, timedelta

TITLES = {
    "stapeljagd": "Stapeljagd", "tiefpunkt": "Tiefpunkt", "farbrausch": "Farbrausch", "kritzelpost": "Kritzelpost",
    "schnellmaler": "Schnellmaler", "galgenraten": "Galgenraten", "imposter": "Imposter", "schaetzmeister": "Schätzmeister",
    "werwuerde": "Wer würde eher …?", "luegenbaron": "Lügenbaron", "punchline": "Punchline", "nochnie": "Ich hab noch nie …",
    "wahrheit": "Wahrheit oder Trinken", "ringoffire": "Ring of Fire", "trinklotto": "Trinklotto", "pyramide": "Pyramide",
    "pferderennen": "Pferderennen", "buzzer": "Buzzer-Quiz", "sortierfix": "Sortierfix", "spion": "Spion",
    "codewoerter": "Codewörter", "werwolf": "Werwolf", "blindmaler": "Blind gezeichnet",
    "stadtlandfluss": "Stadt-Land-Fluss", "schwimmen": "Schwimmen (31)",
}
CARD_GAMES = {"stapeljagd", "tiefpunkt", "farbrausch", "schwimmen"}
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


def month_of(ts: float) -> str:
    return time.strftime("%Y-%m", time.localtime(ts))


def month_label(month: str) -> str:
    year, m = month.split("-")
    return f"{MONTHS[int(m) - 1]} {year}"


def humans(result: dict) -> list[dict]:
    return [p for p in result["players"] if not p.get("bot")]


def members(result: dict) -> list[dict]:
    """Logged-in players: only they collect points and achievements."""
    return [p for p in humans(result) if p.get("account")]


def member_key(player: dict) -> str:
    return "acc:" + str(player["account"])


def counts(result: dict) -> bool:
    return len(humans(result)) >= 2


def points(result: dict, player: dict) -> int:
    """1 for playing, +1 for every player who finished behind you."""
    if player.get("place") is None:
        return 1
    return 1 + sum(1 for o in result["players"] if o.get("place") is not None and o["place"] > player["place"])


# -- achievements -----------------------------------------------------------------------------
# id, icon, title, description, condition, progress (current, target) or None
def _kind_wins(kind):
    return lambda s: s["kind_wins"].get(kind, 0)


ACHIEVEMENTS = [
    ("erste_partie", "🎲", "Willkommen am Tisch", "Die erste Partie gespielt", lambda s: s["games"], 1),
    ("stammgast", "🪑", "Stammgast", "25 Partien gespielt", lambda s: s["games"], 25),
    ("legende", "👑", "Spieleabend-Legende", "100 Partien gespielt", lambda s: s["games"], 100),
    ("erster_sieg", "🥇", "Erster Sieg", "Eine Partie gewonnen", lambda s: s["wins"], 1),
    ("sieger10", "🏆", "Sammelt Pokale", "10 Partien gewonnen", lambda s: s["wins"], 10),
    ("sieger50", "💎", "Unschlagbar", "50 Partien gewonnen", lambda s: s["wins"], 50),
    ("serie3", "🔥", "Heiße Phase", "3 Siege hintereinander", lambda s: s["best_streak"], 3),
    ("serie5", "⚡", "Nicht zu stoppen", "5 Siege hintereinander", lambda s: s["best_streak"], 5),
    ("allrounder", "🧩", "Allrounder", "8 verschiedene Spiele gespielt", lambda s: len(s["kinds"]), 8),
    ("sammler", "📚", "Alles einmal probiert", f"Alle {len(TITLES)} Spiele gespielt", lambda s: len(s["kinds"]), len(TITLES)),
    ("kartenhai", "🃏", "Kartenhai", "10 Kartenspiele gewonnen", lambda s: s["card_wins"], 10),
    ("kuenstler", "🎨", "Pinselprofi", "5-mal Schnellmaler gewonnen", _kind_wins("schnellmaler"), 5),
    ("wortakrobat", "🔤", "Wortakrobat", "5-mal Galgenraten gewonnen", _kind_wins("galgenraten"), 5),
    ("volltreffer", "🎯", "Volltreffer", "Im Schätzmeister höchstens 1 % daneben", lambda s: s["bullseyes"], 1),
    ("schaetzkoenig", "🧠", "Schätzkönig", "10 Volltreffer im Schätzmeister", lambda s: s["bullseyes"], 10),
    ("luegenbaron", "🎭", "Silberzunge", "3-mal Lügenbaron gewonnen", _kind_wins("luegenbaron"), 3),
    ("pointenkoenig", "😂", "Pointenkönig", "3-mal Punchline gewonnen", _kind_wins("punchline"), 3),
    ("imposter", "🕵️", "Unentdeckt", "3-mal als Imposter gewonnen", lambda s: s["imposter_wins"], 3),
    ("buzzerkoenig", "🔔", "Schnellster Finger", "3-mal das Buzzer-Quiz gewonnen", _kind_wins("buzzer"), 3),
    ("codeknacker", "🔐", "Codeknacker", "5-mal Codewörter gewonnen", _kind_wins("codewoerter"), 5),
    ("geheimagent", "🕶️", "Geheimagent", "3-mal Spion gewonnen", _kind_wins("spion"), 3),
    ("vollmond", "🌕", "Vollmondnacht", "3-mal Werwolf gewonnen", _kind_wins("werwolf"), 3),
    ("stadtlandfluss", "🗺️", "Wandelndes Lexikon", "3-mal Stadt-Land-Fluss gewonnen", _kind_wins("stadtlandfluss"), 3),
    ("einunddreissig", "🏊", "Über Wasser", "3-mal Schwimmen gewonnen", _kind_wins("schwimmen"), 3),
    ("underdog", "🐺", "Gegen alle", "Eine Partie mit 6 oder mehr Spielern gewonnen", lambda s: s["big_wins"], 1),
    ("knapp", "😅", "Haarscharf", "Mit nur einem Punkt Vorsprung gewonnen", lambda s: s["close_wins"], 1),
    ("grosserabend", "🎉", "Volle Hütte", "Eine Partie mit 8 oder mehr Spielern", lambda s: s["crowd"], 1),
    ("nachteule", "🦉", "Nachteule", "Eine Partie zwischen Mitternacht und 4 Uhr beendet", lambda s: s["night"], 1),
    ("marathon", "🏃", "Marathon", "5 Partien an einem Abend", lambda s: s["best_evening"], 5),
    ("trinkfest", "🍻", "Trinkfest", "100 Schlucke in Trinkspielen", lambda s: s["sips"], 100),
    ("monatssieger", "🌟", "Spieler des Monats", "Einen Monat auf Platz 1 beendet", lambda s: s["month_wins"], 1),
]


def new_state() -> dict:
    return {"name": "", "games": 0, "wins": 0, "streak": 0, "best_streak": 0, "kinds": set(), "kind_wins": {},
            "card_wins": 0, "bullseyes": 0, "imposter_wins": 0, "big_wins": 0, "close_wins": 0, "crowd": 0, "night": 0,
            "evenings": {}, "best_evening": 0, "sips": 0, "month_wins": 0, "unlocked": {}, "last": 0.0}


def check(state: dict, ts: float) -> list[str]:
    new = []
    for aid, _icon, _title, _desc, value, target in ACHIEVEMENTS:
        if aid not in state["unlocked"] and value(state) >= target:
            state["unlocked"][aid] = ts
            new.append(aid)
    return new


def standings(results: list[dict]) -> list[dict]:
    """Ranking of one month (only counting results)."""
    table: dict[str, dict] = {}
    for r in results:
        for p in members(r):
            k = member_key(p)
            row = table.setdefault(k, {"key": k, "name": p["name"], "points": 0, "wins": 0, "games": 0, "sips": 0, "kinds": {}})
            row["name"] = p["name"]
            row["points"] += points(r, p)
            row["games"] += 1
            row["wins"] += 1 if p.get("won") else 0
            row["sips"] += int(p.get("sips") or 0)
            row["kinds"][r["kind"]] = row["kinds"].get(r["kind"], 0) + 1
    rows = sorted(table.values(), key=lambda x: (-x["points"], -x["wins"], x["games"], x["name"].casefold()))
    place, last = 0, None
    for i, row in enumerate(rows):
        if (row["points"], row["wins"]) != last:
            place, last = i + 1, (row["points"], row["wins"])
        row["place"] = place
        row["winrate"] = round(100 * row["wins"] / row["games"]) if row["games"] else 0
        fav = max(row.pop("kinds").items(), key=lambda kv: kv[1], default=(None, 0))[0]
        row["favorite"] = TITLES.get(fav, fav) if fav else ""
    return rows


def replay(results: list[dict], now: float | None = None) -> tuple[dict, dict]:
    """Player states (lifetime stats and achievements) and the finished months' standings."""
    now = now or time.time()
    current = month_of(now)
    players: dict[str, dict] = {}
    months: dict[str, list[dict]] = {}
    finished: dict[str, list[dict]] = {}

    def close_month(month: str, ts: float) -> None:
        rows = standings(months.get(month, []))
        finished[month] = rows
        for row in rows:
            if row["place"] == 1:
                state = players.setdefault(row["key"], new_state())
                state["month_wins"] += 1
                check(state, ts)

    for r in results:
        if not counts(r):
            continue
        month = month_of(r["ts"])
        for open_month in sorted(m for m in months if m < month and m not in finished):
            close_month(open_month, r["ts"])
        months.setdefault(month, []).append(r)
        ranked = sorted((p for p in r["players"] if p.get("place") is not None), key=lambda p: p["place"])
        scores = [p.get("score") for p in ranked]
        local = datetime.fromtimestamp(r["ts"])
        evening = (local - timedelta(hours=6)).date().isoformat()
        for p in members(r):
            k = member_key(p)
            s = players.setdefault(k, new_state())
            s["name"], s["last"] = p["name"], r["ts"]
            s["games"] += 1
            s["kinds"].add(r["kind"])
            if p.get("place") is not None:     # games with a winner
                if p.get("won"):
                    s["wins"] += 1
                    s["streak"] += 1
                    s["kind_wins"][r["kind"]] = s["kind_wins"].get(r["kind"], 0) + 1
                    if r["kind"] in CARD_GAMES:
                        s["card_wins"] += 1
                    if len(r["players"]) >= 6:
                        s["big_wins"] += 1
                    others = [x for x in scores[1:] if isinstance(x, (int, float))]
                    if isinstance(p.get("score"), (int, float)) and others and 0 < abs(p["score"] - others[0]) <= 1:
                        s["close_wins"] += 1
                else:
                    s["streak"] = 0
                s["best_streak"] = max(s["best_streak"], s["streak"])
            if len(r["players"]) >= 8:
                s["crowd"] += 1
            if local.hour < 4:
                s["night"] += 1
            s["evenings"][evening] = s["evenings"].get(evening, 0) + 1
            s["best_evening"] = max(s["best_evening"], s["evenings"][evening])
            s["sips"] += int(p.get("sips") or 0)
            for h in r.get("highlights") or []:
                if h.get("account") == p["account"]:
                    if h.get("what") == "volltreffer":
                        s["bullseyes"] += 1
                    elif h.get("what") == "imposter_sieg":
                        s["imposter_wins"] += 1
            check(s, r["ts"])
    for open_month in sorted(m for m in months if m < current and m not in finished):
        close_month(open_month, now)
    return players, finished


def achievement_view(state: dict) -> list[dict]:
    out = []
    for aid, icon, title, desc, value, target in ACHIEVEMENTS:
        unlocked = state["unlocked"].get(aid)
        out.append({"id": aid, "icon": icon, "title": title, "desc": desc, "unlocked": unlocked,
                    "progress": min(value(state), target), "target": target})
    return out


def title_of(aid: str) -> tuple[str, str]:
    for a in ACHIEVEMENTS:
        if a[0] == aid:
            return a[1], a[2]
    return "🏅", aid
