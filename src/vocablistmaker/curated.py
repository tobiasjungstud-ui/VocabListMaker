"""Kuratierte Inhalte: von Hand geprüfte Wörter und Beispielsätze.

Dieser Weg ist für den Arbeitsablauf gedacht, bei dem die Inhalte im Chat
mit Claude entstehen und nicht von der Anwendung selbst erzeugt werden:

1. ``vocablistmaker wordlist.xlsx "Unit 7" --export-auswahl auswahl.json``
   erzeugt ein Gerüst mit der geprüften Wortauswahl und leeren Satzfeldern.
2. Die Sätze werden eingetragen (im Chat geschrieben und geprüft).
3. ``vocablistmaker --aus-datei auswahl.json -o Unit_7.docx`` baut die
   Word-Datei und lässt alle Qualitätsprüfungen darüber laufen.

Die Datei ist bewusst schlichtes JSON, damit sie sich auch von Hand
bearbeiten lässt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .additions import AdditionPlan, classify
from .config import Settings
from .leveling import score_candidate
from .models import Candidate, QualityReport, Severity, TestItem, TestPair
from .sentences import find_form_in_sentence
from .validation import validate_all

SCHEMA_VERSION = 1


def _item_to_dict(item: TestItem) -> dict[str, Any]:
    return {
        "nr": item.number,
        "deutsch": item.german,
        "englisch": item.english,
        "satz": item.sentence,
        "form": item.sentence_form,
        "quelle": item.source or "Hauptteil",
    }


def _placeholder(number: int, kind: str) -> dict[str, Any]:
    return {
        "nr": number,
        "deutsch": "",
        "englisch": "",
        "satz": "",
        "form": "",
        "quelle": f"ZU ERGÄNZEN ({kind})",
    }


def export_selection(
    pair: TestPair,
    path: str | Path,
    keep_sentences: bool = False,
    plan: AdditionPlan | None = None,
) -> Path:
    """Schreibt die Wortauswahl als bearbeitbares Gerüst.

    Ist ``plan`` gesetzt, enthält das Gerüst zusätzlich leere Platzhalter für
    die zu ergänzenden Einzelwörter und Ausdrücke - so ist beim Ausfüllen
    sofort sichtbar, wie viele von welcher Art noch fehlen.
    """
    def block(items: list[TestItem]) -> list[dict[str, Any]]:
        rows = []
        for item in items:
            row = _item_to_dict(item)
            row["quelle"] = item.source or "Hauptteil"
            if not keep_sentences:
                row["satz"] = ""
                row["form"] = ""
            rows.append(row)
        return rows

    test1, test2 = block(pair.test1), block(pair.test2)

    if plan is not None and plan.extra_total:
        # Platzhalter abwechselnd auf beide Tests verteilen.
        keep = plan.from_workbook
        merged = [r for pairwise in zip(test1, test2, strict=False) for r in pairwise]
        merged += test1[len(test2):] + test2[len(test1):]
        merged = merged[:keep]
        slots = ["Wort"] * plan.extra_words + ["Ausdruck"] * plan.extra_expressions
        merged += [_placeholder(0, kind) for kind in slots]
        half = plan.target // 2
        test1, test2 = merged[:half], merged[half:]

    for rows in (test1, test2):
        for index, row in enumerate(rows, 1):
            row["nr"] = index

    payload = {
        "schema": SCHEMA_VERSION,
        "unit": pair.unit,
        "unit_label": pair.unit_label,
        "hinweis": (
            "Feld 'satz' je Eintrag ausfüllen. Einträge mit 'ZU ERGÄNZEN' "
            "brauchen zusätzlich 'deutsch' und 'englisch'. 'form' ist die im "
            "Satz verwendete Wortform für die Fettschrift und darf leer "
            "bleiben - sie wird dann automatisch bestimmt."
        ),
        "test1": test1,
        "test2": test2,
    }
    if plan is not None:
        payload["plan"] = {
            "aus_hauptteil": plan.from_workbook,
            "ergaenzte_woerter": plan.extra_words,
            "ergaenzte_ausdruecke": plan.extra_expressions,
            "anteil_ergaenzt": round(plan.share, 3),
        }
    target = Path(path)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _read_items(rows: list[dict[str, Any]], test_name: str) -> list[TestItem]:
    items: list[TestItem] = []
    for index, row in enumerate(rows, 1):
        english = str(row.get("englisch", "")).strip()
        german = str(row.get("deutsch", "")).strip()
        sentence = str(row.get("satz", "")).strip()
        if not english or not german:
            if str(row.get("quelle", "")).startswith("ZU ERGÄNZEN"):
                raise ValueError(
                    f"{test_name}, Eintrag {index}: Platzhalter "
                    f"„{row['quelle']}“ wurde nicht ausgefüllt."
                )
            raise ValueError(
                f"{test_name}, Eintrag {index}: 'deutsch' und 'englisch' sind Pflichtfelder."
            )
        if str(row.get("quelle", "")).startswith("ZU ERGÄNZEN"):
            raise ValueError(
                f"{test_name}, Eintrag {index}: Platzhalter „{row['quelle']}“ "
                "wurde nicht ausgefüllt."
            )
        if not sentence:
            raise ValueError(
                f"{test_name}, Eintrag {index} ('{english}'): Es fehlt ein Beispielsatz. "
                "Kuratierte Listen werden nicht mit Mustersätzen aufgefüllt."
            )
        form = str(row.get("form", "")).strip()
        items.append(
            TestItem(
                number=int(row.get("nr", index)),
                german=german,
                english=english,
                sentence=sentence,
                sentence_form=find_form_in_sentence(sentence, english, form) or form or english,
                source=str(row.get("quelle", "")),
            )
        )
    return items


def load_curated(path: str | Path, settings: Settings | None = None) -> TestPair:
    """Liest eine kuratierte Datei und prüft sie vollständig durch."""
    settings = settings or Settings()
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    test1 = _read_items(list(data.get("test1", [])), "Test 1")
    test2 = _read_items(list(data.get("test2", [])), "Test 2")

    # Nummerierung immer neu vergeben, damit sie lückenlos ist.
    for items in (test1, test2):
        for position, item in enumerate(items, 1):
            item.number = position

    pair = TestPair(
        unit=int(data.get("unit", 0)),
        unit_label=str(data.get("unit_label") or f"Unit {data.get('unit', '')}").strip(),
        test1=test1,
        test2=test2,
    )
    pair.report = review_curated(pair, settings)
    return pair


def _is_addition(item: TestItem) -> bool:
    """Stammt der Eintrag aus einer Ergänzung statt aus der Wortliste?"""
    return str(item.source or "").lower().startswith("neu")


def _to_candidates(items: list[TestItem]) -> list[Candidate]:
    candidates = []
    for item in items:
        candidate = Candidate(english=item.english, german=item.german)
        score_candidate(candidate)
        candidate.sentence = item.sentence
        candidate.sentence_form = item.sentence_form
        candidates.append(candidate)
    return candidates


def review_curated(pair: TestPair, settings: Settings | None = None) -> QualityReport:
    """Lässt alle Prüfungen über eine kuratierte Liste laufen.

    Damit durchlaufen von Hand geschriebene Inhalte dieselbe Kontrolle wie
    automatisch erzeugte: Doppelungen, Niveau, Balance, Beispielsätze - und
    zusätzlich die Seitenprüfung.
    """
    settings = settings or Settings()
    report = validate_all(
        _to_candidates(pair.test1), _to_candidates(pair.test2), len(pair.test1) or 30
    )
    report.stats["quelle"] = "kuratiert"

    added = [i for i in pair.all_items if _is_addition(i)]
    report.stats["ergaenzt_gesamt"] = len(added)
    report.stats["ergaenzte_woerter"] = sum(1 for i in added if classify(i.english) == "Wort")
    report.stats["ergaenzte_ausdruecke"] = sum(
        1 for i in added if classify(i.english) == "Ausdruck"
    )

    from .docx_writer import check_page_fit

    for name, items in (("Test 1", pair.test1), ("Test 2", pair.test2)):
        fit = check_page_fit(items, settings)
        key = "seitenfuellung_test1" if name == "Test 1" else "seitenfuellung_test2"
        report.stats[key] = round(fit.usage, 3)
        if not fit.fits:
            longest = max(items, key=lambda i: len(i.sentence))
            report.add(
                "seitenueberlauf",
                Severity.ERROR,
                f"{name} passt nicht auf eine A4-Seite ({fit.usage:.0%} Füllung). "
                f"Längster Satz: '{longest.sentence}' ({len(longest.sentence)} Zeichen).",
                stage="layout",
            )
        elif fit.usage > 0.97:
            report.add(
                "seite_knapp",
                Severity.WARNING,
                f"{name} füllt die Seite zu {fit.usage:.0%} - wenig Reserve.",
                stage="layout",
            )
    return report
