import pytest

from app.transcripts import TranscriptTurn
from app.validation import (
    ClaimValidationError,
    EvidenceClaim,
    MoodShift,
    derive_claim_evidence,
    filter_valid_mood_shifts,
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


def test_derives_claim_quote_and_timing_from_known_turn_id() -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_1", speaker="customer", start_ms=10, end_ms=20, text="Need help"
    )
    claim = EvidenceClaim(
        claim="Support concern",
        transcript_turn_id="turn_1",
        quote="Shortened quote",
        start_ms=1,
        end_ms=2,
    )

    assert derive_claim_evidence([claim], [turn]) == [
        EvidenceClaim(
            claim="Support concern",
            transcript_turn_id="turn_1",
            quote="Need help",
            start_ms=10,
            end_ms=20,
        )
    ]


def test_rejects_claim_with_unknown_turn_id_even_when_deriving_evidence() -> None:
    claim = EvidenceClaim(
        claim="Support concern",
        transcript_turn_id="unknown",
        quote="Anything",
        start_ms=0,
        end_ms=1,
    )

    with pytest.raises(ClaimValidationError, match="unknown_transcript_turn"):
        derive_claim_evidence([claim], [])


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


def test_filters_invalid_optional_mood_shifts_without_relaxing_validation() -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_1",
        speaker="customer",
        start_ms=10,
        end_ms=20,
        text="Need help",
    )
    invalid_shift = MoodShift(
        from_mood="neutral",
        to_mood="negative",
        reason="Unsupported quote.",
        transcript_turn_id="unknown-turn",
        quote="invented",
        start_ms=10,
        end_ms=20,
    )

    accepted, reasons = filter_valid_mood_shifts([invalid_shift], [turn])

    assert accepted == []
    assert reasons == ["unknown_transcript_turn"]


def test_rejects_mood_shifts_that_are_not_in_saved_time_order() -> None:
    late = TranscriptTurn(
        transcript_turn_id="turn_late",
        speaker="customer",
        start_ms=100,
        end_ms=120,
        text="This is now working.",
    )
    early = TranscriptTurn(
        transcript_turn_id="turn_early",
        speaker="customer",
        start_ms=20,
        end_ms=40,
        text="This is not working.",
    )
    shifts = [
        MoodShift(
            from_mood="negative",
            to_mood="positive",
            reason="Late recovery",
            transcript_turn_id=late.transcript_turn_id,
            quote=late.text,
            start_ms=late.start_ms,
            end_ms=late.end_ms,
        ),
        MoodShift(
            from_mood="neutral",
            to_mood="negative",
            reason="Earlier concern",
            transcript_turn_id=early.transcript_turn_id,
            quote=early.text,
            start_ms=early.start_ms,
            end_ms=early.end_ms,
        ),
    ]

    with pytest.raises(ClaimValidationError, match="mood_shifts_not_ordered"):
        validate_mood_shifts(shifts, [early, late])


def test_filter_discards_entire_ambiguous_mood_timeline_when_order_is_invalid() -> None:
    turns = [
        TranscriptTurn(
            transcript_turn_id="turn_1",
            speaker="customer",
            start_ms=10,
            end_ms=20,
            text="First",
        ),
        TranscriptTurn(
            transcript_turn_id="turn_2",
            speaker="customer",
            start_ms=30,
            end_ms=40,
            text="Second",
        ),
    ]
    shifts = [
        MoodShift(
            from_mood="negative",
            to_mood="positive",
            reason="Second event proposed first",
            transcript_turn_id="turn_2",
            quote="model copy is canonicalized",
            start_ms=0,
            end_ms=1,
        ),
        MoodShift(
            from_mood="neutral",
            to_mood="negative",
            reason="First event proposed second",
            transcript_turn_id="turn_1",
            quote="model copy is canonicalized",
            start_ms=0,
            end_ms=1,
        ),
    ]

    accepted, reasons = filter_valid_mood_shifts(shifts, turns)

    assert accepted == []
    assert reasons == ["mood_shifts_not_ordered"]
