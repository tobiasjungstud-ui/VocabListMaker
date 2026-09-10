"""Herkunftsnachweis: weggelassene, ersetzte und frei ergänzte Wörter."""

from __future__ import annotations

from io import BytesIO

import pytest

from vocablistmaker.excel_reader import read_workbook
from vocablistmaker.models import TestItem, TestPair
from vocablistmaker.provenance import analyse


@pytest.fixture
def workbook(wordlist_bytes: bytes):
    return read_workbook(BytesIO(wordlist_bytes))


def pair_from(words: list[tuple[str, str]]) -> TestPair:
    half = len(words) // 2
    result = TestPair(unit=1, unit_label="Unit 1")
    result.test1 = [
        TestItem(i, de, en, f"They discussed the {en} yesterday.", en)
        for i, (en, de) in enumerate(words[:half], 1)
    ]
    result.test2 = [
        TestItem(i, de, en, f"They discussed the {en} yesterday.", en)
        for i, (en, de) in enumerate(words[half:], 1)
    ]
    return result


def test_words_from_the_workbook_are_not_flagged_as_invented(workbook) -> None:
    pair = pair_from([("persuade", "überzeugen"), ("rubbish", "Abfall")])
    result = analyse(pair, workbook, 1)
    assert result.invented == []


def test_a_word_outside_the_workbook_is_reported(workbook) -> None:
    """Frei erfundene Ergänzungen müssen sichtbar werden."""
    pair = pair_from([("persuade", "überzeugen"), ("flabbergasted", "verblüfft")])
    result = analyse(pair, workbook, 1)
    assert [w for w, _ in result.invented] == ["flabbergasted"]


def test_left_out_words_are_grouped_by_reason(workbook) -> None:
    pair = pair_from([("persuade", "überzeugen"), ("rubbish", "Abfall")])
    result = analyse(pair, workbook, 1)
    assert result.left_out_count > 0
    assert any("Grundwortschatz" in reason for reason in result.left_out)
    beginner = [w for words in result.left_out.values() for w in words]
    assert "dog" in beginner and "sun" in beginner


def test_readmitted_words_are_reported(workbook) -> None:
    """Ein bewusst behaltenes, eigentlich aussortiertes Wort wird genannt."""
    pair = pair_from([("dog", "Hund"), ("persuade", "überzeugen")])
    result = analyse(pair, workbook, 1)
    assert "dog" in [w for w, _ in result.readmitted]


def test_changed_translation_is_reported(workbook) -> None:
    pair = pair_from([("persuade", "überreden statt überzeugen"), ("rubbish", "Abfall")])
    result = analyse(pair, workbook, 1)
    assert [w for w, _, _ in result.gloss_changed] == ["persuade"]


def test_identical_translation_is_not_reported(workbook) -> None:
    pair = pair_from([("persuade", "überzeugen"), ("rubbish", "Abfall")])
    result = analyse(pair, workbook, 1)
    assert result.gloss_changed == []


def test_markdown_names_every_section(workbook) -> None:
    pair = pair_from([("persuade", "überzeugen"), ("flabbergasted", "verblüfft")])
    text = analyse(pair, workbook, 1).to_markdown()
    assert "Selbst ergänzt" in text
    assert "Weggelassen" in text
    assert "flabbergasted" in text


def test_markdown_states_clearly_when_nothing_was_invented(workbook) -> None:
    pair = pair_from([("persuade", "überzeugen"), ("rubbish", "Abfall")])
    text = analyse(pair, workbook, 1).to_markdown()
    assert "Keine. Jedes Wort der Liste steht so in der Excel-Datei." in text


def test_source_sections_are_listed(workbook) -> None:
    """Der Bericht muss zeigen, aus welchem Abschnitt ein Wort stammt."""
    pair = pair_from([("persuade", "überzeugen"), ("car boot sale", "Kofferraumverkauf")])
    result = analyse(pair, workbook, 1)
    listed = {w for words in result.sections.values() for w in words}
    assert {"persuade", "car boot sale"} <= listed
    assert any("Hauptteil" in section for section in result.sections)
    assert any("Culture" in section for section in result.sections)


def test_markdown_shows_the_sections(workbook) -> None:
    pair = pair_from([("persuade", "überzeugen"), ("car boot sale", "Kofferraumverkauf")])
    text = analyse(pair, workbook, 1).to_markdown()
    assert "Aus welchen Abschnitten die Wörter stammen" in text


def test_invented_share_is_reported(workbook) -> None:
    pair = pair_from(
        [("persuade", "überzeugen"), ("rubbish", "Abfall"),
         ("flabbergasted", "verblüfft"), ("serendipity", "Zufallsfund")]
    )
    result = analyse(pair, workbook, 1)
    assert result.invented_share == pytest.approx(0.5)
    assert "50%" in result.to_markdown()


def test_core_only_treats_culture_words_as_additions(workbook) -> None:
    """Beim Hauptteil-Massstab zählt ein Culture-Wort als Ergänzung."""
    pair = pair_from([("persuade", "überzeugen"), ("car boot sale", "Kofferraumverkauf")])
    full = analyse(pair, workbook, 1, core_only=False)
    core = analyse(pair, workbook, 1, core_only=True)
    assert "car boot sale" not in [w for w, _ in full.invented]
    assert "car boot sale" in [w for w, _ in core.invented]
    assert "nur Hauptteil" in core.unit_label
