"""Chunks: Satzrahmen mit offener Stelle."""

from __future__ import annotations

import pytest

from vocablistmaker.additions import classify
from vocablistmaker.config import Settings
from vocablistmaker.docx_writer import (
    CHUNK_COLUMN_WIDTHS,
    COLUMN_WIDTHS,
    check_page_fit,
    choose_column_widths,
)
from vocablistmaker.leveling import is_usable, score_candidate
from vocablistmaker.models import Candidate, TestItem
from vocablistmaker.normalize import chunk_body, is_chunk
from vocablistmaker.sentences import check_sentence, find_form_in_sentence

CHUNKS = [
    ("What stood out to me was …", "Was mir besonders aufgefallen ist, …",
     "What stood out to me was the camera work."),
    ("One of the strongest aspects of the film is …", "Eine der grössten Stärken des Films ist …",
     "One of the strongest aspects of the film is its music."),
    ("I’d recommend it to anyone who enjoys …", "Ich würde es allen empfehlen, die … mögen",
     "I’d recommend it to anyone who enjoys quiet dramas."),
]


@pytest.mark.parametrize("english, _german, _sentence", CHUNKS)
def test_chunks_are_recognised(english: str, _german: str, _sentence: str) -> None:
    assert is_chunk(english)
    assert classify(english) == "Chunk"


@pytest.mark.parametrize("english", ["stand up for", "prejudice", "box office"])
def test_ordinary_entries_are_not_chunks(english: str) -> None:
    assert not is_chunk(english)


def test_chunk_body_drops_the_ellipsis() -> None:
    assert chunk_body("What stood out to me was …") == "What stood out to me was"
    assert chunk_body("It is worth watching because ...") == "It is worth watching because"


@pytest.mark.parametrize("english, german, _sentence", CHUNKS)
def test_chunks_survive_the_level_check(english: str, german: str, _sentence: str) -> None:
    """Ein Satzrahmen aus Alltagswörtern darf nicht als 'zu einfach' gelten."""
    assert is_usable(score_candidate(Candidate(english=english, german=german)))


def test_chunk_is_not_treated_as_core_vocabulary() -> None:
    from vocablistmaker.leveling import is_core_vocabulary

    assert not is_core_vocabulary("What stood out to me was …")


@pytest.mark.parametrize("english, german, sentence", CHUNKS)
def test_valid_chunk_sentences_pass(english: str, german: str, sentence: str) -> None:
    candidate = score_candidate(Candidate(english=english, german=german))
    candidate.sentence = sentence
    candidate.sentence_form = find_form_in_sentence(sentence, english)
    assert candidate.sentence_form
    assert check_sentence(candidate) == []


def test_bold_part_is_the_frame_without_ellipsis() -> None:
    form = find_form_in_sentence("What stood out to me was the camera work.", "What stood out to me was …")
    assert form == "What stood out to me was"


@pytest.mark.parametrize(
    "sentence, code",
    [
        ("What stood out to me was.", "chunk_nicht_vervollstaendigt"),
        ("The camera work was excellent here.", "zielwort_fehlt"),
        ("Honestly, what stood out to me was the music.", "chunk_nicht_am_anfang"),
    ],
)
def test_broken_chunk_sentences_are_caught(sentence: str, code: str) -> None:
    candidate = score_candidate(
        Candidate(english="What stood out to me was …", german="Was mir auffiel, …")
    )
    candidate.sentence = sentence
    assert code in {i.code for i in check_sentence(candidate)}


def _items(with_chunks: bool) -> list[TestItem]:
    if with_chunks:
        return [
            TestItem(i, CHUNKS[i % 3][1], CHUNKS[i % 3][0], CHUNKS[i % 3][2], "")
            for i in range(1, 31)
        ]
    return [
        TestItem(i, "Bösewicht", "villain",
                 "The villain is far more interesting than the hero.", "villain")
        for i in range(1, 31)
    ]


def test_lists_without_chunks_keep_the_template_grid() -> None:
    assert choose_column_widths(_items(False), Settings()) == COLUMN_WIDTHS


def test_lists_with_chunks_get_a_wider_grid() -> None:
    assert choose_column_widths(_items(True), Settings()) == CHUNK_COLUMN_WIDTHS
    assert sum(CHUNK_COLUMN_WIDTHS) == sum(COLUMN_WIDTHS)


def test_chunk_lists_still_fit_one_page() -> None:
    """Mit dem schmalen Vorlagenraster liefe eine Chunk-Liste über."""
    assert check_page_fit(_items(True), Settings()).fits
    narrow = Settings(column_widths=COLUMN_WIDTHS)
    assert not check_page_fit(_items(True), narrow).fits


def test_explicit_widths_win() -> None:
    custom = (400, 3000, 3000, 3120)
    assert choose_column_widths(_items(True), Settings(column_widths=custom)) == custom
