"""Astronomy without big libraries: sun and moon, ISS passes (SGP4), meteor showers and eclipses.

Accuracy is what a person watching the sky needs: pass times to a few seconds, moon phases to a few
minutes, directions to a few degrees.
"""

import math
from datetime import date, datetime, timedelta, timezone

from sgp4.api import Satrec, jday

R_EARTH = 6378.137          # km
F_EARTH = 1 / 298.257223563
DIRS = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def direction(az: float) -> str:
    return DIRS[int((az % 360) / 22.5 + 0.5) % 16]


def julian(t: datetime) -> float:
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
    return jd + fr


def gmst(jd: float) -> float:
    """Greenwich mean sidereal time in radians."""
    t = (jd - 2451545.0) / 36525
    deg = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t - t ** 3 / 38710000
    return math.radians(deg % 360)


def observer_ecef(lat: float, lon: float, alt_m: float = 0) -> tuple[float, float, float]:
    la, lo = math.radians(lat), math.radians(lon)
    e2 = F_EARTH * (2 - F_EARTH)
    n = R_EARTH / math.sqrt(1 - e2 * math.sin(la) ** 2)
    h = alt_m / 1000
    return ((n + h) * math.cos(la) * math.cos(lo), (n + h) * math.cos(la) * math.sin(lo), (n * (1 - e2) + h) * math.sin(la))


def eci_to_ecef(v: tuple[float, float, float], theta: float) -> tuple[float, float, float]:
    c, s = math.cos(theta), math.sin(theta)
    return (c * v[0] + s * v[1], -s * v[0] + c * v[1], v[2])


def look_angles(target_ecef, obs_ecef, lat: float, lon: float) -> tuple[float, float, float]:
    """Elevation and azimuth (degrees) and distance (km) of a point seen from the observer."""
    dx, dy, dz = (target_ecef[i] - obs_ecef[i] for i in range(3))
    la, lo = math.radians(lat), math.radians(lon)
    east = -math.sin(lo) * dx + math.cos(lo) * dy
    north = -math.sin(la) * math.cos(lo) * dx - math.sin(la) * math.sin(lo) * dy + math.cos(la) * dz
    up = math.cos(la) * math.cos(lo) * dx + math.cos(la) * math.sin(lo) * dy + math.sin(la) * dz
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    return math.degrees(math.asin(up / dist)), math.degrees(math.atan2(east, north)) % 360, dist


# -- sun ------------------------------------------------------------------------------------------------
def sun_eci(jd: float) -> tuple[float, float, float]:
    """Unit vector to the sun (low precision, about 0.01°)."""
    n = jd - 2451545.0
    L = math.radians((280.460 + 0.9856474 * n) % 360)
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = L + math.radians(1.915) * math.sin(g) + math.radians(0.020) * math.sin(2 * g)
    eps = math.radians(23.439 - 0.0000004 * n)
    return (math.cos(lam), math.cos(eps) * math.sin(lam), math.sin(eps) * math.sin(lam))


def sun_elevation(t: datetime, lat: float, lon: float) -> float:
    jd = julian(t)
    s = eci_to_ecef(tuple(x * 149597870.7 for x in sun_eci(jd)), gmst(jd))
    return look_angles(s, observer_ecef(lat, lon), lat, lon)[0]


def dark_hours(day: date, lat: float, lon: float, tz, limit: float = -12) -> tuple[datetime, datetime] | None:
    """Start and end of the night (sun below `limit`) beginning on `day`, in local time."""
    start = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
    t, begin = start, None
    while t < start + timedelta(hours=24):
        below = sun_elevation(t.astimezone(timezone.utc), lat, lon) < limit
        if below and begin is None:
            begin = t
        elif not below and begin is not None:
            return begin, t
        t += timedelta(minutes=10)
    return (begin, start + timedelta(hours=24)) if begin else None


# -- ISS --------------------------------------------------------------------------------------------------
def passes(tle1: str, tle2: str, lat: float, lon: float, alt_m: float, start: datetime, days: float = 10,
           min_elev: float = 10) -> list[dict]:
    """Passes of a satellite over the observer; 'sichtbar' = observer in darkness and satellite in sunlight."""
    sat = Satrec.twoline2rv(tle1, tle2)
    obs = observer_ecef(lat, lon, alt_m)

    def at(t: datetime):
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
        err, r, _ = sat.sgp4(jd, fr)
        if err:
            return None
        elev, az, dist = look_angles(eci_to_ecef(r, gmst(jd + fr)), obs, lat, lon)
        sun = sun_eci(jd + fr)
        s = sum(r[i] * sun[i] for i in range(3))
        perp = math.sqrt(max(0.0, sum(x * x for x in r) - s * s))
        sunlit = s > 0 or perp > R_EARTH
        return elev, az, dist, sunlit

    out, t, end, step = [], start, start + timedelta(days=days), timedelta(seconds=30)
    while t < end:
        p = at(t)
        if p and p[0] > 0:
            # walk back to the rise, then through the pass in 5-second steps
            r = t - step
            while (q := at(r)) and q[0] > 0:
                r -= timedelta(seconds=5)
            u, samples = r, []
            while u < t + timedelta(minutes=20):
                q = at(u)
                if q is None:
                    break
                if q[0] > 0:
                    samples.append((u, *q))
                elif samples:
                    break
                u += timedelta(seconds=5)
            t = u + step
            if not samples:
                continue
            dark = [s for s in samples if s[4] and s[1] >= 10 and sun_elevation(s[0], lat, lon) < -6]
            pick = dark or [s for s in samples if s[1] >= 10]
            if not pick:
                continue
            # for a visible pass only the visible part counts (the ISS may vanish into Earth's shadow)
            top = max(pick, key=lambda x: x[1])
            if top[1] < min_elev:
                continue
            first, last = pick[0], pick[-1]
            out.append({"beginn": first[0].isoformat(), "hoechster": top[0].isoformat(), "ende": last[0].isoformat(),
                        "max_hoehe": round(top[1]), "von": direction(first[2]), "nach": direction(last[2]),
                        "richtung_max": direction(top[2]), "dauer_s": int((last[0] - first[0]).total_seconds()),
                        "sichtbar": bool(dark)})
        else:
            t += step
    return out


# -- moon -------------------------------------------------------------------------------------------------
def _phase_jde(k: float) -> float:
    """Meeus, chapter 49: new moon (k integer) or full moon (k + 0.5), main terms."""
    t = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * t * t
    m = math.radians((2.5534 + 29.10535670 * k) % 360)
    mp = math.radians((201.5643 + 385.81693528 * k + 0.0107582 * t * t) % 360)
    f = math.radians((160.7108 + 390.67050284 * k - 0.0016118 * t * t) % 360)
    om = math.radians((124.7746 - 1.56375588 * k) % 360)
    e = 1 - 0.002516 * t
    if abs(k - round(k)) < 1e-9:      # new moon
        c = (-0.40720 * math.sin(mp) + 0.17241 * e * math.sin(m) + 0.01608 * math.sin(2 * mp) + 0.01039 * math.sin(2 * f)
             + 0.00739 * e * math.sin(mp - m) - 0.00514 * e * math.sin(mp + m) + 0.00208 * e * e * math.sin(2 * m)
             - 0.00111 * math.sin(mp - 2 * f) - 0.00057 * math.sin(mp + 2 * f) + 0.00056 * e * math.sin(2 * mp + m)
             - 0.00042 * math.sin(3 * mp) + 0.00042 * e * math.sin(m + 2 * f) + 0.00038 * e * math.sin(m - 2 * f)
             - 0.00024 * e * math.sin(2 * mp - m) - 0.00017 * math.sin(om))
    else:                             # full moon
        c = (-0.40614 * math.sin(mp) + 0.17302 * e * math.sin(m) + 0.01614 * math.sin(2 * mp) + 0.01043 * math.sin(2 * f)
             + 0.00734 * e * math.sin(mp - m) - 0.00515 * e * math.sin(mp + m) + 0.00209 * e * e * math.sin(2 * m)
             - 0.00111 * math.sin(mp - 2 * f) - 0.00057 * math.sin(mp + 2 * f) + 0.00056 * e * math.sin(2 * mp + m)
             - 0.00042 * math.sin(3 * mp) + 0.00042 * e * math.sin(m + 2 * f) + 0.00038 * e * math.sin(m - 2 * f)
             - 0.00024 * e * math.sin(2 * mp - m) - 0.00017 * math.sin(om))
    return jde + c


def _from_jd(jd: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)


def moon_phases(start: datetime, count: int = 4) -> list[dict]:
    """The next new and full moons after `start` (UTC)."""
    k = math.floor((start.year + (start.timetuple().tm_yday / 365.25) - 2000) * 12.3685) - 1
    out = []
    while len(out) < count:
        for kk, name in ((k, "Neumond"), (k + 0.5, "Vollmond")):
            t = _from_jd(_phase_jde(kk) - 69 / 86400)      # TT → UT (about 69 s)
            if t > start:
                out.append({"art": name, "zeit": t.isoformat()})
        k += 1
    return sorted(out, key=lambda x: x["zeit"])[:count]


def moon_now(t: datetime) -> dict:
    """Age (days), illumination (%) and name of the phase."""
    k = math.floor((t.year + (t.timetuple().tm_yday / 365.25) - 2000) * 12.3685) + 1
    while _from_jd(_phase_jde(k)) > t:
        k -= 1
    age = (t - _from_jd(_phase_jde(k))).total_seconds() / 86400
    frac = age / 29.530588861
    illum = (1 - math.cos(2 * math.pi * frac)) / 2
    names = [(0.03, "Neumond"), (0.22, "zunehmende Sichel"), (0.28, "erstes Viertel"), (0.47, "zunehmender Mond"),
             (0.53, "Vollmond"), (0.72, "abnehmender Mond"), (0.78, "letztes Viertel"), (0.97, "abnehmende Sichel"), (1.01, "Neumond")]
    return {"alter_tage": round(age, 1), "beleuchtet": round(illum * 100), "phase": next(n for lim, n in names if frac < lim)}


# -- meteor showers and eclipses ----------------------------------------------------------------------------
# Peak (month, day), name, rate per hour under a dark sky (ZHR), radiant hint.
SHOWERS = [
    ((1, 3), "Quadrantiden", 110, "zweite Nachthälfte, Richtung Nordosten"),
    ((4, 22), "Lyriden", 18, "zweite Nachthälfte, hoch im Osten"),
    ((5, 6), "Eta-Aquariiden", 50, "kurz vor der Dämmerung, bei uns nur wenige"),
    ((7, 30), "Südliche Delta-Aquariiden", 25, "nach Mitternacht, tief im Süden"),
    ((8, 12), "Perseiden", 100, "ab etwa 23 Uhr, beste Zeit nach Mitternacht"),
    ((10, 8), "Draconiden", 10, "am Abend, hoch im Norden"),
    ((10, 21), "Orioniden", 20, "nach Mitternacht, Richtung Osten"),
    ((11, 17), "Leoniden", 15, "nach Mitternacht, Richtung Osten"),
    ((12, 14), "Geminiden", 150, "die ganze Nacht, bester Strom des Jahres"),
    ((12, 22), "Ursiden", 10, "die ganze Nacht, Richtung Norden"),
]

# Eclipses until 2030 with what is to be seen from Central Europe (source: NASA eclipse catalogue).
ECLIPSES = [
    ("2026-08-12", "Totale Sonnenfinsternis", "Total in Grönland, Island und Nordspanien; in Deutschland am frühen Abend tief partiell."),
    ("2026-08-28", "Partielle Mondfinsternis", "Fast total; in Mitteleuropa in den frühen Morgenstunden zu sehen."),
    ("2027-08-02", "Totale Sonnenfinsternis", "Total in Südspanien, Nordafrika und Ägypten; im Süden Europas partiell."),
    ("2028-12-31", "Totale Mondfinsternis", "Am Silvesterabend in Europa gut zu sehen."),
    ("2029-06-26", "Totale Mondfinsternis", "Sehr lange Totalität; in Europa in den Morgenstunden, im Westen besser."),
    ("2029-12-20", "Totale Mondfinsternis", "In Europa am Abend bzw. in der Nacht zu sehen."),
    ("2030-06-01", "Ringförmige Sonnenfinsternis", "Ringförmig in Nordafrika, Griechenland, Türkei und Russland; in Deutschland partiell."),
]


def showers_between(start: date, end: date) -> list[dict]:
    out = []
    for year in range(start.year, end.year + 1):
        for (month, day), name, zhr, hint in SHOWERS:
            peak = date(year, month, day)
            if start <= peak <= end:
                out.append({"name": name, "datum": peak.isoformat(), "pro_stunde": zhr, "tipp": hint})
    return sorted(out, key=lambda s: s["datum"])


def eclipses_between(start: date, end: date) -> list[dict]:
    return [{"datum": d, "name": n, "sichtbarkeit": v} for d, n, v in ECLIPSES if start.isoformat() <= d <= end.isoformat()]


def _selftest() -> None:
    # Full moon of 2026-10-26 ~04:12 UTC and new moon of 2026-11-09 ~07:02 UTC (expected values).
    ph = moon_phases(datetime(2026, 10, 20, tzinfo=timezone.utc), 2)
    assert ph[0]["art"] == "Vollmond" and ph[0]["zeit"].startswith("2026-10-26T0"), ph
    assert ph[1]["art"] == "Neumond" and ph[1]["zeit"].startswith("2026-11-09T0"), ph
    # Sun at local noon in Berlin around the equinox: about 90 - 52.5 = 37.5°
    e = sun_elevation(datetime(2026, 3, 20, 11, 10, tzinfo=timezone.utc), 52.52, 13.40)
    assert 35 < e < 40, e
    assert direction(0) == "N" and direction(95) == "O" and direction(225) == "SW"


if __name__ == "__main__":
    _selftest()
    print("ok")
