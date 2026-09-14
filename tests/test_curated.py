"""Kuratierte Inhalte: Einlesen, Prüfen, Seitenkontrolle."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vocablistmaker.config import Settings
from vocablistmaker.curated import export_selection, load_curated
from vocablistmaker.models import TestItem, TestPair


def make_file(tmp_path: Path, sentence: str = "She signed the petition last week.", count: int = 30) -> Path:
    def block() -> list[dict]:
        return [
            {"nr": i, "deutsch": f"Wort {i}", "englisch": "petition", "satz": sentence, "form": ""}
            for i in range(1, count + 1)
        ]

    payload = {"schema": 1, "unit": 7, "unit_label": "Unit 7", "test1": block(), "test2": block()}
    path = tmp_path / "kuratiert.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def pair() -> TestPair:
    result = TestPair(unit=7, unit_label="Unit 7")
    result.test1 = [
        TestItem(i, "Petition", "petition", "Over ten thousand people signed the petition.", "petition")
        for i in range(1, 31)
    ]
    result.test2 = [
        TestItem(i, "Spende", "donation", "The hospital received a large donation last week.", "donation")
        for i in range(1, 31)
    ]
    return result


def test_export_leaves_sentence_fields_empty(pair: TestPair, tmp_path: Path) -> None:
    target = export_selection(pair, tmp_path / "auswahl.json")
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["unit_label"] == "Unit 7"
    assert len(data["test1"]) == 30
    assert all(row["satz"] == "" for row in data["test1"])
    assert all(row["englisch"] for row in data["test1"])


def test_export_can_keep_sentences(pair: TestPair, tmp_path: Path) -> None:
    target = export_selection(pair, tmp_path / "auswahl.json", keep_sentences=True)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert all(row["satz"] for row in data["test1"])


def test_missing_sentence_is_rejected(tmp_path: Path) -> None:
    """Kuratierte Listen werden nicht stillschweigend mit Mustersätzen gefüllt."""
    path = make_file(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["test1"][3]["satz"] = ""
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Beispielsatz"):
        load_curated(path)


def test_missing_translation_is_rejected(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["test2"][0]["deutsch"] = ""
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Pflichtfelder"):
        load_curated(path)


def test_numbering_is_repaired(tmp_path: Path) -> None:
    path = make_file(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["test1"]:
        row["nr"] = 99
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    pair = load_curated(path)
    assert [i.number for i in pair.test1] == list(range(1, 31))


def test_word_form_is_found_for_bolding(tmp_path: Path) -> None:
    path = make_file(tmp_path, "They signed two petitions last month.")
    pair = load_curated(path)
    assert pair.test1[0].sentence_form == "petitions"


def test_overlong_sentences_are_reported(tmp_path: Path) -> None:
    long_sentence = (
        "The campaigners signed a very long petition that simply refused to end "
        "and carried on for far too many words indeed."
    )
    pair = load_curated(make_file(tmp_path, long_sentence))
    assert any(i.code == "seitenueberlauf" for i in pair.report.errors)


def test_page_usage_is_recorded(tmp_path: Path) -> None:
    pair = load_curated(make_file(tmp_path))
    assert 0 < pair.report.stats["seitenfuellung_test1"] <= 1.0


@pytest.mark.parametrize("unit", [7, 8])
def test_shipped_lists_are_clean(unit: int) -> None:
    """Die mitgelieferten Listen müssen fehlerfrei durch alle Prüfungen gehen."""
    path = Path(__file__).resolve().parents[1] / "kuratiert" / f"unit_{unit}.json"
    if not path.exists():
        pytest.skip("Kuratierte Liste nicht vorhanden")
    pair = load_curated(path, Settings())
    assert pair.report.errors == [], [str(i) for i in pair.report.errors]
    assert len(pair.test1) == 30 and len(pair.test2) == 30
    assert pair.report.stats["seitenfuellung_test1"] <= 1.0
    assert pair.report.stats["seitenfuellung_test2"] <= 1.0


def test_export_writes_placeholders_for_both_kinds(pair: TestPair, tmp_path: Path) -> None:
    from vocablistmaker.additions import plan_additions

    plan = plan_additions(39, 60, extra_words=12, extra_expressions=9)
    target = export_selection(pair, tmp_path / "auswahl.json", plan=plan)
    data = json.loads(target.read_text(encoding="utf-8"))
    rows = data["test1"] + data["test2"]
    assert sum(1 for r in rows if r["quelle"] == "ZU ERGÄNZEN (Wort)") == 12
    assert sum(1 for r in rows if r["quelle"] == "ZU ERGÄNZEN (Ausdruck)") == 9
    assert data["plan"]["ergaenzte_ausdruecke"] == 9


def test_unfilled_placeholder_is_refused(pair: TestPair, tmp_path: Path) -> None:
    from vocablistmaker.additions import plan_additions

    plan = plan_additions(39, 60, extra_words=12, extra_expressions=9)
    target = export_selection(pair, tmp_path / "auswahl.json", plan=plan, keep_sentences=True)
    with pytest.raises(ValueError, match="ZU ERGÄNZEN"):
        load_curated(target)


def test_report_counts_words_and_expressions(tmp_path: Path) -> None:
    rows = []
    for i in range(1, 31):
        rows.append({"nr": i, "deutsch": f"Wort {i}", "englisch": "petition",
                     "satz": "She signed the petition last week.", "quelle": "Hauptteil"})
    extra = [
        {"nr": 1, "deutsch": "sich einsetzen für", "englisch": "stand up for",
         "satz": "She always stands up for her brother.", "quelle": "neu (Ausdruck)"},
        {"nr": 2, "deutsch": "Vorurteil", "englisch": "prejudice",
         "satz": "Their prejudice slowly disappeared here.", "quelle": "neu (Wort)"},
    ]
    payload = {"schema": 1, "unit": 7, "unit_label": "Unit 7",
               "test1": rows, "test2": extra + rows[:28]}
    path = tmp_path / "k.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    pair = load_curated(path)
    assert pair.report.stats["ergaenzte_ausdruecke"] == 1
    assert pair.report.stats["ergaenzte_woerter"] == 1
