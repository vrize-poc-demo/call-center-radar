import json
import time

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from app.logging import log_event
from app.transcripts import TranscriptTurn

router = APIRouter(prefix="/api/calls", tags=["analysis"])

MODEL_VERSION = "local-demo-structured-v1"


class CallAnalysis(BaseModel):
    intent: str = Field(min_length=1, max_length=160)
    mood: str = Field(pattern="^(positive|neutral|negative|mixed)$")
    resolution: str = Field(pattern="^(resolved|unresolved|unclear)$")
    summary: str = Field(min_length=1, max_length=600)
    manager_brief: str = Field(min_length=1, max_length=400)
    recommended_action: str = Field(min_length=1, max_length=300)
    model_version: str


class AnalysisResponse(BaseModel):
    call_id: str
    analysis: CallAnalysis


def build_prompt(turns: list[TranscriptTurn]) -> str:
    transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in turns)
    return (
        "Return JSON only with intent, mood, resolution, summary, manager_brief, and "
        "recommended_action. Do not create evidence or timestamps.\n\nTranscript:\n" + transcript
    )


def parse_model_output(raw_output: str) -> CallAnalysis:
    payload = json.loads(raw_output)
    return CallAnalysis.model_validate(payload)


def local_demo_model(turns: list[TranscriptTurn]) -> str:
    text = " ".join(turn.text for turn in turns).casefold()
    has_problem = any(term in text for term in ("issue", "error", "help", "problem", "not working"))
    has_unresolved = any(
        term in text for term in ("not resolved", "still not working", "cannot", "can't", "unable")
    )
    resolution = "unresolved" if has_unresolved else "unclear" if has_problem else "resolved"
    mood = "negative" if has_problem else "neutral"
    payload = {
        "intent": "Request support" if has_problem else "General service enquiry",
        "mood": mood,
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
        "model_version": MODEL_VERSION,
    }
    return json.dumps(payload)


@router.get("/{call_id}/analysis", response_model=AnalysisResponse)
def get_analysis(call_id: str, request: Request) -> AnalysisResponse:
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
    except (json.JSONDecodeError, ValidationError):
        log_event(
            request.app.state.logger,
            "analysis_schema_failed",
            "Structured analysis schema failed",
            context={"call_id": call_id, "model_version": MODEL_VERSION},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Analysis output was invalid."
        ) from None
    log_event(
        request.app.state.logger,
        "analysis_generated",
        "Structured call analysis generated",
        context={
            "call_id": call_id,
            "model_version": MODEL_VERSION,
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
        },
    )
    return AnalysisResponse(call_id=call_id, analysis=analysis)
