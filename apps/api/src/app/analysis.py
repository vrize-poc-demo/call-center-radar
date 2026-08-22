import json
import time

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from app.logging import log_event
from app.transcripts import TranscriptTurn
from app.validation import (
    ClaimValidationError,
    EvidenceClaim,
    MoodShift,
    validate_claims,
    validate_mood_shifts,
)

router = APIRouter(prefix="/api/calls", tags=["analysis"])

MODEL_VERSION = "local-demo-structured-v1"


class CallAnalysis(BaseModel):
    intent: str = Field(min_length=1, max_length=160)
    mood: str = Field(pattern="^(positive|neutral|negative|mixed)$")
    resolution: str = Field(pattern="^(resolved|unresolved|unclear)$")
    summary: str = Field(min_length=1, max_length=600)
    manager_brief: str = Field(min_length=1, max_length=400)
    recommended_action: str = Field(min_length=1, max_length=300)
    claims: list[EvidenceClaim]
    mood_shifts: list[MoodShift] = Field(default_factory=list, max_length=6)
    model_version: str
    analysis_version: int = Field(default=0, ge=0)
    analyzed_at: str | None = None


class AnalysisResponse(BaseModel):
    call_id: str
    analysis: CallAnalysis


def build_prompt(turns: list[TranscriptTurn]) -> str:
    transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in turns)
    return (
        "Return JSON only with intent, mood, resolution, summary, manager_brief, "
        "recommended_action, and mood_shifts. Each mood shift must cite one saved transcript "
        "turn exactly. Do not create evidence or timestamps.\n\nTranscript:\n" + transcript
    )


def parse_model_output(raw_output: str) -> CallAnalysis:
    payload = json.loads(raw_output)
    return CallAnalysis.model_validate(payload)


def load_persisted_analysis(connection, call_id: str) -> CallAnalysis | None:
    row = connection.execute(
        """
        SELECT call_analyses.id, call_analyses.intent, call_analyses.mood,
               call_analyses.resolution, call_analyses.summary,
               call_analyses.manager_brief, call_analyses.recommended_action,
               call_analyses.model_version, call_analyses.analysis_version,
               call_analyses.analyzed_at
        FROM call_analyses
        JOIN calls ON calls.id = call_analyses.call_id
        WHERE calls.call_id = ?
        """,
        (call_id,),
    ).fetchone()
    if row is None:
        return None
    claims = connection.execute(
        """
        SELECT call_analysis_claims.claim, call_analysis_claims.transcript_turn_id,
               transcript_turns.text AS quote, call_analysis_claims.start_ms,
               call_analysis_claims.end_ms
        FROM call_analysis_claims
        JOIN transcript_turns
          ON transcript_turns.transcript_turn_id = call_analysis_claims.transcript_turn_id
        WHERE call_analysis_claims.analysis_id = ?
        ORDER BY call_analysis_claims.id
        """,
        (row["id"],),
    ).fetchall()
    mood_shifts = connection.execute(
        """
        SELECT call_analysis_mood_shifts.from_mood, call_analysis_mood_shifts.to_mood,
               call_analysis_mood_shifts.reason,
               call_analysis_mood_shifts.transcript_turn_id,
               transcript_turns.text AS quote, call_analysis_mood_shifts.start_ms,
               call_analysis_mood_shifts.end_ms
        FROM call_analysis_mood_shifts
        JOIN transcript_turns
          ON transcript_turns.transcript_turn_id = call_analysis_mood_shifts.transcript_turn_id
        WHERE call_analysis_mood_shifts.analysis_id = ?
        ORDER BY call_analysis_mood_shifts.start_ms, call_analysis_mood_shifts.id
        """,
        (row["id"],),
    ).fetchall()
    return CallAnalysis(
        **{key: row[key] for key in row.keys() if key != "id"},
        claims=[EvidenceClaim(**dict(claim)) for claim in claims],
        mood_shifts=[MoodShift(**dict(shift)) for shift in mood_shifts],
    )


def persist_analysis(connection, call_db_id: int, analysis: CallAnalysis) -> CallAnalysis:
    """Replace one call's analysis while preserving an increasing refresh version."""
    connection.execute(
        """
        INSERT INTO call_analyses (
            call_id, intent, mood, resolution, summary, manager_brief,
            recommended_action, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(call_id) DO UPDATE SET
            intent = excluded.intent,
            mood = excluded.mood,
            resolution = excluded.resolution,
            summary = excluded.summary,
            manager_brief = excluded.manager_brief,
            recommended_action = excluded.recommended_action,
            model_version = excluded.model_version,
            analysis_version = call_analyses.analysis_version + 1,
            analyzed_at = CURRENT_TIMESTAMP
        """,
        (
            call_db_id,
            analysis.intent,
            analysis.mood,
            analysis.resolution,
            analysis.summary,
            analysis.manager_brief,
            analysis.recommended_action,
            analysis.model_version,
        ),
    )
    analysis_row = connection.execute(
        "SELECT id FROM call_analyses WHERE call_id = ?", (call_db_id,)
    ).fetchone()
    assert analysis_row is not None
    connection.execute(
        "DELETE FROM call_analysis_claims WHERE analysis_id = ?", (analysis_row["id"],)
    )
    for claim in analysis.claims:
        connection.execute(
            """
            INSERT INTO call_analysis_claims (
                analysis_id, claim, transcript_turn_id, start_ms, end_ms
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                analysis_row["id"],
                claim.claim,
                claim.transcript_turn_id,
                claim.start_ms,
                claim.end_ms,
            ),
        )
    connection.execute(
        "DELETE FROM call_analysis_mood_shifts WHERE analysis_id = ?", (analysis_row["id"],)
    )
    for shift in analysis.mood_shifts:
        connection.execute(
            """
            INSERT INTO call_analysis_mood_shifts (
                analysis_id, from_mood, to_mood, reason, transcript_turn_id, start_ms, end_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_row["id"],
                shift.from_mood,
                shift.to_mood,
                shift.reason,
                shift.transcript_turn_id,
                shift.start_ms,
                shift.end_ms,
            ),
        )
    # Resolve the public identifier from the database row before rebuilding response quotes.
    row = connection.execute("SELECT call_id FROM calls WHERE id = ?", (call_db_id,)).fetchone()
    assert row is not None
    persisted = load_persisted_analysis(connection, row["call_id"])
    assert persisted is not None
    return persisted


def local_demo_model(turns: list[TranscriptTurn]) -> str:
    customer_text = " ".join(turn.text for turn in turns if turn.speaker == "customer").casefold()
    has_problem = any(
        term in customer_text
        for term in ("issue", "error", "problem", "not working", "unable", "cannot", "can't")
    )
    has_unresolved = any(
        term in customer_text
        for term in ("not resolved", "still not working", "cannot", "can't", "unable")
    )
    has_confirmed_service_outcome = any(
        turn.speaker == "agent"
        and any(
            phrase in turn.text.casefold()
            for phrase in ("has been sent", "is working now", "has been resolved")
        )
        for turn in turns
    )
    resolution = "unresolved" if has_unresolved else "unclear" if has_problem else "resolved"
    mood_shifts = []
    current_mood = "neutral"
    for turn in turns:
        if turn.speaker != "customer":
            continue
        turn_text = turn.text.casefold()
        next_mood = current_mood
        if any(
            term in turn_text
            for term in (
                "issue",
                "error",
                "problem",
                "not working",
                "unable",
                "cannot",
                "can't",
            )
        ):
            next_mood = "negative"
        elif any(
            term in turn_text
            for term in ("thank", "resolved", "working now", "great", "appreciate")
        ):
            next_mood = "positive"
        if next_mood != current_mood:
            mood_shifts.append(
                {
                    "from_mood": current_mood,
                    "to_mood": next_mood,
                    "reason": "The saved transcript contains a supported mood-change signal.",
                    "transcript_turn_id": turn.transcript_turn_id,
                    "quote": turn.text,
                    "start_ms": turn.start_ms,
                    "end_ms": turn.end_ms,
                }
            )
            current_mood = next_mood
    if current_mood == "neutral" and has_confirmed_service_outcome:
        current_mood = "positive"
    payload = {
        "intent": "Request support" if has_problem else "General service enquiry",
        "mood": current_mood,
        "resolution": resolution,
        "summary": "The caller raised a support request that requires review."
        if has_problem
        else "The call contains a general service conversation.",
        "manager_brief": "Review the support concern and confirm the next owner."
        if has_problem
        else "No immediate escalation is indicated by the local demo model.",
        "recommended_action": "Confirm ownership and follow up with the customer."
        if has_problem
        else "Monitor the call outcome in normal workflow.",
        "claims": [
            {
                "claim": "Customer support concern",
                "transcript_turn_id": turn.transcript_turn_id,
                "quote": turn.text,
                "start_ms": turn.start_ms,
                "end_ms": turn.end_ms,
            }
            for turn in turns[:1]
        ],
        "mood_shifts": mood_shifts,
        "model_version": MODEL_VERSION,
    }
    return json.dumps(payload)


def generate_and_persist_analysis(call_id: str, request: Request) -> CallAnalysis:
    started_at = time.perf_counter()
    with request.app.state.database.connect() as connection:
        call = connection.execute("SELECT id FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
        rows = connection.execute(
            "SELECT transcript_turn_id, speaker, start_ms, end_ms, text "
            "FROM transcript_turns WHERE call_id = ? ORDER BY start_ms, id",
            (call["id"],),
        ).fetchall()
        turns = [TranscriptTurn(**dict(row)) for row in rows]
        try:
            analysis = parse_model_output(local_demo_model(turns))
            analysis.claims = validate_claims(analysis.claims, turns)
            analysis.mood_shifts = validate_mood_shifts(analysis.mood_shifts, turns)
            analysis = persist_analysis(connection, call["id"], analysis)
        except (json.JSONDecodeError, ValidationError, ClaimValidationError) as error:
            failure_reason = (
                str(error) if isinstance(error, ClaimValidationError) else "invalid_model_output"
            )
            log_event(
                request.app.state.logger,
                "analysis_schema_failed",
                "Structured analysis schema failed",
                context={
                    "call_id": call_id,
                    "model_version": MODEL_VERSION,
                    "reason": failure_reason,
                    "rejected_mood_shift_count": int(isinstance(error, ClaimValidationError)),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Analysis output was invalid."
            ) from None
    log_event(
        request.app.state.logger,
        "analysis_persisted",
        "Structured call analysis generated and persisted",
        context={
            "call_id": call_id,
            "model_version": analysis.model_version,
            "analysis_version": analysis.analysis_version,
            "mood_shift_count": len(analysis.mood_shifts),
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
        },
    )
    return analysis


@router.get("/{call_id}/analysis", response_model=AnalysisResponse)
def get_analysis(call_id: str, request: Request) -> AnalysisResponse:
    with request.app.state.database.connect() as connection:
        call = connection.execute("SELECT id FROM calls WHERE call_id = ?", (call_id,)).fetchone()
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
        analysis = load_persisted_analysis(connection, call_id)
    if analysis is None:
        analysis = generate_and_persist_analysis(call_id, request)
    return AnalysisResponse(call_id=call_id, analysis=analysis)


@router.post("/{call_id}/analysis", response_model=AnalysisResponse)
def refresh_analysis(call_id: str, request: Request) -> AnalysisResponse:
    analysis = generate_and_persist_analysis(call_id, request)
    log_event(
        request.app.state.logger,
        "analysis_refreshed",
        "Structured call analysis refreshed",
        context={"call_id": call_id, "analysis_version": analysis.analysis_version},
    )
    return AnalysisResponse(call_id=call_id, analysis=analysis)
