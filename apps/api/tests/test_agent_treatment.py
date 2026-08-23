from app.agent_treatment import detect_agent_treatment_signals
from app.transcripts import TranscriptTurn


def _turn(turn_id: str, speaker: str, text: str) -> TranscriptTurn:
    return TranscriptTurn(
        transcript_turn_id=turn_id,
        speaker=speaker,
        start_ms=1000,
        end_ms=2000,
        text=text,
    )


def test_detects_customer_abuse_and_explicit_escalation_with_the_saved_turn() -> None:
    turns = [
        _turn("abuse", "customer", "You are useless."),
        _turn("escalation", "customer", "Let me speak to a supervisor."),
    ]

    detections, suppressed_count = detect_agent_treatment_signals(turns)

    assert [(event.rule_id, event.turn.transcript_turn_id) for event in detections] == [
        ("customer_abusive_language_v1", "abuse"),
        ("customer_escalation_or_frustration_v1", "escalation"),
    ]
    assert suppressed_count == 0


def test_ignores_agent_language_and_counts_unknown_speaker_turns_as_suppressed() -> None:
    detections, suppressed_count = detect_agent_treatment_signals(
        [
            _turn("agent", "agent", "The customer called me incompetent."),
            _turn("unknown", "unknown", "You are useless."),
            _turn("broad", "customer", "The process feels incompetent."),
        ]
    )

    assert detections == []
    assert suppressed_count == 1
