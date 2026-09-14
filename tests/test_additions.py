"""Aufteilung der Ergänzungen in Einzelwörter und Ausdrücke."""

from __future__ import annotations

import pytest

from vocablistmaker.additions import (
    MAX_ADDITION_SHARE,
    AdditionPlanError,
    classify,
    max_additions,
    plan_additions,
)


def test_cap_is_forty_percent() -> None:
    assert max_additions(60) == 24
    assert MAX_ADDITION_SHARE == pytest.approx(0.40)


@pytest.mark.parametrize(
    "english, expected",
    [
        ("stand up for", "Ausdruck"),
        ("make a difference", "Ausdruck"),
        ("box office", "Ausdruck"),
        ("prejudice", "Wort"),
        ("refugee", "Wort"),
        ("gave (give)", "Wort"),
    ],
)
def test_classify(english: str, expected: str) -> None:
    assert classify(english) == expected


def test_gap_is_filled_when_no_split_is_given() -> None:
    plan = plan_additions(41, 60)
    assert plan.from_workbook == 41
    assert plan.extra_words == 19
    assert plan.extra_expressions == 0
    assert plan.within_cap


def test_explicit_split_is_honoured() -> None:
    plan = plan_additions(41, 60, extra_words=12, extra_expressions=9)
    assert (plan.extra_words, plan.extra_expressions) == (12, 9)
    assert plan.from_workbook == 39
    assert plan.share == pytest.approx(0.35)


def test_expressions_alone_are_allowed() -> None:
    plan = plan_additions(45, 60, extra_words=0, extra_expressions=15)
    assert plan.extra_expressions == 15
    assert plan.extra_words == 0


def test_exactly_at_the_cap_is_accepted() -> None:
    plan = plan_additions(36, 60, extra_words=15, extra_expressions=9)
    assert plan.share == pytest.approx(0.40)
    assert plan.within_cap


def test_too_many_additions_are_refused() -> None:
    with pytest.raises(AdditionPlanError, match="höchstens 24"):
        plan_additions(41, 60, extra_words=20, extra_expressions=10)


def test_too_few_additions_leave_a_gap() -> None:
    with pytest.raises(AdditionPlanError, match="Anzahl erhöhen"):
        plan_additions(41, 60, extra_words=5, extra_expressions=5)


def test_gap_larger_than_the_cap_is_explained() -> None:
    """Unit 8: 33 Wörter im Hauptteil reichen auch mit 40 % nicht."""
    with pytest.raises(AdditionPlanError, match="Grenzfälle"):
        plan_additions(33, 60)


def test_gap_larger_than_cap_with_explicit_split() -> None:
    with pytest.raises(AdditionPlanError, match="Grenzfälle"):
        plan_additions(33, 60, extra_words=15, extra_expressions=9)


def test_describe_mentions_both_kinds() -> None:
    text = plan_additions(39, 60, extra_words=12, extra_expressions=9).describe()
    assert "Einzelwörter" in text and "Ausdrücke" in text
