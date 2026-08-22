import pytest

from app.transcripts import TranscriptTurn
from app.validation import (
    ClaimValidationError,
    EvidenceClaim,
    MoodShift,
    validate_claims,
    validate_mood_shifts,
)


def test_accepts_claim_with_exact_saved_evidence() -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_1", speaker="customer", start_ms=10, end_ms=20, text="Need help"
    )
    claim = EvidenceClaim(
        claim="Support concern",
        transcript_turn_id="turn_1",
        quote="Need help",
        start_ms=10,
        end_ms=20,
    )
    assert validate_claims([claim], [turn]) == [claim]


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("transcript_turn_id", "unknown", "unknown_transcript_turn"),
        ("quote", "invented", "quote_not_in_transcript_turn"),
        ("start_ms", 11, "timestamp_not_derived_from_turn"),
    ],
)
def test_rejects_unsupported_claims(field, value, reason) -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_1", speaker="customer", start_ms=10, end_ms=20, text="Need help"
    )
    payload = {
        "claim": "Support concern",
        "transcript_turn_id": "turn_1",
        "quote": "Need help",
        "start_ms": 10,
        "end_ms": 20,
    }
    payload[field] = value
    with pytest.raises(ClaimValidationError, match=reason):
        validate_claims([EvidenceClaim(**payload)], [turn])


def test_validates_ordered_mood_shifts_against_saved_turns() -> None:
    turns = [
        TranscriptTurn(
            transcript_turn_id="turn_1",
            speaker="customer",
            start_ms=10,
            end_ms=20,
            text="I need help",
        ),
        TranscriptTurn(
            transcript_turn_id="turn_2",
            speaker="customer",
            start_ms=30,
            end_ms=40,
            text="Thank you, it is working now",
        ),
    ]
    shifts = [
        MoodShift(
            from_mood="neutral",
            to_mood="negative",
            reason="A problem is reported.",
            transcript_turn_id="turn_1",
            quote="I need help",
            start_ms=10,
            end_ms=20,
        ),
        MoodShift(
            from_mood="negative",
            to_mood="positive",
            reason="The customer confirms success.",
            transcript_turn_id="turn_2",
            quote="Thank you, it is working now",
            start_ms=30,
            end_ms=40,
        ),
    ]

    assert validate_mood_shifts(shifts, turns) == shifts


@pytest.mark.parametrize(
    "payload,reason",
    [
        (
            {
                "from_mood": "negative",
                "to_mood": "negative",
                "reason": "No change.",
                "transcript_turn_id": "turn_1",
                "quote": "Need help",
                "start_ms": 10,
                "end_ms": 20,
            },
            "mood_shift_requires_change",
        ),
        (
            {
                "from_mood": "neutral",
                "to_mood": "negative",
                "reason": "Unsupported quote.",
                "transcript_turn_id": "turn_1",
                "quote": "invented",
                "start_ms": 10,
                "end_ms": 20,
            },
            "quote_not_in_transcript_turn",
        ),
    ],
)
def test_rejects_unsupported_mood_shifts(payload, reason) -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_1",
        speaker="customer",
        start_ms=10,
        end_ms=20,
        text="Need help",
    )

    with pytest.raises(ClaimValidationError, match=reason):
        validate_mood_shifts([MoodShift(**payload)], [turn])
