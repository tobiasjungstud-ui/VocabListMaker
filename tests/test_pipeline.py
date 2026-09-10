"""Gesamtablauf ohne Sprachmodell sowie die Zusammenarbeit mit einem Modell."""

from __future__ import annotations

import pytest

from vocablistmaker.config import Settings
from vocablistmaker.dedup import find_cross_overlaps, find_internal_overlaps
from vocablistmaker.llm import LLMClient
from vocablistmaker.models import Candidate
from vocablistmaker.pipeline import generate_tests
from vocablistmaker.schemas import SentenceDraft, SentenceDraftList
from vocablistmaker.sentences import check_sentence


@pytest.fixture
def settings() -> Settings:
    return Settings(api_key=None, use_llm=False, words_per_test=30)


@pytest.fixture(scope="module")
def offline_result(wordlist_bytes):
    from io import BytesIO

    return generate_tests(
        BytesIO(wordlist_bytes), 1, Settings(api_key=None, use_llm=False, words_per_test=30)
    )


def test_produces_two_full_tests(offline_result) -> None:
    assert len(offline_result.pair.test1) == 30
    assert len(offline_result.pair.test2) == 30


def test_numbering_starts_at_one_in_both_tests(offline_result) -> None:
    assert [i.number for i in offline_result.pair.test1] == list(range(1, 31))
    assert [i.number for i in offline_result.pair.test2] == list(range(1, 31))


def test_no_word_appears_in_both_tests(offline_result) -> None:
    first = {i.english.lower() for i in offline_result.pair.test1}
    second = {i.english.lower() for i in offline_result.pair.test2}
    assert first & second == set()


def test_no_word_families_span_the_two_tests(offline_result) -> None:
    """recycle/recycling dürfen nicht auf die beiden Tests verteilt werden."""
    first = [Candidate(english=i.english, german=i.german) for i in offline_result.pair.test1]
    second = [Candidate(english=i.english, german=i.german) for i in offline_result.pair.test2]
    assert find_cross_overlaps(first, second) == []


def test_no_duplicates_inside_a_test(offline_result) -> None:
    for items in (offline_result.pair.test1, offline_result.pair.test2):
        candidates = [Candidate(english=i.english, german=i.german) for i in items]
        assert find_internal_overlaps(candidates) == []


def test_beginner_words_never_reach_the_tests(offline_result) -> None:
    words = {i.english.lower() for i in offline_result.pair.all_items}
    assert not (words & {"sun", "star", "house", "dog", "big", "world"})


def test_every_entry_has_a_sentence_containing_its_word(offline_result) -> None:
    for item in offline_result.pair.all_items:
        candidate = Candidate(
            english=item.english, german=item.german,
            headword=item.english, sentence=item.sentence,
            sentence_form=item.sentence_form,
        )
        problems = {i.code for i in check_sentence(candidate)}
        assert "zielwort_fehlt" not in problems, f"{item.english}: {item.sentence}"
        assert "loesung_verraten" not in problems, f"{item.english}: {item.sentence}"


def test_tests_have_comparable_difficulty(offline_result) -> None:
    assert offline_result.pair.report.stats["schwierigkeit_differenz"] <= 0.10


def test_report_has_no_errors(offline_result) -> None:
    assert offline_result.pair.report.errors == []


def test_run_is_reproducible(wordlist_bytes) -> None:
    from io import BytesIO

    config = Settings(api_key=None, use_llm=False, words_per_test=30, seed=42)
    first = generate_tests(BytesIO(wordlist_bytes), 1, config)
    second = generate_tests(BytesIO(wordlist_bytes), 1, config)
    assert [i.english for i in first.pair.test1] == [i.english for i in second.pair.test1]


def test_unknown_unit_is_reported(wordlist_bytes, settings) -> None:
    from io import BytesIO

    with pytest.raises(ValueError, match="Verfügbar"):
        generate_tests(BytesIO(wordlist_bytes), 9, settings)


def test_unit_without_enough_vocabulary_is_reported(wordlist_bytes, settings) -> None:
    from io import BytesIO

    with pytest.raises(ValueError, match="verwendbare Wörter"):
        generate_tests(BytesIO(wordlist_bytes), 2, settings)


class _StubClient(LLMClient):
    """Sprachmodell-Ersatz, der nur Beispielsätze liefert."""

    def __init__(self) -> None:
        super().__init__(Settings(api_key="stub", use_llm=True))
        self.prompts: list[str] = []

    @property
    def available(self) -> bool:
        return True

    def try_structured(self, prompt, schema, *, max_tokens=None, effort=None):
        self.prompts.append(prompt)
        if schema is SentenceDraftList:
            drafts = []
            for line in prompt.splitlines():
                if "  —  " not in line or not line[0].isdigit():
                    continue
                word = line.split(".", 1)[1].split("  —  ")[0].strip()
                drafts.append(
                    SentenceDraft(
                        english=word,
                        sentence=f"Our class looked at {word} during the lesson.",
                        form_used=word,
                    )
                )
            self.calls += 1
            return SentenceDraftList(sentences=drafts)
        return None


def test_llm_sentences_are_used_when_available(wordlist_bytes) -> None:
    from io import BytesIO

    client = _StubClient()
    result = generate_tests(
        BytesIO(wordlist_bytes), 1,
        Settings(api_key="stub", use_llm=True, words_per_test=30),
        client,
    )
    sentences = [i.sentence for i in result.pair.all_items]
    assert any("Our class looked at" in s for s in sentences)
    assert client.calls > 0


def test_pipeline_falls_back_when_model_fails(wordlist_bytes) -> None:
    """Fällt das Modell aus, entstehen trotzdem vollständige Listen."""
    from io import BytesIO

    class _FailingClient(_StubClient):
        def try_structured(self, prompt, schema, *, max_tokens=None, effort=None):
            return None

    result = generate_tests(
        BytesIO(wordlist_bytes), 1,
        Settings(api_key="stub", use_llm=True, words_per_test=30),
        _FailingClient(),
    )
    assert len(result.pair.test1) == 30
    assert all(i.sentence for i in result.pair.all_items)
