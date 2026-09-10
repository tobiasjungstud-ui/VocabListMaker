"""Pydantic-Schemata für die strukturierten Antworten des Sprachmodells."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordJudgement(BaseModel):
    """Fachliche Beurteilung eines einzelnen Vokabeleintrags."""

    english: str = Field(description="Das beurteilte englische Stichwort, unverändert.")
    keep: bool = Field(description="True, wenn das Wort für einen B1.2-B2.1-Test taugt.")
    cefr: str = Field(description="Geschätztes Niveau: A1, A2, B1, B2, C1 oder C2.")
    too_easy: bool = Field(description="True, wenn Lernende das Wort längst kennen.")
    too_obscure: bool = Field(description="True, wenn das Wort im Englischen unüblich ist.")
    translation_ok: bool = Field(
        description="True, wenn die deutsche Übersetzung im Kontext der Unit korrekt ist."
    )
    corrected_german: str = Field(
        default="",
        description="Korrigierte deutsche Übersetzung, sonst leerer String.",
    )
    reason: str = Field(default="", description="Kurze Begründung auf Deutsch.")


class WordJudgementList(BaseModel):
    judgements: list[WordJudgement]


class DuplicatePair(BaseModel):
    """Zwei Einträge, die denselben Lerninhalt prüfen."""

    first: str
    second: str
    reason: str = Field(description="Warum die beiden Einträge sich überschneiden.")
    drop: str = Field(description="Welches der beiden Wörter entfallen sollte.")


class DuplicateReport(BaseModel):
    pairs: list[DuplicatePair] = Field(default_factory=list)


class ReplacementWord(BaseModel):
    """Ein thematisch passendes Ersatzwort."""

    english: str = Field(description="Natürliches, gebräuchliches englisches Wort.")
    german: str = Field(description="Deutsche Übersetzung, wie sie im Test steht.")
    cefr: str = Field(description="Niveau, angestrebt B1 oder B2.")
    rationale: str = Field(default="", description="Warum das Wort zum Thema passt.")


class ReplacementList(BaseModel):
    words: list[ReplacementWord]


class SentenceDraft(BaseModel):
    """Beispielsatz zu einem Stichwort."""

    english: str = Field(description="Das Stichwort, zu dem der Satz gehört.")
    sentence: str = Field(description="Ein natürlicher englischer Beispielsatz.")
    form_used: str = Field(
        description=(
            "Die im Satz tatsächlich vorkommende Form des Stichworts, "
            "exakt so geschrieben wie im Satz (für die Fettschrift)."
        )
    )


class SentenceDraftList(BaseModel):
    sentences: list[SentenceDraft]


class SentenceVerdict(BaseModel):
    """Prüfergebnis zu einem Beispielsatz."""

    english: str
    grammatical: bool = Field(description="Ist der Satz grammatikalisch korrekt?")
    natural: bool = Field(description="Klingt der Satz wie natürliches Englisch?")
    uses_target_meaning: bool = Field(
        description="Wird das Stichwort in der geprüften Bedeutung verwendet?"
    )
    gives_away_answer: bool = Field(
        description="Verrät der Satz die deutsche Übersetzung zu offensichtlich?"
    )
    level_ok: bool = Field(description="Ist der Satz auf B1.2-B2.1 verständlich?")
    revised_sentence: str = Field(
        default="", description="Verbesserter Satz, falls nötig, sonst leerer String."
    )
    revised_form: str = Field(
        default="", description="Wortform im verbesserten Satz, sonst leerer String."
    )
    problem: str = Field(default="", description="Kurze Problembeschreibung auf Deutsch.")


class SentenceVerdictList(BaseModel):
    verdicts: list[SentenceVerdict]


class FinalIssue(BaseModel):
    """Befund der abschliessenden Gesamtkontrolle."""

    severity: str = Field(description="'error' oder 'warning'.")
    code: str = Field(description="Kurzer Fehlercode, z. B. 'doppelung'.")
    message: str = Field(description="Beschreibung des Problems auf Deutsch.")
    words: list[str] = Field(default_factory=list)


class FinalReview(BaseModel):
    ready_for_class: bool = Field(
        description="True, wenn beide Listen ohne Nacharbeit einsetzbar sind."
    )
    issues: list[FinalIssue] = Field(default_factory=list)
    summary: str = Field(default="", description="Ein bis zwei Sätze Gesamturteil.")
