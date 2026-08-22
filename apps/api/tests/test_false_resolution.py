from app.false_resolution import detect_false_resolution
from app.transcripts import TranscriptTurn
from app.validation import (
    ClaimValidationError,
    EvidenceClaim,
    FalseResolutionSignal,
    validate_false_resolution,
)


def _turn(turn_id: str, speaker: str, start_ms: int, text: str) -> TranscriptTurn:
    return TranscriptTurn(
        transcript_turn_id=turn_id,
        speaker=speaker,
        start_ms=start_ms,
        end_ms=start_ms + 500,
        text=text,
    )


def _claim(turn: TranscriptTurn, claim: str) -> EvidenceClaim:
    return EvidenceClaim(
        claim=claim,
        transcript_turn_id=turn.transcript_turn_id,
        quote=turn.text,
        start_ms=turn.start_ms,
        end_ms=turn.end_ms,
    )


def test_detects_agent_resolution_followed_by_customer_contradiction() -> None:
    turns = [
        _turn("agent-resolution", "agent", 1000, "Your card is fixed now."),
        _turn("customer-contradiction", "customer", 3000, "It still is not working."),
    ]

    detection = detect_false_resolution(turns)

    assert detection.detected is True
    assert detection.resolution_turn == turns[0]
    assert detection.contradiction_turn == turns[1]


def test_suppresses_resolution_without_a_later_customer_contradiction() -> None:
    detection = detect_false_resolution(
        [_turn("agent-resolution", "agent", 1000, "Your card is fixed now.")]
    )

    assert detection.detected is False
    assert detection.suppression_reason == "no_later_customer_contradiction"


def test_does_not_treat_an_agent_promise_or_agent_contradiction_as_evidence() -> None:
    detection = detect_false_resolution(
        [
            _turn("agent-promise", "agent", 1000, "I will resolve this for you."),
            _turn("agent-contradiction", "agent", 3000, "It still is not working."),
        ]
    )

    assert detection.detected is False
    assert detection.suppression_reason is None


def test_rejects_a_false_resolution_signal_with_wrong_speakers() -> None:
    customer_resolution = _turn("customer-resolution", "customer", 1000, "It is fixed now.")
    agent_contradiction = _turn("agent-contradiction", "agent", 3000, "It does not work.")
    signal = FalseResolutionSignal(
        rule_id="test-rule",
        resolution=_claim(customer_resolution, "Agent stated the issue was resolved"),
        contradiction=_claim(agent_contradiction, "Customer later contradicted the resolution"),
    )

    try:
        validate_false_resolution(signal, [customer_resolution, agent_contradiction])
    except ClaimValidationError as error:
        assert str(error) == "false_resolution_requires_agent_statement"
    else:
        raise AssertionError("Unsupported false-resolution signal was accepted")
