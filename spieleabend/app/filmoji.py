"""Filmoji: a film told in emojis – guess the title. A game for one player (like Wortgitter).

The page gets the emojis and hints; the titles stay on the server, which checks the guesses
tolerantly (case, umlauts, articles, small typos, English original titles).
"""

import re
import unicodedata

from filmoji_daten import FILME

ARTICLES = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "the", "a", "an"}
FILLERS = ARTICLES | {"und", "in", "im", "zu", "von", "vom", "mit", "auf", "of", "to", "and", "nicht", "man", "ist", "hat"}


def words(text: str, plain: bool = False) -> list[str]:
    """Lower case ASCII words: umlauts become ae/oe/ue (or a/o/u with plain), ß becomes ss,
    punctuation is dropped."""
    text = str(text).lower().replace("&", " und ").replace("?", " fragezeichen ")
    if not plain:
        text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = text.replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text).split()


def distance(a: str, b: str) -> int:
    """Levenshtein distance."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def tolerance(length: int) -> int:
    """How many typos are forgiven for an answer of this length."""
    if length <= 4:
        return 0
    if length <= 7:
        return 1
    if length <= 12:
        return 2
    return max(3, length // 6)


def _keys(text: str) -> set[str]:
    """Ways to write the answer that count as the same: without a leading article, without all
    articles and small words, and with umlauts written without the 'e' (König → konig)."""
    keys = set()
    for plain in (False, True):
        ws = words(text, plain)
        while len(ws) > 1 and ws[0] in ARTICLES:
            ws = ws[1:]
        keys |= {"".join(ws), "".join(w for w in ws if w not in FILLERS) or "".join(ws)}
    return {k for k in keys if k}


def _close(a: str, b: str) -> bool:
    return distance(a, b) <= tolerance(len(b))


def _covers(guess: str, answer: str) -> bool:
    """Long answers (sayings): enough of the important words are there, each with a typo at most."""
    need = [w for w in words(answer) if w not in FILLERS]
    have = [w for w in words(guess) if w not in FILLERS]
    if len(need) < 3 or not have:
        return False
    found = sum(1 for w in need if any(distance(w, h) <= (1 if len(w) >= 5 else 0) for h in have))
    return found >= max(3, round(len(need) * .75))


def matches(guess: str, answer: str, alternatives=()) -> bool:
    guess_keys = _keys(guess)
    if not guess_keys:
        return False
    options = {k for option in (answer, *alternatives) for k in _keys(option)}
    if guess_keys & OTHER_ANSWERS and not guess_keys & options:
        return False     # exactly another puzzle's answer (Island ≠ Irland) is no typo
    numbers = re.findall(r"\d+", guess)
    for option in (answer, *alternatives):
        if re.findall(r"\d+", option) not in ([], numbers):
            continue     # numbers have to be right (101 Dalmatiner, not 100)
        for want in _keys(option):
            if any(_close(g, want) for g in guess_keys):
                return True
        if _covers(guess, option):
            return True
    return False


OTHER_ANSWERS = {k for _, answer, alts, _ in FILME for option in (answer, *alts) for k in _keys(option)}


def mask(title: str) -> str:
    """Hint: the first letter of every word, the other letters as underscores ("D__ K____ d__ L____")."""
    return re.sub(r"\w+", lambda m: m.group(0)[0] + "_" * (len(m.group(0)) - 1), title)


def puzzles() -> list[dict]:
    """What the page needs: emojis and hints, no titles."""
    return [{"id": i, "e": e, "y": year, "m": mask(title)} for i, (e, title, _, year) in enumerate(FILME)]


def title(film_id) -> str | None:
    try:
        return FILME[int(film_id)][1]
    except (TypeError, ValueError, IndexError):
        return None


def check(film_id, guess: str) -> bool:
    e, answer, alts, _ = FILME[int(film_id)]
    return matches(str(guess)[:120], answer, alts)
