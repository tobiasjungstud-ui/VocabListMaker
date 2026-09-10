"""Grundformen, Wortfamilien und Wortarten."""

from __future__ import annotations

import pytest

from vocablistmaker.models import POS
from vocablistmaker.normalize import (
    cognate_similarity,
    german_glosses,
    headword,
    pos_from_german,
    same_family,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("gave (give)", "give"),
        ("ate (eat)", "eat"),
        ("chat", "chat"),
        ("have a “good ear”", "have a good ear"),
        ("recycling", "recycling"),
    ],
)
def test_headword(raw: str, expected: str) -> None:
    assert headword(raw) == expected


@pytest.mark.parametrize(
    "first, second",
    [
        ("recycle", "recycling"),
        ("recycled", "recycle"),
        ("pollute", "pollution"),
        ("nominate", "nomination"),
        ("adapt", "adaptation"),
        ("act", "actor"),
        ("noise", "noisy"),
        ("resource", "natural resource"),
        ("knife", "Swiss army knife"),
    ],
)
def test_same_family_detects_relatives(first: str, second: str) -> None:
    assert same_family(first, second)


@pytest.mark.parametrize(
    "first, second",
    [
        ("convince", "persuade"),
        ("audience", "viewer"),
        ("plastic", "plantation"),
        ("bin", "binary"),
        ("queue", "question"),
    ],
)
def test_same_family_keeps_distinct_words_apart(first: str, second: str) -> None:
    assert not same_family(first, second)


@pytest.mark.parametrize(
    "english, german, expected",
    [
        ("rubbish", "Abfall", POS.NOUN),
        ("car boot sale", "Kofferraumverkauf, Flohmarkt", POS.NOUN),
        ("persuade", "überzeugen", POS.VERB),
        ("waterproof", "wasserdicht", POS.ADJECTIVE),
        ("typically", "normalerweise, typischerweise", POS.ADVERB),
        ("regularly", "regelmässig", POS.ADVERB),
    ],
)
def test_pos_from_german(english: str, german: str, expected: POS) -> None:
    assert pos_from_german(german, english) is expected


def test_cognate_similarity_flags_transparent_words() -> None:
    assert cognate_similarity("protein", "Protein, Eiweiß") > 0.8
    assert cognate_similarity("slogan", "Slogan, Motto") > 0.9
    assert cognate_similarity("jewellery", "Schmuck") < 0.4


def test_german_glosses_splits_alternatives() -> None:
    assert german_glosses("Paket, Verpackung") == ["paket", "verpackung"]
