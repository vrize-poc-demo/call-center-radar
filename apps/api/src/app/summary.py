MAX_SUMMARY_WORDS = 40


class SummaryValidationError(ValueError):
    def __init__(self, reason: str, word_count: int | None = None) -> None:
        self.reason = reason
        self.word_count = word_count
        super().__init__(reason)


def normalize_summary(value: object) -> str:
    """Normalize whitespace and reject summaries outside the manager-scannable limit."""
    if not isinstance(value, str):
        raise SummaryValidationError("summary_not_text")
    words = value.split()
    word_count = len(words)
    if word_count == 0:
        raise SummaryValidationError("summary_empty", word_count)
    if word_count > MAX_SUMMARY_WORDS:
        raise SummaryValidationError("summary_word_limit_exceeded", word_count)
    return " ".join(words)


def count_summary_words(summary: str) -> int:
    return len(summary.split())
