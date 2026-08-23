import re
from dataclasses import dataclass

from app.transcripts import TranscriptTurn

RULE_ID = "repeated_question_exact_v1"
QUESTION_OPENERS = (
    "what ",
    "when ",
    "where ",
    "why ",
    "who ",
    "how ",
    "can you ",
    "could you ",
    "would you ",
    "do you ",
    "did you ",
    "is it ",
    "are you ",
)


@dataclass(frozen=True)
class RepeatedQuestionDetection:
    speaker: str
    original_turn: TranscriptTurn
    repeated_turn: TranscriptTurn


def _normalized_question(text: str) -> str | None:
    lowered = text.strip().lower()
    if not ("?" in lowered or lowered.startswith(QUESTION_OPENERS)):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    return normalized or None


def detect_repeated_questions(turns: list[TranscriptTurn]) -> list[RepeatedQuestionDetection]:
    """Detect exact repeated information requests by the same known speaker."""
    first_by_speaker_and_question: dict[tuple[str, str], TranscriptTurn] = {}
    detections = []
    for turn in turns:
        if turn.speaker not in {"agent", "customer"}:
            continue
        normalized = _normalized_question(turn.text)
        if normalized is None:
            continue
        key = (turn.speaker, normalized)
        original_turn = first_by_speaker_and_question.get(key)
        if original_turn is None:
            first_by_speaker_and_question[key] = turn
            continue
        detections.append(
            RepeatedQuestionDetection(
                speaker=turn.speaker,
                original_turn=original_turn,
                repeated_turn=turn,
            )
        )
    return detections
