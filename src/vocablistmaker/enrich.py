"""Ersatzwörter beschaffen, wenn der geprüfte Pool zu klein ist.

Aussortierte Wörter werden nicht einfach gestrichen: Die Anwendung sucht
thematisch passende, anspruchsvollere Begriffe auf B1.2-B2.1-Niveau, damit die
Liste am Ende wieder 60 sinnvolle Einträge enthält.
"""

from __future__ import annotations

import logging
from collections import Counter

from .dedup import overlap_reason
from .leveling import LevelContext, is_usable, score_candidate
from .llm import LLMClient, ReplacementList, prompt_replacements
from .models import Candidate, QualityReport, Severity

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def unit_topics(pool: list[Candidate], limit: int = 12) -> str:
    """Beschreibt die Themen der Unit anhand ihrer auffälligsten Wörter."""
    if not pool:
        return "allgemeiner Wortschatz"
    ranked = sorted(pool, key=lambda c: (-c.learning_value, -c.difficulty))
    words = []
    for c in ranked:
        hw = (c.headword or c.english).strip()
        if hw and hw.lower() not in {w.lower() for w in words}:
            words.append(hw)
        if len(words) >= limit:
            break
    sections = [s for s, _ in Counter(c.section for c in pool if c.section).most_common(3)]
    topic_hint = "; ".join(sections)
    return f"{', '.join(words)}" + (f" (Abschnitte: {topic_hint})" if topic_hint else "")


def find_replacements(
    client: LLMClient,
    needed: int,
    unit_label: str,
    pool: list[Candidate],
    chosen: list[Candidate],
    ctx: LevelContext,
    report: QualityReport,
) -> list[Candidate]:
    """Besorgt ``needed`` zusätzliche, geprüfte Ersatzwörter."""
    if needed <= 0:
        return []
    if not client.available:
        report.add(
            "ersatz_nicht_moeglich",
            Severity.WARNING,
            f"{needed} Ersatzwörter wären nötig, aber es ist kein Sprachmodell "
            "konfiguriert. Die Liste wurde aus dem vorhandenen Material aufgefüllt.",
            stage="enrich",
        )
        return []

    topics = unit_topics(pool)
    examples = [c.headword or c.english for c in pool[:25]]
    accepted: list[Candidate] = []

    for attempt in range(MAX_ATTEMPTS):
        outstanding = needed - len(accepted)
        if outstanding <= 0:
            break
        avoid = [c.headword or c.english for c in chosen + accepted]
        result = client.try_structured(
            prompt_replacements(outstanding + 4, unit_label, topics, avoid, examples),
            ReplacementList,
        )
        if result is None:
            break

        for word in result.words:
            if len(accepted) >= needed:
                break
            candidate = Candidate(
                english=word.english.strip(),
                german=word.german.strip(),
                section=f"Ergänzung ({unit_label})",
                origin="llm",
            )
            if not candidate.english or not candidate.german:
                continue
            score_candidate(candidate, ctx)
            candidate.notes.append(word.rationale or "Vom Sprachmodell ergänzt.")

            # Ersatzwörter durchlaufen dieselben Prüfungen wie das Originalmaterial.
            if not is_usable(candidate):
                log.info("Ersatzwort verworfen (%s): %s", candidate.flags, candidate.english)
                continue
            if any(overlap_reason(candidate, other) for other in chosen + accepted):
                continue
            candidate.replaces = "Pool zu klein"
            accepted.append(candidate)

        if attempt and not accepted:
            break

    if accepted:
        report.add(
            "ersatzwoerter",
            Severity.INFO,
            f"{len(accepted)} passende Ersatzwörter wurden ergänzt, weil zu viele "
            "Originaleinträge zu einfach oder doppelt waren.",
            words=[c.headword for c in accepted],
            stage="enrich",
        )
    if len(accepted) < needed:
        report.add(
            "ersatz_unvollstaendig",
            Severity.WARNING,
            f"Es konnten nur {len(accepted)} von {needed} Ersatzwörtern gefunden werden.",
            stage="enrich",
        )
    return accepted
