"""Niveaubewertung und Lernwert."""

from __future__ import annotations

import pytest

from vocablistmaker.leveling import LevelContext, is_core_vocabulary, is_usable, score_candidate
from vocablistmaker.models import Candidate, VocabEntry


def make(english: str, german: str, **kw) -> Candidate:
    return score_candidate(Candidate(english=english, german=german, **kw))


@pytest.mark.parametrize("word", ["sun", "star", "house", "dog", "big", "go", "water"])
def test_obvious_beginner_words_are_rejected(word: str) -> None:
    """Genau die Wörter, die laut Auftrag aussortiert werden sollen."""
    candidate = make(word, "Testwort")
    assert not is_usable(candidate), f"'{word}' hätte aussortiert werden müssen"


@pytest.mark.parametrize(
    "english, german",
    [
        ("persuade", "überzeugen"),
        ("waterproof", "wasserdicht"),
        ("jewellery", "Schmuck"),
        ("rubbish", "Abfall"),
        ("negotiate", "verhandeln"),
    ],
)
def test_useful_b1_b2_words_are_kept(english: str, german: str) -> None:
    assert is_usable(make(english, german))


def test_core_vocabulary_list_covers_everyday_words() -> None:
    assert is_core_vocabulary("house")
    assert is_core_vocabulary("go to school")
    assert not is_core_vocabulary("negotiate")


def test_transparent_cognates_lose_learning_value() -> None:
    """Für deutschsprachige Lernende bringt 'Protein' nichts."""
    cognate = make("protein", "Protein")
    genuine = make("jewellery", "Schmuck")
    assert "kognat" in cognate.flags
    assert not is_usable(cognate)
    assert genuine.learning_value > cognate.learning_value


def test_words_from_earlier_units_are_penalised() -> None:
    earlier = [VocabEntry(english="persuade", german="überzeugen", section="Unit 1", unit=1)]
    context = LevelContext.from_entries(earlier)
    repeated = score_candidate(Candidate(english="persuade", german="überzeugen"), context)
    assert "frueher_gelernt" in repeated.flags
    assert not is_usable(repeated)


def test_very_rare_words_are_rejected() -> None:
    assert not is_usable(make("anosmia", "Anosmie"))


def test_difficulty_is_bounded_and_ordered() -> None:
    easy = make("noise", "Geräusch")
    hard = make("caterpillar", "Raupe")
    assert 0.0 <= easy.difficulty <= 1.0
    assert 0.0 <= hard.difficulty <= 1.0
    assert hard.difficulty > easy.difficulty
