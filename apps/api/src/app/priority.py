from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.evidence import EvidenceCandidate, extract_evidence
from app.logging import log_event
from app.transcripts import TranscriptTurn

router = APIRouter(prefix="/api/calls", tags=["priority"])

SCORING_VERSION = "radar-priority-v1"
FACTOR_WEIGHTS = {
    "unresolved_phrase": ("Unresolved customer concern", 60),
    "problem_phrase": ("Customer reported a problem", 40),
}


class PriorityFactor(BaseModel):
    factor_key: str
    label: str
    contribution: int = Field(gt=0, le=100)
    evidence_id: str
    transcript_turn_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


class RadarPriority(BaseModel):
    call_id: str
    score: int = Field(ge=0, le=100)
    scoring_version: str
    factors: list[PriorityFactor]


def calculate_priority(candidates: list[EvidenceCandidate]) -> tuple[int, list[PriorityFactor]]:
    """Apply the published deterministic rules once each, keeping their evidence links."""
    factors: list[PriorityFactor] = []
    for factor_key, (label, contribution) in FACTOR_WEIGHTS.items():
        candidate = next((item for item in candidates if item.rule_id == factor_key), None)
        if candidate is None:
            continue
        factors.append(
            PriorityFactor(
                factor_key=factor_key,
                label=label,
                contribution=contribution,
                evidence_id=candidate.evidence_id,
                transcript_turn_id=candidate.transcript_turn_id,
                start_ms=candidate.start_ms,
                end_ms=candidate.end_ms,
            )
        )
    return min(100, sum(factor.contribution for factor in factors)), factors


def load_turns(connection, call_db_id: int) -> list[TranscriptTurn]:
    rows = connection.execute(
        "SELECT transcript_turn_id, speaker, start_ms, end_ms, text "
        "FROM transcript_turns WHERE call_id = ? ORDER BY start_ms, id",
        (call_db_id,),
    ).fetchall()
    return [TranscriptTurn(**dict(row)) for row in rows]


def persist_priority(
    connection, call_db_id: int, score: int, factors: list[PriorityFactor]
) -> None:
    connection.execute("DELETE FROM radar_priority_scores WHERE call_id = ?", (call_db_id,))
    score_id = connection.execute(
        "INSERT INTO radar_priority_scores (call_id, score, scoring_version) VALUES (?, ?, ?)",
        (call_db_id, score, SCORING_VERSION),
    ).lastrowid
    for factor in factors:
        connection.execute(
            "INSERT INTO radar_priority_factors "
            "(score_id, factor_key, label, contribution, evidence_id, transcript_turn_id, "
            "start_ms, end_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                score_id,
                factor.factor_key,
                factor.label,
                factor.contribution,
                factor.evidence_id,
                factor.transcript_turn_id,
                factor.start_ms,
                factor.end_ms,
            ),
        )


def load_priority(connection, call_id: str) -> RadarPriority | None:
    score_row = connection.execute(
        "SELECT id, score, scoring_version FROM radar_priority_scores WHERE call_id = "
        "(SELECT id FROM calls WHERE call_id = ?)",
        (call_id,),
    ).fetchone()
    if score_row is None:
        return None
    factors = connection.execute(
        "SELECT factor_key, label, contribution, evidence_id, transcript_turn_id, start_ms, end_ms "
        "FROM radar_priority_factors WHERE score_id = ? ORDER BY id",
        (score_row["id"],),
    ).fetchall()
    return RadarPriority(
        call_id=call_id,
        score=score_row["score"],
        scoring_version=score_row["scoring_version"],
        factors=[PriorityFactor(**dict(factor)) for factor in factors],
    )


@router.post("/{call_id}/priority", response_model=RadarPriority)
def calculate_and_persist_priority(call_id: str, request: Request) -> RadarPriority:
    with request.app.state.database.connect() as connection:
        call = connection.execute("SELECT id FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
        candidates = extract_evidence(load_turns(connection, call["id"]))
        score, factors = calculate_priority(candidates)
        persist_priority(connection, call["id"], score, factors)
        priority = load_priority(connection, call_id)

    assert priority is not None
    log_event(
        request.app.state.logger,
        "radar_priority_calculated",
        "Radar Priority score calculated and persisted",
        context={
            "call_id": call_id,
            "score": score,
            "scoring_version": SCORING_VERSION,
            "factor_keys": [factor.factor_key for factor in factors],
        },
    )
    return priority


@router.get("/{call_id}/priority", response_model=RadarPriority)
def get_priority(call_id: str, request: Request) -> RadarPriority:
    with request.app.state.database.connect() as connection:
        call = connection.execute("SELECT id FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
        priority = load_priority(connection, call_id)
    if priority is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Radar Priority has not been calculated for this call.",
        )
    return priority
