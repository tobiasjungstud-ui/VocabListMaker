"""Bewertung von Sprachniveau, Schwierigkeit und Lernwert.

Zielgruppe sind Lernende auf B1.2-B2.1. Ein Wort ist geeignet, wenn es
(a) nicht längst bekannt ist, (b) im Englischen wirklich gebräuchlich ist und
(c) den Wortschatz spürbar erweitert.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path

from .models import POS, Candidate
from .normalize import (
    cognate_similarity,
    first_gloss,
    headword,
    is_multiword,
    pos_from_german,
)

_DATA = Path(__file__).parent / "data"

# Zipf-Häufigkeit (wordfreq): 7 = extrem häufig ("the"), 1 = sehr selten.
ZIPF_TOO_EASY = 4.75  # darüber: Grundwortschatz, längst bekannt
ZIPF_SWEET_HIGH = 4.55
ZIPF_SWEET_LOW = 3.00
ZIPF_TOO_RARE = 2.45  # darunter: exotisch, kein Alltagsnutzen

COGNATE_TRANSPARENT = 0.92  # praktisch identisch mit dem deutschen Wort
COGNATE_HIGH = 0.75

_CEFR_BOUNDS = (
    (5.30, "A1"),
    (4.75, "A2"),
    (4.15, "B1"),
    (3.35, "B2"),
    (2.60, "C1"),
)

# Sehr häufige Funktions- und Alltagswörter, die selbst bei mittlerer
# Häufigkeit keinen Prüfwert haben.
_LOW_VALUE_EXTRA = {
    "etc", "ok", "okay", "hi", "hey", "www", "email", "internet", "online",
    "app", "video", "foto", "info", "sms", "cd", "dvd", "pc", "tv",
}

_PROPER_NOUN = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$")


@functools.lru_cache(maxsize=1)
def _core_vocabulary() -> frozenset[str]:
    """A1/A2-Grundwortschatz, der als bekannt vorausgesetzt wird."""
    words: set[str] = set()
    path = _DATA / "a1_a2_core.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip().lower()
            if line:
                words.update(t for t in line.split() if t)
    return frozenset(words)


@functools.lru_cache(maxsize=4096)
def zipf(word: str) -> float:
    """Häufigkeit des seltensten Inhaltsworts einer Wendung."""
    try:
        from wordfreq import zipf_frequency
    except ImportError:  # pragma: no cover - wordfreq ist eine Pflichtabhängigkeit
        return 3.8

    tokens = [t for t in re.findall(r"[a-z'’-]+", word.lower()) if len(t) > 2]
    if not tokens:
        return 3.8
    scores = [zipf_frequency(t, "en") for t in tokens]
    scores = [s for s in scores if s > 0] or [2.0]
    # Eine Wendung ist so schwer wie ihr schwierigstes Element, aber
    # Mehrwortausdrücke sind als Ganzes immer etwas anspruchsvoller.
    return min(scores)


def cefr_estimate(z: float) -> str:
    for bound, level in _CEFR_BOUNDS:
        if z >= bound:
            return level
    return "C2"


@dataclass
class LevelContext:
    """Kontextwissen aus der Arbeitsmappe: was wurde vorher schon gelernt?"""

    known_earlier: frozenset[str] = frozenset()
    known_earlier_stems: frozenset[str] = frozenset()

    @classmethod
    def from_entries(cls, earlier_entries) -> LevelContext:
        from .normalize import stem

        words = {headword(e.english).lower() for e in earlier_entries}
        stems = {stem(e.english) for e in earlier_entries}
        return cls(frozenset(words), frozenset(stems))


def is_core_vocabulary(word: str) -> bool:
    """Steht das Wort im vorausgesetzten A1/A2-Grundwortschatz?"""
    hw = headword(word).lower()
    core = _core_vocabulary()
    if hw in core:
        return True
    tokens = hw.split()
    # Eine Wendung gilt nur dann als trivial, wenn *alle* Bestandteile trivial sind.
    return bool(tokens) and all(t in core or len(t) <= 2 for t in tokens)


def score_candidate(c: Candidate, ctx: LevelContext | None = None) -> Candidate:
    """Füllt Wortart, Häufigkeit, Niveau, Schwierigkeit und Lernwert."""
    ctx = ctx or LevelContext()
    from .normalize import stem as _stem

    c.headword = headword(c.english)
    c.stem = _stem(c.english)
    c.pos = pos_from_german(c.german, c.english)
    c.zipf = zipf(c.headword)
    c.cefr = cefr_estimate(c.zipf)

    hw_lower = c.headword.lower()
    cognate = cognate_similarity(c.english, c.german)

    # --- Ausschlussgründe -------------------------------------------------
    if not c.headword or len(hw_lower) < 2:
        c.flag("unbrauchbar", "Kein verwertbares Stichwort.")
    if is_core_vocabulary(c.headword):
        # Harte Untergrenze: Grundwortschatz darf auch dann nicht in einen
        # Test rutschen, wenn die Unit zu wenig Material hergibt.
        c.flag("grundwortschatz", "Gehört zum A1/A2-Grundwortschatz.")
        c.flag("zu_einfach", "Gehört zum A1/A2-Grundwortschatz.")
    if c.zipf >= ZIPF_TOO_EASY:
        c.flag("zu_einfach", f"Sehr hohe Häufigkeit (Zipf {c.zipf:.2f}).")
    if c.zipf < ZIPF_TOO_RARE and not is_multiword(c.headword):
        c.flag("zu_selten", f"Im Englischen kaum gebräuchlich (Zipf {c.zipf:.2f}).")
    if hw_lower in ctx.known_earlier or c.stem in ctx.known_earlier_stems:
        c.flag("frueher_gelernt", "Kommt bereits in einer früheren Unit vor.")
    if cognate >= COGNATE_TRANSPARENT and not is_multiword(c.headword):
        c.flag("kognat", "Deckungsgleich mit dem deutschen Wort - kein Lernzuwachs.")
    if hw_lower in _LOW_VALUE_EXTRA:
        c.flag("kognat", "Internationalismus ohne Prüfwert.")
    if _PROPER_NOUN.match(c.headword) and c.zipf < 3.2:
        c.flag("eigenname", "Wirkt wie ein Eigenname.")

    # --- Schwierigkeit (0 = leicht, 1 = schwer) ---------------------------
    span = 5.6 - 2.2
    difficulty = max(0.0, min(1.0, (5.6 - c.zipf) / span))
    if is_multiword(c.headword):
        difficulty += 0.06
    if len(hw_lower) >= 10:
        difficulty += 0.04
    if c.pos is POS.PHRASE:
        difficulty += 0.05
    if cognate >= COGNATE_HIGH:
        difficulty -= 0.10
    c.difficulty = max(0.0, min(1.0, difficulty))

    # --- Lernwert ---------------------------------------------------------
    value = 1.0
    # Optimalzone: genau zwischen "kennt man schon" und "braucht man nie".
    if ZIPF_SWEET_LOW <= c.zipf <= ZIPF_SWEET_HIGH:
        value += 0.55
    elif c.zipf > ZIPF_SWEET_HIGH:
        value -= 1.4 * (c.zipf - ZIPF_SWEET_HIGH)
    else:
        value -= 1.1 * (ZIPF_SWEET_LOW - c.zipf)

    if is_multiword(c.headword):
        value += 0.20  # Kollokationen und Phrasal Verbs sind echter Zugewinn
    if c.pos is POS.PHRASE:
        value += 0.10
    if cognate >= COGNATE_HIGH:
        value -= 0.75 * (cognate - COGNATE_HIGH) / (1.0 - COGNATE_HIGH) - 0.05
    if c.oxford3000 and c.zipf < ZIPF_TOO_EASY:
        value += 0.10  # im Kernwortschatz der Oberstufe verankert
    if "frueher_gelernt" in c.flags:
        value -= 0.60
    if "zu_einfach" in c.flags:
        value -= 1.20
    if "zu_selten" in c.flags:
        value -= 0.90
    if "kognat" in c.flags:
        value -= 1.20
    if len(first_gloss(c.german)) < 2:
        value -= 0.50
    c.learning_value = round(max(0.0, min(2.0, value)), 3)
    return c


def is_usable(c: Candidate) -> bool:
    """Darf der Kandidat überhaupt in einen Test?"""
    blocking = {
        "zu_einfach", "zu_selten", "kognat", "unbrauchbar", "eigenname", "frueher_gelernt",
    }
    return not (blocking & set(c.flags))


#: Merkmale, die ein Wort unter allen Umständen ausschliessen - auch wenn
#: dadurch zu wenige Wörter übrig bleiben.
HARD_EXCLUSIONS = frozenset({"grundwortschatz", "unbrauchbar", "eigenname"})


def is_hard_excluded(c: Candidate) -> bool:
    """Darf das Wort auch als Notlösung nicht nachrücken?"""
    return bool(HARD_EXCLUSIONS & set(c.flags))


def describe(c: Candidate) -> str:  # pragma: no cover - Diagnoseausgabe
    return (
        f"{c.headword:26s} {c.pos.value:16s} zipf={c.zipf:4.2f} {c.cefr:3s} "
        f"diff={c.difficulty:.2f} wert={c.learning_value:.2f} {','.join(c.flags)}"
    )
