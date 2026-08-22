from app.repeated_questions import detect_repeated_questions
from app.transcripts import TranscriptTurn


def _turn(turn_id: str, speaker: str, start_ms: int, text: str) -> TranscriptTurn:
    return TranscriptTurn(
        transcript_turn_id=turn_id,
        speaker=speaker,
        start_ms=start_ms,
        end_ms=start_ms + 500,
        text=text,
    )


def test_detects_an_exact_question_repeated_by_the_same_customer() -> None:
    turns = [
        _turn("first", "customer", 1000, "What time is my appointment?"),
        _turn("agent", "agent", 2000, "Let me check that for you."),
        _turn("repeat", "customer", 3000, "What time is my appointment?"),
    ]

    events = detect_repeated_questions(turns)

    assert len(events) == 1
    assert events[0].speaker == "customer"
    assert events[0].original_turn == turns[0]
    assert events[0].repeated_turn == turns[2]


def test_normalizes_case_and_terminal_punctuation_but_not_question_meaning() -> None:
    turns = [
        _turn("first", "agent", 1000, "Could you confirm your address?"),
        _turn("repeat", "agent", 3000, "could you confirm your address"),
        _turn("different", "agent", 5000, "Could you confirm your phone number?"),
    ]

    events = detect_repeated_questions(turns)

    assert [
        (event.original_turn.transcript_turn_id, event.repeated_turn.transcript_turn_id)
        for event in events
    ] == [("first", "repeat")]


def test_does_not_mix_speakers_or_treat_statements_as_questions() -> None:
    turns = [
        _turn("customer", "customer", 1000, "What time is my appointment?"),
        _turn("agent", "agent", 2000, "What time is my appointment?"),
        _turn("statement", "customer", 3000, "My appointment is at four."),
        _turn("unknown", "unknown", 4000, "What time is my appointment?"),
    ]

    assert detect_repeated_questions(turns) == []
