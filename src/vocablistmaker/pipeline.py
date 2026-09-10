"""Orchestrierung: von der Excel-Datei zur fertigen Word-Datei.

Ablauf
------
1. Excel einlesen, Unit bestimmen, Pool der Unit sammeln
2. Regelbasierte Bewertung (Niveau, Lernwert, Wortart)
3. Fachliche Beurteilung durch das Sprachmodell (optional)
4. Doppelungen und Bedeutungsüberschneidungen entfernen
5. Auswahl von 60 Wörtern, bei Bedarf Ersatzwörter beschaffen
6. Aufteilung auf zwei gleich schwere Tests
7. Beispielsätze erzeugen und prüfen
8. Mehrere Validierungs- und Reparaturrunden
9. Abschliessende Gesamtkontrolle
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from .config import Settings
from .dedup import deduplicate, overlap_reason
from .enrich import find_replacements, unit_topics
from .excel_reader import Workbook, collect_unit_pool, read_workbook
from .leveling import LevelContext, is_hard_excluded, is_usable, score_candidate
from .llm import (
    DuplicateReport,
    FinalReview,
    LLMClient,
    SentenceDraftList,
    SentenceVerdictList,
    WordJudgementList,
    prompt_check_sentences,
    prompt_find_duplicates,
    prompt_judge_words,
    prompt_sentences,
)
from .models import Candidate, QualityReport, Severity, TestItem, TestPair
from .selection import select_words, split_balanced
from .sentences import check_sentence, ensure_sentence, find_form_in_sentence
from .validation import validate_all

log = logging.getLogger(__name__)

Progress = Callable[[str, float], None]


def _noop(message: str, fraction: float) -> None:
    log.info("[%3.0f%%] %s", fraction * 100, message)


@dataclass
class PipelineResult:
    pair: TestPair
    workbook: Workbook
    candidates: list[Candidate] = field(default_factory=list)
    llm_used: bool = False
    llm_calls: int = 0

    @property
    def report(self) -> QualityReport:
        return self.pair.report


def _chunks(items: Sequence, size: int) -> list[Sequence]:
    return [items[i : i + size] for i in range(0, len(items), size)] or []


# ---------------------------------------------------------------------------
# Einzelne Stufen
# ---------------------------------------------------------------------------


def judge_with_llm(
    client: LLMClient,
    candidates: list[Candidate],
    unit_label: str,
    topics: str,
    report: QualityReport,
    batch_size: int,
) -> None:
    """Lässt das Sprachmodell Niveau und Übersetzungen beurteilen."""
    if not client.available:
        return
    by_key = {c.headword.lower(): c for c in candidates}

    for batch in _chunks(candidates, batch_size):
        rows = [(c.headword, c.german) for c in batch]
        result = client.try_structured(
            prompt_judge_words(rows, unit_label, topics), WordJudgementList
        )
        if result is None:
            return

        for judgement in result.judgements:
            candidate = by_key.get(judgement.english.strip().lower())
            if candidate is None:
                continue
            candidate.cefr = judgement.cefr or candidate.cefr
            if judgement.too_easy:
                candidate.flag("zu_einfach", judgement.reason or "Vom Modell als zu einfach beurteilt.")
            if judgement.too_obscure:
                candidate.flag("zu_selten", judgement.reason or "Vom Modell als unüblich beurteilt.")
            if not judgement.keep and not (judgement.too_easy or judgement.too_obscure):
                candidate.flag("modell_abgelehnt", judgement.reason or "Vom Modell abgelehnt.")
            if not judgement.translation_ok and judgement.corrected_german.strip():
                report.add(
                    "uebersetzung_korrigiert",
                    Severity.INFO,
                    f"'{candidate.headword}': Übersetzung von '{candidate.german}' zu "
                    f"'{judgement.corrected_german.strip()}' korrigiert.",
                    words=[candidate.headword],
                    stage="beurteilung",
                )
                candidate.german = judgement.corrected_german.strip()


def semantic_dedup_with_llm(
    client: LLMClient, chosen: list[Candidate], unit_label: str, report: QualityReport
) -> list[Candidate]:
    """Entfernt Paare, die inhaltlich dasselbe prüfen, aber formal verschieden sind."""
    if not client.available or len(chosen) < 2:
        return chosen

    rows = [(c.headword, c.german) for c in chosen]
    result = client.try_structured(prompt_find_duplicates(rows, unit_label), DuplicateReport)
    if result is None or not result.pairs:
        return chosen

    by_key = {c.headword.lower(): c for c in chosen}
    to_drop: set[str] = set()
    for pair in result.pairs:
        drop_key = pair.drop.strip().lower()
        if drop_key not in by_key:
            continue
        # Nie so viele streichen, dass die Liste unbrauchbar klein wird.
        if len(chosen) - len(to_drop) - 1 < 2:
            break
        to_drop.add(drop_key)
        report.add(
            "semantische_doppelung",
            Severity.INFO,
            f"'{pair.first}' und '{pair.second}' prüfen dasselbe ({pair.reason}); "
            f"'{pair.drop}' wurde entfernt.",
            words=[pair.first, pair.second],
            stage="doppelungen",
        )
    return [c for c in chosen if c.headword.lower() not in to_drop]


def write_sentences(
    client: LLMClient,
    items: list[Candidate],
    unit_label: str,
    batch_size: int,
    report: QualityReport,
    allow_templates: bool = True,
) -> None:
    """Beispielsätze erzeugen - per Sprachmodell, sonst regelbasiert.

    Ist ``allow_templates`` False, bricht die Funktion ab, statt Sätze aus
    festen Mustern zu erzeugen.
    """
    pending = [c for c in items if not c.sentence]
    if client.available and pending:
        by_key = {c.headword.lower(): c for c in pending}
        for batch in _chunks(pending, batch_size):
            rows = [(c.headword, c.german) for c in batch]
            result = client.try_structured(
                prompt_sentences(rows, unit_label), SentenceDraftList
            )
            if result is None:
                break
            for draft in result.sentences:
                candidate = by_key.get(draft.english.strip().lower())
                if candidate is None or not draft.sentence.strip():
                    continue
                candidate.sentence = draft.sentence.strip()
                candidate.sentence_form = (
                    find_form_in_sentence(
                        candidate.sentence, candidate.headword, draft.form_used.strip()
                    )
                    or draft.form_used.strip()
                )

    rule_based: list[str] = []
    for candidate in items:
        if not candidate.sentence:
            candidate.origin = "regel" if candidate.origin == "excel" else candidate.origin
            ensure_sentence(candidate)
            rule_based.append(candidate.headword)
        elif not candidate.sentence_form:
            candidate.sentence_form = (
                find_form_in_sentence(candidate.sentence, candidate.headword)
                or candidate.headword
            )

    if rule_based:
        if not allow_templates:
            raise ValueError(
                f"Für {len(rule_based)} Wörter konnte kein Beispielsatz erzeugt werden "
                f"({', '.join(rule_based[:6])}{' …' if len(rule_based) > 6 else ''}). "
                "Mustersätze sind abgeschaltet (allow_template_sentences=False), damit "
                "keine blassen Füllsätze in den Unterricht gelangen."
            )
        report.add(
            "satz_regelbasiert",
            Severity.WARNING,
            f"{len(rule_based)} Beispielsätze wurden regelbasiert erzeugt und sind "
            "inhaltlich blass. Für unterrichtsfertige Sätze bitte einen "
            "ANTHROPIC_API_KEY hinterlegen.",
            words=rule_based,
            stage="saetze",
        )


def review_sentences(
    client: LLMClient,
    items: list[Candidate],
    unit_label: str,
    batch_size: int,
    report: QualityReport,
) -> int:
    """Prüft die Sätze und übernimmt Verbesserungen. Gibt die Zahl der Korrekturen zurück."""
    if not client.available or not items:
        return 0

    by_key = {c.headword.lower(): c for c in items}
    fixed = 0
    for batch in _chunks(items, batch_size):
        rows = [(c.headword, c.german, c.sentence) for c in batch]
        result = client.try_structured(
            prompt_check_sentences(rows, unit_label), SentenceVerdictList
        )
        if result is None:
            break
        for verdict in result.verdicts:
            candidate = by_key.get(verdict.english.strip().lower())
            if candidate is None:
                continue
            flawed = not all(
                (
                    verdict.grammatical,
                    verdict.natural,
                    verdict.uses_target_meaning,
                    verdict.level_ok,
                )
            ) or verdict.gives_away_answer
            if not flawed:
                continue
            replacement = verdict.revised_sentence.strip()
            if not replacement:
                report.add(
                    "satz_bemaengelt",
                    Severity.WARNING,
                    f"'{candidate.headword}': {verdict.problem or 'Der Satz wurde bemängelt.'}",
                    words=[candidate.headword],
                    stage="satzpruefung",
                )
                continue
            form = find_form_in_sentence(
                replacement, candidate.headword, verdict.revised_form.strip()
            )
            if not form:
                continue  # Korrektur ohne Zielwort wird nicht übernommen
            candidate.sentence = replacement
            candidate.sentence_form = form
            fixed += 1
            report.add(
                "satz_verbessert",
                Severity.INFO,
                f"'{candidate.headword}': Beispielsatz überarbeitet "
                f"({verdict.problem or 'sprachliche Korrektur'}).",
                words=[candidate.headword],
                stage="satzpruefung",
            )
    return fixed


def repair_sentences(
    client: LLMClient,
    items: list[Candidate],
    unit_label: str,
    report: QualityReport,
    allow_templates: bool = True,
) -> int:
    """Erzeugt für beanstandete Sätze einen neuen Versuch."""
    broken = [c for c in items if check_sentence(c)]
    if not broken:
        return 0
    for candidate in broken:
        candidate.sentence = ""
        candidate.sentence_form = ""
    write_sentences(client, broken, unit_label, len(broken) or 1, report, allow_templates)
    for candidate in broken:
        ensure_sentence(candidate)
    return len(broken)


def final_review(
    client: LLMClient, pair: TestPair, unit_label: str, report: QualityReport
) -> None:
    """Abschliessende Gesamtkontrolle durch das Sprachmodell."""
    if not client.available:
        return
    from .llm import prompt_final_review

    def rows(items: list[TestItem]) -> list[tuple[str, str, str]]:
        return [(i.german, i.english, i.sentence) for i in items]

    result = client.try_structured(
        prompt_final_review(rows(pair.test1), rows(pair.test2), unit_label), FinalReview
    )
    if result is None:
        return

    report.stats["gesamturteil"] = result.summary
    report.stats["unterrichtsreif"] = result.ready_for_class
    for issue in result.issues:
        severity = Severity.ERROR if issue.severity.lower() == "error" else Severity.WARNING
        report.add(
            f"abschluss_{issue.code}", severity, issue.message, words=issue.words,
            stage="abschlusskontrolle",
        )


# ---------------------------------------------------------------------------
# Hauptablauf
# ---------------------------------------------------------------------------


def generate_tests(
    source: str | Path | IO[bytes],
    unit: int,
    settings: Settings | None = None,
    client: LLMClient | None = None,
    progress: Progress | None = None,
) -> PipelineResult:
    """Erzeugt beide Vokabeltests für die gewünschte Unit."""
    settings = settings or Settings()
    client = client if client is not None else LLMClient(settings)
    notify = progress or _noop
    report = QualityReport()

    notify("Excel-Datei wird gelesen …", 0.05)
    workbook = read_workbook(source)
    for warning in workbook.warnings:
        report.add("excel_hinweis", Severity.WARNING, warning, stage="einlesen")

    pool_entries = collect_unit_pool(workbook, unit)
    unit_label = workbook.unit_label(unit)
    report.stats["unit"] = unit_label
    report.stats["eintraege_in_unit"] = len(pool_entries)

    notify(f"{len(pool_entries)} Einträge für {unit_label} werden bewertet …", 0.15)
    context = LevelContext.from_entries(workbook.entries_before(unit))
    candidates = [
        score_candidate(
            Candidate(
                english=entry.english,
                german=entry.german,
                section=entry.section,
                unit=entry.unit,
                oxford3000=entry.oxford3000,
            ),
            context,
        )
        for entry in pool_entries
    ]
    topics = unit_topics(candidates)

    if client.available:
        notify("Wörter werden fachlich beurteilt …", 0.25)
        judge_with_llm(client, candidates, unit_label, topics, report, settings.batch_size)

    usable = [c for c in candidates if is_usable(c) and "modell_abgelehnt" not in c.flags]
    rejected = [c for c in candidates if c not in usable]
    report.stats["geeignet_nach_pruefung"] = len(usable)
    report.stats["aussortiert"] = len(rejected)

    notify("Doppelungen werden entfernt …", 0.35)
    deduped, dropped = deduplicate(usable)
    for loser, winner, why in dropped:
        report.add(
            "doppelung_entfernt",
            Severity.INFO,
            f"'{loser.headword}' entfällt zugunsten von '{winner.headword}' ({why}).",
            words=[loser.headword, winner.headword],
            stage="doppelungen",
        )

    notify("Wörter werden ausgewählt …", 0.45)
    selection = select_words(deduped, fallback=rejected, target=settings.target_total)
    chosen = selection.chosen
    for note in selection.notes:
        report.add("pool_zu_klein", Severity.WARNING, note, stage="auswahl")

    chosen = semantic_dedup_with_llm(client, chosen, unit_label, report)

    if len(chosen) < settings.target_total:
        needed = settings.target_total - len(chosen)
        notify(f"{needed} Ersatzwörter werden gesucht …", 0.55)
        chosen.extend(
            find_replacements(
                client, needed, unit_label, candidates, chosen, context, report
            )
        )

    if len(chosen) < settings.target_total:
        # Letzter Ausweg: Pool erneut lockern, damit immer 60 Einträge entstehen.
        extra = select_words(
            [c for c in deduped + rejected if c not in chosen],
            fallback=rejected,
            target=settings.target_total - len(chosen),
        )
        for candidate in extra.chosen:
            if is_hard_excluded(candidate):
                continue
            if not any(overlap_reason(candidate, other) for other in chosen):
                candidate.flag("aufgefuellt", "Nachgerückt, um 60 Einträge zu erreichen.")
                chosen.append(candidate)

    if len(chosen) < settings.target_total:
        raise ValueError(
            f"{unit_label} liefert nur {len(chosen)} verwendbare Wörter; "
            f"für zwei Tests werden {settings.target_total} benötigt. "
            "Bitte eine Unit mit mehr Vokabular wählen oder die Wortliste ergänzen."
        )

    notify("Tests werden ausbalanciert …", 0.62)
    test1, test2 = split_balanced(chosen, settings.words_per_test, seed=settings.seed)

    notify("Beispielsätze werden geschrieben …", 0.70)
    write_sentences(
        client, test1 + test2, unit_label, settings.batch_size, report,
        settings.allow_template_sentences,
    )

    if client.available:
        notify("Beispielsätze werden geprüft …", 0.80)
        review_sentences(client, test1 + test2, unit_label, settings.batch_size, report)

    notify("Qualitätskontrolle läuft …", 0.88)
    rounds = 0
    for attempt in range(settings.max_repair_rounds):
        rounds = attempt + 1
        check = validate_all(test1, test2, settings.words_per_test)
        sentence_errors = [
            i for i in check.errors
            if i.code in {"satz_fehlt", "zielwort_fehlt", "loesung_verraten", "deutsch_im_satz"}
        ]
        if not sentence_errors:
            break
        repaired = repair_sentences(
            client, test1 + test2, unit_label, report, settings.allow_template_sentences
        )
        if not repaired:
            break

    final = validate_all(test1, test2, settings.words_per_test, report)
    final.rounds = rounds

    pair = TestPair(
        unit=unit,
        unit_label=unit_label,
        test1=[TestItem.from_candidate(i, c) for i, c in enumerate(test1, 1)],
        test2=[TestItem.from_candidate(i, c) for i, c in enumerate(test2, 1)],
        report=final,
    )

    from .docx_writer import check_page_fit

    for name, items in (("Test 1", pair.test1), ("Test 2", pair.test2)):
        fit = check_page_fit(items, settings)
        final.stats["seitenfuellung_test1" if name == "Test 1" else "seitenfuellung_test2"] = round(
            fit.usage, 3
        )
        if not fit.fits:
            final.add(
                "seitenueberlauf",
                Severity.ERROR,
                f"{name} passt nicht auf eine A4-Seite ({fit.usage:.0%} Füllung). "
                "Kürzere Beispielsätze oder eine kleinere Schrift schaffen Platz.",
                stage="layout",
            )

    if client.available:
        notify("Abschliessende Gesamtkontrolle …", 0.95)
        final_review(client, pair, unit_label, final)

    if client.disabled_reason:
        final.add(
            "modell_nicht_verfuegbar",
            Severity.WARNING,
            f"Das Sprachmodell war nicht nutzbar ({client.disabled_reason}). "
            "Auswahl und Sätze entstanden rein regelbasiert.",
            stage="abschluss",
        )

    final.stats["sprachmodell"] = "verwendet" if client.calls else "nicht verwendet"
    final.stats["modellaufrufe"] = client.calls
    notify("Fertig.", 1.0)

    return PipelineResult(
        pair=pair,
        workbook=workbook,
        candidates=candidates,
        llm_used=bool(client.calls),
        llm_calls=client.calls,
    )
