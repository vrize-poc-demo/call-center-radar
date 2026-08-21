from pydantic import BaseModel, Field

from app.transcripts import TranscriptTurn


class EvidenceClaim(BaseModel):
    claim: str = Field(min_length=1, max_length=300)
    transcript_turn_id: str
    quote: str = Field(min_length=1, max_length=10000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class ClaimValidationError(ValueError):
    pass


def validate_claims(claims: list[EvidenceClaim], turns: list[TranscriptTurn]) -> list[EvidenceClaim]:
    turns_by_id = {turn.transcript_turn_id: turn for turn in turns}
    validated = []
    for claim in claims:
        turn = turns_by_id.get(claim.transcript_turn_id)
        if turn is None:
            raise ClaimValidationError("unknown_transcript_turn")
        if claim.quote != turn.text:
            raise ClaimValidationError("quote_not_in_transcript_turn")
        if claim.start_ms != turn.start_ms or claim.end_ms != turn.end_ms:
            raise ClaimValidationError("timestamp_not_derived_from_turn")
        validated.append(claim)
    return validated
