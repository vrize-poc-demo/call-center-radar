import hashlib

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.logging import log_event
from app.transcripts import TranscriptTurn

router = APIRouter(prefix="/api/calls", tags=["evidence"])

RULES = (
    (
        "unresolved_phrase",
        "Unresolved concern",
        ("not resolved", "still not working", "cannot", "can't", "unable to"),
    ),
    ("problem_phrase", "Problem statement", ("problem", "issue", "error", "failed", "help")),
)


class EvidenceCandidate(BaseModel):
    evidence_id: str
    rule_id: str
    label: str
    transcript_turn_id: str
    start_ms: int
    end_ms: int
    quote: str


class EvidenceResponse(BaseModel):
    call_id: str
    candidates: list[EvidenceCandidate]


def extract_evidence(turns: list[TranscriptTurn]) -> list[EvidenceCandidate]:
    candidates = []
    for turn in turns:
        normalized_text = turn.text.casefold()
        for rule_id, label, phrases in RULES:
            if not any(phrase in normalized_text for phrase in phrases):
                continue
            digest = hashlib.sha256(f"{rule_id}:{turn.transcript_turn_id}".encode()).hexdigest()[
                :16
            ]
            candidates.append(
                EvidenceCandidate(
                    evidence_id=f"evidence_{digest}",
                    rule_id=rule_id,
                    label=label,
                    transcript_turn_id=turn.transcript_turn_id,
                    start_ms=turn.start_ms,
                    end_ms=turn.end_ms,
                    quote=turn.text,
                )
            )
    return candidates


@router.get("/{call_id}/evidence", response_model=EvidenceResponse)
def get_evidence(call_id: str, request: Request) -> EvidenceResponse:
    with request.app.state.database.connect() as connection:
        call = connection.execute("SELECT id FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
        rows = connection.execute(
            "SELECT transcript_turn_id, speaker, start_ms, end_ms, text "
            "FROM transcript_turns WHERE call_id = ? ORDER BY start_ms, id",
            (call["id"],),
        ).fetchall()
    candidates = extract_evidence([TranscriptTurn(**dict(row)) for row in rows])
    for candidate in candidates:
        log_event(
            request.app.state.logger,
            "evidence_rule_hit",
            "Evidence rule matched",
            context={
                "call_id": call_id,
                "rule_id": candidate.rule_id,
                "transcript_turn_id": candidate.transcript_turn_id,
            },
        )
    log_event(
        request.app.state.logger,
        "evidence_extracted",
        "Evidence candidates extracted",
        context={"call_id": call_id, "candidate_count": len(candidates)},
    )
    return EvidenceResponse(call_id=call_id, candidates=candidates)
