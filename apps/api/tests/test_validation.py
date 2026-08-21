import pytest

from app.transcripts import TranscriptTurn
from app.validation import ClaimValidationError, EvidenceClaim, validate_claims


def test_accepts_claim_with_exact_saved_evidence() -> None:
    turn = TranscriptTurn(transcript_turn_id="turn_1", speaker="customer", start_ms=10, end_ms=20, text="Need help")
    claim = EvidenceClaim(claim="Support concern", transcript_turn_id="turn_1", quote="Need help", start_ms=10, end_ms=20)
    assert validate_claims([claim], [turn]) == [claim]


@pytest.mark.parametrize("field,value,reason", [("transcript_turn_id", "unknown", "unknown_transcript_turn"), ("quote", "invented", "quote_not_in_transcript_turn"), ("start_ms", 11, "timestamp_not_derived_from_turn")])
def test_rejects_unsupported_claims(field, value, reason) -> None:
    turn = TranscriptTurn(transcript_turn_id="turn_1", speaker="customer", start_ms=10, end_ms=20, text="Need help")
    payload = {"claim": "Support concern", "transcript_turn_id": "turn_1", "quote": "Need help", "start_ms": 10, "end_ms": 20}
    payload[field] = value
    with pytest.raises(ClaimValidationError, match=reason):
        validate_claims([EvidenceClaim(**payload)], [turn])
