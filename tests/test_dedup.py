"""Doppelungen und Bedeutungsüberschneidungen."""

from __future__ import annotations

from vocablistmaker.dedup import deduplicate, find_cross_overlaps, overlap_reason
from vocablistmaker.leveling import score_candidate
from vocablistmaker.models import Candidate


def make(english: str, german: str) -> Candidate:
    return score_candidate(Candidate(english=english, german=german))


def test_identical_words_collide() -> None:
    assert overlap_reason(make("noise", "Geräusch"), make("noise", "Lärm"))


def test_word_family_collides() -> None:
    assert overlap_reason(make("recycle", "wiederverwerten"), make("recycling", "Wiederverwertung"))


def test_synonyms_via_german_translation_collide() -> None:
    """'convince' und 'persuade' sind beide 'überzeugen' - das prüft dasselbe."""
    assert overlap_reason(make("convince", "überzeugen"), make("persuade", "überzeugen"))


def test_unrelated_words_do_not_collide() -> None:
    assert overlap_reason(make("rubbish", "Abfall"), make("falcon", "Falke")) is None


def test_deduplicate_keeps_the_more_valuable_word() -> None:
    weak = make("recycling", "Recycling")
    strong = make("recycled", "wiederverwertet")
    kept, dropped = deduplicate([weak, strong])
    assert len(kept) == 1
    assert dropped and dropped[0][1] is kept[0]


def test_no_cross_overlap_between_disjoint_tests() -> None:
    test1 = [make("rubbish", "Abfall"), make("falcon", "Falke")]
    test2 = [make("pendant", "Anhänger"), make("queue", "Warteschlange")]
    assert find_cross_overlaps(test1, test2) == []


def test_cross_overlap_is_reported() -> None:
    test1 = [make("pollute", "verschmutzen")]
    test2 = [make("pollution", "Verschmutzung")]
    assert len(find_cross_overlaps(test1, test2)) == 1
