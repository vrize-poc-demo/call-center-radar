from app.silence_and_balance import (
    calculate_conversation_balance,
    detect_silence_windows,
)
from app.transcripts import TranscriptTurn


def _turn(turn_id: str, speaker: str, start_ms: int, end_ms: int) -> TranscriptTurn:
    return TranscriptTurn(
        transcript_turn_id=turn_id,
        speaker=speaker,
        start_ms=start_ms,
        end_ms=end_ms,
        text=turn_id,
    )


def test_detects_only_silence_windows_of_three_seconds_or_longer() -> None:
    turns = [
        _turn("first", "agent", 0, 1000),
        _turn("short-gap", "customer", 3500, 4000),
        _turn("long-gap", "agent", 7500, 8000),
    ]

    windows = detect_silence_windows(turns)

    actual = [
        (
            window.before_turn.transcript_turn_id,
            window.after_turn.transcript_turn_id,
            window.duration_ms,
        )
        for window in windows
    ]
    assert actual == [("short-gap", "long-gap", 3500)]


def test_ignores_overlapping_speech_when_computing_silence() -> None:
    turns = [
        _turn("agent", "agent", 0, 5000),
        _turn("customer", "customer", 1000, 3000),
        _turn("later", "customer", 7000, 7500),
    ]

    windows = detect_silence_windows(turns)

    assert windows == []


def test_calculates_attributed_talk_balance_without_unknown_speakers() -> None:
    turns = [
        _turn("agent", "agent", 0, 6000),
        _turn("customer", "customer", 1000, 5000),
        _turn("unknown", "unknown", 0, 9000),
    ]

    balance = calculate_conversation_balance(turns)

    assert balance.agent_talk_ms == 6000
    assert balance.customer_talk_ms == 4000
    assert balance.agent_share_pct == 60
    assert balance.customer_share_pct == 40
