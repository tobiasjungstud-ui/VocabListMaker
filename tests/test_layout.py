"""Passt eine Liste mit 30 Einträgen auf eine A4-Seite?"""

from __future__ import annotations

import pytest

from vocablistmaker.config import Settings
from vocablistmaker.docx_writer import check_page_fit
from vocablistmaker.layout import line_count, text_width_points
from vocablistmaker.models import TestItem

COLUMN = 4550  # Breite der Spalte "Example sentence" in Twips

LONG_SENTENCE = "Better lighting could prevent accidents at night."


def items(sentence: str = LONG_SENTENCE, count: int = 30) -> list[TestItem]:
    return [
        TestItem(i, "Unterstützer(in), Befürworter(in)", "campaigner", sentence, "prevent")
        for i in range(1, count + 1)
    ]


def test_width_grows_with_font_size() -> None:
    assert text_width_points("hello", 12) > text_width_points("hello", 10)


def test_wide_letters_take_more_space() -> None:
    assert text_width_points("mmmm", 10) > text_width_points("iiii", 10)


def test_short_text_stays_on_one_line() -> None:
    assert line_count("She felt confident.", COLUMN, 10.0) == 1


def test_long_text_wraps() -> None:
    assert line_count(LONG_SENTENCE, COLUMN, 10.0) >= 2


def test_default_settings_fit_thirty_entries_on_one_page() -> None:
    result = check_page_fit(items(), Settings())
    assert result.fits, result.describe()


def test_eleven_point_would_overflow() -> None:
    """Begründung für die Verkleinerung auf 10 pt."""
    result = check_page_fit(items(), Settings(font_size_pt=11.0, row_height_twips=397))
    assert not result.fits


def test_overlong_sentences_are_detected() -> None:
    very_long = (
        "This is a deliberately long example sentence that keeps going on and on "
        "without ever reaching a natural end point for the reader."
    )
    result = check_page_fit(items(very_long), Settings())
    assert not result.fits


@pytest.mark.parametrize("count", [20, 25, 30])
def test_usage_grows_with_the_number_of_entries(count: int) -> None:
    assert check_page_fit(items(count=count), Settings()).usage > 0
