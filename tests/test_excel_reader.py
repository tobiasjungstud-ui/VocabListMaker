"""Einlesen und Unit-Erkennung."""

from __future__ import annotations

import pytest

from vocablistmaker.excel_reader import (
    parse_unit,
    parse_unit_input,
    read_workbook,
    strip_page_reference,
)


@pytest.mark.parametrize(
    "section, expected",
    [
        ("Starter Unit, p.4", 0),
        ("Unit 1, p.12", 1),
        ("Unit 4, p.44", 4),
        ("Unit 8, pp.88-89", 8),
        ("Curriculum extra 4", 4),
        ("Culture 4", 4),
        ("Extra Listening and Speaking Unit 4", 4),
        ("Project 4", 4),
        ("Songs 7", 7),
    ],
)
def test_unit_detection(section: str, expected: int) -> None:
    assert parse_unit(section)[0] == expected


def test_page_number_is_not_mistaken_for_unit() -> None:
    """Die häufigste Fehlerquelle: 'Starter Unit, p.4' ist nicht Unit 4."""
    assert parse_unit("Starter Unit, p.4")[0] == 0
    assert parse_unit("Unit 2, p.7")[0] == 2


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Unit 3, p. 30", "Unit 3"),
        ("Culture 2", "Culture 2"),
        ("Unit 5 (p. 51)", "Unit 5"),
    ],
)
def test_strip_page_reference(raw: str, expected: str) -> None:
    assert strip_page_reference(raw) == expected


@pytest.mark.parametrize(
    "text, expected",
    [("Unit 4", 4), ("4", 4), ("unit8", 8), ("Starter", 0), ("  Unit 12 ", 12)],
)
def test_parse_unit_input(text: str, expected: int) -> None:
    assert parse_unit_input(text) == expected


def test_parse_unit_input_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        parse_unit_input("keine Zahl")


def test_reads_all_units(wordlist) -> None:
    book = read_workbook(wordlist)
    assert book.units == [0, 1, 2]
    assert len(book.unit_entries(0)) == 3
    assert len(book.unit_entries(1)) > 60


def test_culture_section_belongs_to_its_unit(wordlist) -> None:
    book = read_workbook(wordlist)
    english = {e.english for e in book.unit_entries(1)}
    assert "car boot sale" in english


def test_entries_before_marks_earlier_vocabulary(wordlist) -> None:
    book = read_workbook(wordlist)
    earlier = {e.english for e in book.entries_before(1)}
    assert "afternoon" in earlier
    assert "persuade" not in earlier


def test_missing_header_raises() -> None:
    from io import BytesIO

    from openpyxl import Workbook as XlsxWorkbook

    book = XlsxWorkbook()
    book.active.append(["irgendwas", "anderes"])
    buffer = BytesIO()
    book.save(buffer)
    buffer.seek(0)
    with pytest.raises(ValueError, match="Kopfzeile"):
        read_workbook(buffer)
