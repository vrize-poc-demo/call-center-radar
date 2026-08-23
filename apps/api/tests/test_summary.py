import pytest

from app.summary import (
    MAX_SUMMARY_WORDS,
    SummaryValidationError,
    count_summary_words,
    normalize_summary,
)


def test_normalizes_punctuation_and_whitespace_without_changing_words() -> None:
    summary = normalize_summary("  Card,   replacement\narrives tomorrow.  ")

    assert summary == "Card, replacement arrives tomorrow."
    assert count_summary_words(summary) == 4


@pytest.mark.parametrize("word_count", [1, MAX_SUMMARY_WORDS])
def test_accepts_summary_at_the_word_limit(word_count: int) -> None:
    summary = normalize_summary("word " * word_count)

    assert count_summary_words(summary) == word_count


def test_rejects_a_summary_above_the_word_limit() -> None:
    with pytest.raises(SummaryValidationError, match="summary_word_limit_exceeded") as error:
        normalize_summary("word " * (MAX_SUMMARY_WORDS + 1))

    assert error.value.word_count == MAX_SUMMARY_WORDS + 1


@pytest.mark.parametrize("value,reason", [(" \t\n ", "summary_empty"), (4, "summary_not_text")])
def test_rejects_empty_or_non_text_summaries(value: object, reason: str) -> None:
    with pytest.raises(SummaryValidationError, match=reason):
        normalize_summary(value)
