"""Anbindung an die Claude-API für die inhaltlichen Prüfschritte.

Die Anwendung funktioniert auch ohne API-Schlüssel; dann übernehmen die
regelbasierten Verfahren aus :mod:`leveling`, :mod:`dedup` und
:mod:`sentences` die Arbeit. Mit Schlüssel kommen die sprachlich
anspruchsvollen Schritte hinzu: Niveaubeurteilung, Ersatzwörter,
Beispielsätze und die abschliessende Gesamtkontrolle.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import Settings
from .schemas import (
    DuplicateReport,
    FinalReview,
    ReplacementList,
    SentenceDraftList,
    SentenceVerdictList,
    WordJudgementList,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT = """\
You are an experienced teacher of English as a foreign language at a Swiss \
secondary school. Your learners are German-speaking and work at CEFR level \
B1.2 to B2.1. You are preparing printed vocabulary tests that will be handed \
to the class without further editing, so everything you produce must be \
correct, natural and immediately usable.

Guiding principles:
* A test word must be worth learning at B1.2-B2.1. Reject words the learners \
almost certainly met years ago (sun, star, house, dog, big, go).
* Reject words that are so rare, technical or regional that they have no \
everyday value.
* For German-speaking learners, an English word that is nearly identical to \
its German translation (Protein/Protein, Slogan/Slogan) carries almost no \
learning value.
* German translations must match the meaning the word carries in that \
teaching unit, not merely a dictionary entry.
* Never invent English that native speakers would not say.

Answer only through the requested structured output, in the requested \
language, and keep German explanations short and factual."""


class LLMUnavailable(RuntimeError):
    """Wird ausgelöst, wenn kein Sprachmodell erreichbar ist."""


class LLMClient:
    """Dünne, fehlertolerante Hülle um den Anthropic-Client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._client: Any = None
        self._disabled_reason: str | None = None
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    # -- Verfügbarkeit ----------------------------------------------------
    @property
    def api_key(self) -> str | None:
        return self.settings.api_key or os.environ.get("ANTHROPIC_API_KEY") or None

    @property
    def available(self) -> bool:
        """Ist ein Zugang zum Sprachmodell konfiguriert?

        Ein tatsächlich funktionierender Zugang wird erst beim ersten Aufruf
        bestätigt; schlägt dieser fehl, schaltet :meth:`disable` das Modell ab
        und die Pipeline arbeitet regelbasiert weiter.
        """
        if not self.settings.use_llm or self._disabled_reason:
            return False
        return bool(self.api_key or self._has_ambient_credentials())

    @staticmethod
    def _has_ambient_credentials() -> bool:
        """Zugangsdaten ausserhalb von ``ANTHROPIC_API_KEY`` (Token oder Profil)."""
        if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return True
        from pathlib import Path

        for candidate in (
            Path.home() / ".config" / "anthropic",
            Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "anthropic",
        ):
            try:
                if candidate.is_dir() and any(candidate.iterdir()):
                    return True
            except OSError:  # pragma: no cover - Rechteprobleme
                continue
        return False

    def _ensure_client(self) -> Any:
        if self._client is None:
            import anthropic

            kwargs: dict[str, Any] = {
                "max_retries": self.settings.max_retries,
                "timeout": self.settings.timeout_seconds,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def disable(self, reason: str) -> None:
        """Schaltet das Sprachmodell für den Rest des Laufs ab."""
        if not self._disabled_reason:
            self._disabled_reason = reason
            log.warning("Sprachmodell deaktiviert: %s", reason)

    @property
    def disabled_reason(self) -> str | None:
        return self._disabled_reason

    # -- Kernaufruf -------------------------------------------------------
    def structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        max_tokens: int | None = None,
        effort: str | None = None,
    ) -> T:
        """Ein Aufruf mit garantiert schemakonformer Antwort."""
        import anthropic

        if not self.available:
            raise LLMUnavailable(self._disabled_reason or "Kein API-Schlüssel gesetzt.")

        client = self._ensure_client()
        request: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": max_tokens or self.settings.max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": schema,
            "thinking": {"type": "adaptive"},
        }
        chosen_effort = effort or self.settings.effort
        if chosen_effort:
            request["output_config"] = {"effort": chosen_effort}

        try:
            response = client.messages.parse(**request)
        except anthropic.AuthenticationError as exc:
            self.disable(f"Anmeldung fehlgeschlagen: {exc}")
            raise LLMUnavailable(str(exc)) from exc
        except anthropic.PermissionDeniedError as exc:
            self.disable(f"Kein Zugriff auf das Modell: {exc}")
            raise LLMUnavailable(str(exc)) from exc
        except anthropic.NotFoundError as exc:
            self.disable(f"Modell '{self.settings.model}' nicht gefunden: {exc}")
            raise LLMUnavailable(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMUnavailable(f"Ratenbegrenzung erreicht: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMUnavailable(f"API-Fehler {exc.status_code}: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMUnavailable(f"Verbindung zur API fehlgeschlagen: {exc}") from exc

        if getattr(response, "stop_reason", None) == "refusal":
            raise LLMUnavailable("Die Anfrage wurde vom Modell abgelehnt.")

        self.calls += 1
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.input_tokens += getattr(usage, "input_tokens", 0) or 0
            self.output_tokens += getattr(usage, "output_tokens", 0) or 0

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise LLMUnavailable("Die Antwort enthielt keine auswertbaren Daten.")
        return parsed

    def try_structured(
        self, prompt: str, schema: type[T], *, max_tokens: int | None = None,
        effort: str | None = None,
    ) -> T | None:
        """Wie :meth:`structured`, gibt aber ``None`` statt einer Ausnahme zurück."""
        try:
            return self.structured(prompt, schema, max_tokens=max_tokens, effort=effort)
        except LLMUnavailable as exc:
            log.warning("Sprachmodell-Aufruf übersprungen: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - Netzwerk/SDK-Sonderfälle
            log.warning("Unerwarteter Fehler beim Sprachmodell-Aufruf: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Prompt-Bausteine
# ---------------------------------------------------------------------------


def _word_table(rows: Sequence[tuple[str, str]]) -> str:
    return "\n".join(f"{i}. {en}  —  {de}" for i, (en, de) in enumerate(rows, 1))


def prompt_judge_words(rows: Sequence[tuple[str, str]], unit_label: str, topics: str) -> str:
    return f"""\
Below is the candidate vocabulary for a test on {unit_label}. \
The unit covers these topics: {topics}.

For every entry decide whether it belongs in a vocabulary test for \
German-speaking learners at B1.2-B2.1, and check the German translation \
against the meaning the word has in this unit.

Set `keep` to false when the word is clearly below the level (everyday A1/A2 \
vocabulary), when it is too rare or too technical to be useful, or when it is \
so close to its German translation that nothing is learned. Set `keep` to \
true for words that genuinely widen the learners' vocabulary.

Return exactly one judgement per entry, in the same order, and repeat the \
English word unchanged so the entries can be matched.

Entries:
{_word_table(rows)}"""


def prompt_find_duplicates(rows: Sequence[tuple[str, str]], unit_label: str) -> str:
    return f"""\
Here is the selected vocabulary for the two tests on {unit_label}.

Find pairs that would test the same knowledge twice: synonyms or near-synonyms, \
different forms of the same word, singular/plural variants, or entries whose \
German translations mean effectively the same thing. Only report pairs that a \
teacher would actually consider redundant on one test paper — do not report \
words that merely share a topic.

For each pair, name which of the two should be dropped (the one with the lower \
learning value). Report nothing if there is no genuine redundancy.

Entries:
{_word_table(rows)}"""


def prompt_replacements(
    count: int, unit_label: str, topics: str, avoid: Sequence[str], examples: Sequence[str]
) -> str:
    avoid_list = ", ".join(sorted(set(avoid))) or "—"
    example_list = ", ".join(examples[:25]) or "—"
    return f"""\
A vocabulary test for {unit_label} is {count} words short after unsuitable \
entries were removed. The unit covers: {topics}.

Suggest exactly {count} additional English words or short collocations that:
* fit the topics of this unit and would plausibly appear in teaching material \
for it,
* sit at CEFR B1 to B2 (a real step up from A2, but not obscure),
* are genuinely common in everyday English — no invented or artificial terms,
* are clearly distinct from every word already in use.

Words already in the test (do not repeat these, and avoid synonyms and other \
forms of them): {avoid_list}

For orientation, the unit's own material contains words such as: {example_list}

Give each word a German translation in the style of a school word list \
(for example "Umweltverschmutzung" or "etwas wiederverwerten"). Where a German \
word alone would be ambiguous, add a short clarification in the same style the \
list uses."""


def prompt_sentences(rows: Sequence[tuple[str, str]], unit_label: str) -> str:
    return f"""\
Write one example sentence for each entry of a vocabulary test on {unit_label}.

Requirements for every sentence:
* Grammatically correct, natural English that a native speaker would write.
* Understandable for German-speaking learners at B1.2-B2.1: keep it to roughly \
6-14 words and avoid vocabulary harder than the target word itself.
* The target word must appear in the sentence, used in exactly the meaning \
given by the German translation. Any inflected form is fine \
(acted, takes place, issues, displayed).
* The sentence must NOT give the translation away. Do not define the word, do \
not paraphrase it in the same sentence, and do not add an obvious synonym next \
to it. A learner who does not know the word should be able to guess only from \
a plausible context, not read the answer off the page. Avoid patterns such as \
"A villain is a bad person in a story."
* Keep the content appropriate for a school classroom.

In `form_used`, repeat the exact word form as it appears in your sentence, \
including capitalisation — it will be printed in bold.

Entries:
{_word_table(rows)}"""


def prompt_check_sentences(rows: Sequence[tuple[str, str, str]], unit_label: str) -> str:
    listing = "\n".join(
        f"{i}. {en}  —  {de}\n   Satz: {sent}" for i, (en, de, sent) in enumerate(rows, 1)
    )
    return f"""\
Check the example sentences of a vocabulary test on {unit_label} before it is \
printed for the class.

For each sentence judge whether it is grammatical, natural, uses the target \
word in the meaning given by the German translation, stays within B1.2-B2.1, \
and — importantly — whether it gives the translation away too obviously \
(a definition, a paraphrase, or an adjacent synonym).

If anything is wrong, supply a corrected sentence in `revised_sentence` that \
keeps the same target word and fixes the problem, and put the exact word form \
used in `revised_form`. Leave both empty when the sentence is fine.

Entries:
{listing}"""


def prompt_final_review(test1: Sequence[tuple[str, str, str]], test2: Sequence[tuple[str, str, str]], unit_label: str) -> str:
    def block(title: str, rows: Sequence[tuple[str, str, str]]) -> str:
        body = "\n".join(
            f"{i}. {de} | {en} | {sent}" for i, (de, en, sent) in enumerate(rows, 1)
        )
        return f"{title}\n{body}"

    return f"""\
Final check before printing. Below are the two finished vocabulary tests for \
{unit_label}, each with 30 entries in the columns German | English | example \
sentence.

Judge them as a teacher would judge material about to be handed to a class:
* Does any word appear in both tests, or do the two tests test the same thing \
twice (synonyms, word families, singular/plural)?
* Is any German translation wrong or misleading for the meaning tested?
* Is any word clearly too easy for B1.2-B2.1, or artificially rare?
* Does any example sentence contain a language error, sound unnatural, or give \
the answer away?
* Are the two tests of comparable difficulty overall?

Report only genuine problems that would require the teacher to intervene. \
Use severity "error" for anything that must be fixed before printing and \
"warning" for minor remarks. Set `ready_for_class` to true only if you would \
hand out these lists unchanged.

{block("TEST 1", test1)}

{block("TEST 2", test2)}"""


__all__ = [
    "LLMClient",
    "LLMUnavailable",
    "SYSTEM_PROMPT",
    "DuplicateReport",
    "FinalReview",
    "ReplacementList",
    "SentenceDraftList",
    "SentenceVerdictList",
    "WordJudgementList",
    "prompt_judge_words",
    "prompt_find_duplicates",
    "prompt_replacements",
    "prompt_sentences",
    "prompt_check_sentences",
    "prompt_final_review",
]
