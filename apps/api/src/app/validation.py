from pydantic import BaseModel, Field

from app.transcripts import TranscriptTurn

MOOD_VALUES = "^(positive|neutral|negative|mixed)$"


class EvidenceClaim(BaseModel):
    claim: str = Field(min_length=1, max_length=300)
    transcript_turn_id: str
    quote: str = Field(min_length=1, max_length=10000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class ClaimValidationError(ValueError):
    pass


class MoodShift(BaseModel):
    from_mood: str = Field(pattern=MOOD_VALUES)
    to_mood: str = Field(pattern=MOOD_VALUES)
    reason: str = Field(min_length=1, max_length=300)
    transcript_turn_id: str
    quote: str = Field(min_length=1, max_length=10000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class FalseResolutionSignal(BaseModel):
    rule_id: str = Field(min_length=1, max_length=120)
    resolution: EvidenceClaim
    contradiction: EvidenceClaim


def _validate_turn_reference(
    transcript_turn_id: str,
    quote: str,
    start_ms: int,
    end_ms: int,
    turns_by_id: dict[str, TranscriptTurn],
) -> None:
    turn = turns_by_id.get(transcript_turn_id)
    if turn is None:
        raise ClaimValidationError("unknown_transcript_turn")
    if quote != turn.text:
        raise ClaimValidationError("quote_not_in_transcript_turn")
    if start_ms != turn.start_ms or end_ms != turn.end_ms:
        raise ClaimValidationError("timestamp_not_derived_from_turn")


def validate_claims(
    claims: list[EvidenceClaim], turns: list[TranscriptTurn]
) -> list[EvidenceClaim]:
    turns_by_id = {turn.transcript_turn_id: turn for turn in turns}
    validated = []
    for claim in claims:
        _validate_turn_reference(
            claim.transcript_turn_id,
            claim.quote,
            claim.start_ms,
            claim.end_ms,
            turns_by_id,
        )
        validated.append(claim)
    return validated


def validate_mood_shifts(shifts: list[MoodShift], turns: list[TranscriptTurn]) -> list[MoodShift]:
    turns_by_id = {turn.transcript_turn_id: turn for turn in turns}
    validated = []
    previous_start_ms = -1
    for shift in shifts:
        if shift.from_mood == shift.to_mood:
            raise ClaimValidationError("mood_shift_requires_change")
        _validate_turn_reference(
            shift.transcript_turn_id,
            shift.quote,
            shift.start_ms,
            shift.end_ms,
            turns_by_id,
        )
        if shift.start_ms < previous_start_ms:
            raise ClaimValidationError("mood_shifts_not_ordered")
        previous_start_ms = shift.start_ms
        validated.append(shift)
    return validated


def validate_false_resolution(
    signal: FalseResolutionSignal, turns: list[TranscriptTurn]
) -> FalseResolutionSignal:
    turns_by_id = {turn.transcript_turn_id: turn for turn in turns}
    _validate_turn_reference(
        signal.resolution.transcript_turn_id,
        signal.resolution.quote,
        signal.resolution.start_ms,
        signal.resolution.end_ms,
        turns_by_id,
    )
    _validate_turn_reference(
        signal.contradiction.transcript_turn_id,
        signal.contradiction.quote,
        signal.contradiction.start_ms,
        signal.contradiction.end_ms,
        turns_by_id,
    )
    resolution_turn = turns_by_id[signal.resolution.transcript_turn_id]
    contradiction_turn = turns_by_id[signal.contradiction.transcript_turn_id]
    if resolution_turn.speaker != "agent":
        raise ClaimValidationError("false_resolution_requires_agent_statement")
    if contradiction_turn.speaker != "customer":
        raise ClaimValidationError("false_resolution_requires_customer_contradiction")
    if contradiction_turn.start_ms <= resolution_turn.start_ms:
        raise ClaimValidationError("false_resolution_requires_later_contradiction")
    return signal
