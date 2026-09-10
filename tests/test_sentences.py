"""Beispielsätze: Erzeugung, Zielwortsuche, Prüfungen."""

from __future__ import annotations

import pytest

from vocablistmaker.leveling import score_candidate
from vocablistmaker.models import Candidate
from vocablistmaker.sentences import (
    check_sentence,
    ensure_sentence,
    find_form_in_sentence,
    gives_away_answer,
)


def make(english: str, german: str) -> Candidate:
    return score_candidate(Candidate(english=english, german=german))


@pytest.mark.parametrize(
    "sentence, target, expected",
    [
        ("Have you ever acted in a school play?", "act", "acted"),
        ("The story takes place in New York.", "take place", "takes place"),
        ("The winning pictures are displayed there.", "display", "displayed"),
        ("She prefers graphic novels to normal ones.", "graphic novel", "graphic novels"),
        ("Nothing matches here.", "falcon", ""),
    ],
)
def test_find_form_in_sentence(sentence: str, target: str, expected: str) -> None:
    assert find_form_in_sentence(sentence, target) == expected


def test_definition_sentences_are_rejected() -> None:
    candidate = make("villain", "Bösewicht")
    assert gives_away_answer("A villain is a bad person in a story.", candidate)


def test_context_sentences_are_accepted() -> None:
    candidate = make("villain", "Bösewicht")
    assert not gives_away_answer("The villain is more interesting than the hero.", candidate)


def test_german_translation_in_sentence_is_caught() -> None:
    candidate = make("villain", "Bösewicht")
    assert gives_away_answer("The Bösewicht appears in chapter two.", candidate)


def test_cognate_does_not_trigger_a_false_alarm() -> None:
    """'protein' enthält zwangsläufig sein deutsches Gegenstück - das ist kein Verrat."""
    candidate = make("protein", "Protein, Eiweiß")
    candidate.sentence_form = "protein"
    assert not gives_away_answer("Beans contain a lot of protein.", candidate)


@pytest.mark.parametrize(
    "sentence, code",
    [
        ("Too short.", "satz_zu_kurz"),
        ("The falcon flies over the field every single morning", "satz_ohne_punkt"),
        ("the falcon flies over the field today.", "satz_klein"),
        ("The bird flies over the field today.", "zielwort_fehlt"),
    ],
)
def test_sentence_checks_detect_problems(sentence: str, code: str) -> None:
    candidate = make("falcon", "Falke")
    assert code in {issue.code for issue in check_sentence(candidate, sentence)}


def test_generated_sentences_pass_their_own_checks() -> None:
    for english, german in [
        ("persuade", "überzeugen"), ("rubbish", "Abfall"), ("light bulb", "Glühbirne"),
        ("waterproof", "wasserdicht"), ("typically", "normalerweise"), ("queue", "Warteschlange"),
    ]:
        candidate = ensure_sentence(make(english, german))
        assert candidate.sentence
        assert not check_sentence(candidate), f"{english}: {check_sentence(candidate)}"


def test_uncountable_nouns_get_no_article() -> None:
    candidate = ensure_sentence(make("rubbish", "Abfall"))
    assert "a rubbish" not in candidate.sentence.lower()
