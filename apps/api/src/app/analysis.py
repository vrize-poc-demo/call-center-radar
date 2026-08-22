import json
import time

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError

from app.analysis_provider import AnalysisProviderError
from app.false_resolution import RULE_ID, detect_false_resolution
from app.logging import log_event
from app.repeated_questions import RULE_ID as REPEATED_QUESTION_RULE_ID
from app.repeated_questions import detect_repeated_questions
from app.silence_and_balance import (
    calculate_conversation_balance,
    detect_silence_windows,
)
from app.summary import SummaryValidationError, count_summary_words, normalize_summary
from app.transcripts import TranscriptTurn
from app.validation import (
    ClaimValidationError,
    EvidenceClaim,
    FalseResolutionSignal,
    MoodShift,
    derive_claim_evidence,
    filter_valid_mood_shifts,
    validate_false_resolution,
)

router = APIRouter(prefix="/api/calls", tags=["analysis"])


class AnalysisProposal(BaseModel):
    intent: str = Field(min_length=1, max_length=160)
    mood: str = Field(pattern="^(positive|neutral|negative|mixed)$")
    resolution: str = Field(pattern="^(resolved|unresolved|unclear)$")
    summary: str = Field(min_length=1)
    manager_brief: str = Field(min_length=1, max_length=400)
    recommended_action: str = Field(min_length=1, max_length=300)
    claims: list[EvidenceClaim] = Field(min_length=1, max_length=6)
    mood_shifts: list[MoodShift] = Field(default_factory=list, max_length=6)


class RepeatedQuestionEvent(BaseModel):
    rule_id: str = Field(min_length=1, max_length=120)
    speaker: str = Field(pattern="^(agent|customer)$")
    original: EvidenceClaim
    repeated: EvidenceClaim


class SilenceWindowEvent(BaseModel):
    before: EvidenceClaim
    after: EvidenceClaim
    duration_ms: int = Field(ge=3000)


class ConversationBalance(BaseModel):
    agent_talk_ms: int = Field(ge=0)
    customer_talk_ms: int = Field(ge=0)
    agent_share_pct: float = Field(ge=0, le=100)
    customer_share_pct: float = Field(ge=0, le=100)


class CallAnalysis(AnalysisProposal):
    model_version: str
    analysis_version: int = Field(default=0, ge=0)
    analyzed_at: str | None = None
    false_resolution: FalseResolutionSignal | None = None
    repeated_questions: list[RepeatedQuestionEvent] = Field(default_factory=list, max_length=6)
    silence_windows: list[SilenceWindowEvent] = Field(default_factory=list, max_length=12)
    conversation_balance: ConversationBalance = Field(
        default_factory=lambda: ConversationBalance(
            agent_talk_ms=0,
            customer_talk_ms=0,
            agent_share_pct=0,
            customer_share_pct=0,
        )
    )


class AnalysisResponse(BaseModel):
    call_id: str
    analysis: CallAnalysis


def parse_model_output(raw_output: str, model_version: str) -> CallAnalysis:
    payload = json.loads(raw_output)
    if isinstance(payload, dict) and "summary" in payload:
        payload["summary"] = normalize_summary(payload["summary"])
    proposal = AnalysisProposal.model_validate(payload)
    return CallAnalysis(**proposal.model_dump(), model_version=model_version)


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
    false_resolution_row = connection.execute(
        """
        SELECT signal.rule_id,
               resolution.transcript_turn_id AS resolution_transcript_turn_id,
               resolution.text AS resolution_quote,
               resolution.start_ms AS resolution_start_ms,
               resolution.end_ms AS resolution_end_ms,
               contradiction.transcript_turn_id AS contradiction_transcript_turn_id,
               contradiction.text AS contradiction_quote,
               contradiction.start_ms AS contradiction_start_ms,
               contradiction.end_ms AS contradiction_end_ms
        FROM call_analysis_false_resolution_signals AS signal
        JOIN transcript_turns AS resolution
          ON resolution.transcript_turn_id = signal.resolution_transcript_turn_id
        JOIN transcript_turns AS contradiction
          ON contradiction.transcript_turn_id = signal.contradiction_transcript_turn_id
        WHERE signal.analysis_id = ?
        """,
        (row["id"],),
    ).fetchone()
    false_resolution = None
    if false_resolution_row is not None:
        false_resolution = FalseResolutionSignal(
            rule_id=false_resolution_row["rule_id"],
            resolution=EvidenceClaim(
                claim="Agent stated the issue was resolved",
                transcript_turn_id=false_resolution_row["resolution_transcript_turn_id"],
                quote=false_resolution_row["resolution_quote"],
                start_ms=false_resolution_row["resolution_start_ms"],
                end_ms=false_resolution_row["resolution_end_ms"],
            ),
            contradiction=EvidenceClaim(
                claim="Customer later contradicted the resolution",
                transcript_turn_id=false_resolution_row["contradiction_transcript_turn_id"],
                quote=false_resolution_row["contradiction_quote"],
                start_ms=false_resolution_row["contradiction_start_ms"],
                end_ms=false_resolution_row["contradiction_end_ms"],
            ),
        )
    repeated_question_rows = connection.execute(
        """
        SELECT event.rule_id, event.speaker,
               original.transcript_turn_id AS original_transcript_turn_id,
               original.text AS original_quote, original.start_ms AS original_start_ms,
               original.end_ms AS original_end_ms,
               repeated.transcript_turn_id AS repeated_transcript_turn_id,
               repeated.text AS repeated_quote, repeated.start_ms AS repeated_start_ms,
               repeated.end_ms AS repeated_end_ms
        FROM call_analysis_repeated_question_events AS event
        JOIN transcript_turns AS original
          ON original.transcript_turn_id = event.original_transcript_turn_id
        JOIN transcript_turns AS repeated
          ON repeated.transcript_turn_id = event.repeated_transcript_turn_id
        WHERE event.analysis_id = ?
        ORDER BY repeated.start_ms, event.id
        """,
        (row["id"],),
    ).fetchall()
    repeated_questions = [
        RepeatedQuestionEvent(
            rule_id=event["rule_id"],
            speaker=event["speaker"],
            original=EvidenceClaim(
                claim="Original information request",
                transcript_turn_id=event["original_transcript_turn_id"],
                quote=event["original_quote"],
                start_ms=event["original_start_ms"],
                end_ms=event["original_end_ms"],
            ),
            repeated=EvidenceClaim(
                claim="Repeated information request",
                transcript_turn_id=event["repeated_transcript_turn_id"],
                quote=event["repeated_quote"],
                start_ms=event["repeated_start_ms"],
                end_ms=event["repeated_end_ms"],
            ),
        )
        for event in repeated_question_rows
    ]
    silence_rows = connection.execute(
        """
        SELECT before_turn.transcript_turn_id AS before_transcript_turn_id,
               before_turn.text AS before_quote, before_turn.start_ms AS before_start_ms,
               before_turn.end_ms AS before_end_ms,
               after_turn.transcript_turn_id AS after_transcript_turn_id,
               after_turn.text AS after_quote, after_turn.start_ms AS after_start_ms,
               after_turn.end_ms AS after_end_ms, window.duration_ms
        FROM call_analysis_silence_windows AS window
        JOIN transcript_turns AS before_turn
          ON before_turn.transcript_turn_id = window.before_transcript_turn_id
        JOIN transcript_turns AS after_turn
          ON after_turn.transcript_turn_id = window.after_transcript_turn_id
        WHERE window.analysis_id = ?
        ORDER BY before_turn.end_ms, window.id
        """,
        (row["id"],),
    ).fetchall()
    balance_rows = connection.execute(
        "SELECT speaker, start_ms, end_ms, text, transcript_turn_id FROM transcript_turns "
        "JOIN calls ON calls.id = transcript_turns.call_id WHERE calls.call_id = ? "
        "ORDER BY transcript_turns.start_ms, transcript_turns.id",
        (call_id,),
    ).fetchall()
    balance = calculate_conversation_balance(
        [TranscriptTurn(**dict(balance_row)) for balance_row in balance_rows]
    )
    return CallAnalysis(
        **{key: row[key] for key in row.keys() if key != "id"},
        claims=[EvidenceClaim(**dict(claim)) for claim in claims],
        mood_shifts=[MoodShift(**dict(shift)) for shift in mood_shifts],
        false_resolution=false_resolution,
        repeated_questions=repeated_questions,
        silence_windows=[
            SilenceWindowEvent(
                before=EvidenceClaim(
                    claim="Speech before silence",
                    transcript_turn_id=window["before_transcript_turn_id"],
                    quote=window["before_quote"],
                    start_ms=window["before_start_ms"],
                    end_ms=window["before_end_ms"],
                ),
                after=EvidenceClaim(
                    claim="Speech after silence",
                    transcript_turn_id=window["after_transcript_turn_id"],
                    quote=window["after_quote"],
                    start_ms=window["after_start_ms"],
                    end_ms=window["after_end_ms"],
                ),
                duration_ms=window["duration_ms"],
            )
            for window in silence_rows
        ],
        conversation_balance=ConversationBalance(**balance.__dict__),
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
    connection.execute(
        "DELETE FROM call_analysis_false_resolution_signals WHERE analysis_id = ?",
        (analysis_row["id"],),
    )
    if analysis.false_resolution is not None:
        connection.execute(
            """
            INSERT INTO call_analysis_false_resolution_signals (
                analysis_id, rule_id, resolution_transcript_turn_id,
                contradiction_transcript_turn_id
            ) VALUES (?, ?, ?, ?)
            """,
            (
                analysis_row["id"],
                analysis.false_resolution.rule_id,
                analysis.false_resolution.resolution.transcript_turn_id,
                analysis.false_resolution.contradiction.transcript_turn_id,
            ),
        )
    connection.execute(
        "DELETE FROM call_analysis_repeated_question_events WHERE analysis_id = ?",
        (analysis_row["id"],),
    )
    for event in analysis.repeated_questions:
        connection.execute(
            """
            INSERT INTO call_analysis_repeated_question_events (
                analysis_id, rule_id, speaker, original_transcript_turn_id,
                repeated_transcript_turn_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                analysis_row["id"],
                event.rule_id,
                event.speaker,
                event.original.transcript_turn_id,
                event.repeated.transcript_turn_id,
            ),
        )
    connection.execute(
        "DELETE FROM call_analysis_silence_windows WHERE analysis_id = ?",
        (analysis_row["id"],),
    )
    for window in analysis.silence_windows:
        connection.execute(
            """
            INSERT INTO call_analysis_silence_windows (
                analysis_id, before_transcript_turn_id, after_transcript_turn_id, duration_ms
            ) VALUES (?, ?, ?, ?)
            """,
            (
                analysis_row["id"],
                window.before.transcript_turn_id,
                window.after.transcript_turn_id,
                window.duration_ms,
            ),
        )
    # Resolve the public identifier from the database row before rebuilding response quotes.
    row = connection.execute("SELECT call_id FROM calls WHERE id = ?", (call_db_id,)).fetchone()
    assert row is not None
    persisted = load_persisted_analysis(connection, row["call_id"])
    assert persisted is not None
    return persisted


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
            generated = request.app.state.analysis_provider.generate(turns)
            analysis = parse_model_output(generated.raw_output, generated.model_version)
            analysis.claims = derive_claim_evidence(analysis.claims, turns)
            analysis.mood_shifts, rejected_mood_shift_reasons = filter_valid_mood_shifts(
                analysis.mood_shifts, turns
            )
            if rejected_mood_shift_reasons:
                log_event(
                    request.app.state.logger,
                    "optional_mood_shifts_discarded",
                    "Unsupported optional mood shifts were discarded",
                    context={
                        "call_id": call_id,
                        "rejected_count": len(rejected_mood_shift_reasons),
                        "reasons": sorted(set(rejected_mood_shift_reasons)),
                    },
                )
            detection = detect_false_resolution(turns)
            if detection.detected:
                assert detection.resolution_turn is not None
                assert detection.contradiction_turn is not None
                analysis.false_resolution = validate_false_resolution(
                    FalseResolutionSignal(
                        rule_id=RULE_ID,
                        resolution=EvidenceClaim(
                            claim="Agent stated the issue was resolved",
                            transcript_turn_id=detection.resolution_turn.transcript_turn_id,
                            quote=detection.resolution_turn.text,
                            start_ms=detection.resolution_turn.start_ms,
                            end_ms=detection.resolution_turn.end_ms,
                        ),
                        contradiction=EvidenceClaim(
                            claim="Customer later contradicted the resolution",
                            transcript_turn_id=detection.contradiction_turn.transcript_turn_id,
                            quote=detection.contradiction_turn.text,
                            start_ms=detection.contradiction_turn.start_ms,
                            end_ms=detection.contradiction_turn.end_ms,
                        ),
                    ),
                    turns,
                )
                log_event(
                    request.app.state.logger,
                    "false_resolution_detected",
                    "False-resolution rule found a later customer contradiction",
                    context={
                        "call_id": call_id,
                        "rule_id": RULE_ID,
                        "resolution_turn_id": detection.resolution_turn.transcript_turn_id,
                        "contradiction_turn_id": detection.contradiction_turn.transcript_turn_id,
                    },
                )
            elif detection.suppression_reason is not None:
                log_event(
                    request.app.state.logger,
                    "false_resolution_suppressed",
                    "False-resolution candidate was not strong enough to expose",
                    context={
                        "call_id": call_id,
                        "rule_id": RULE_ID,
                        "reason": detection.suppression_reason,
                    },
                )
            analysis.repeated_questions = [
                RepeatedQuestionEvent(
                    rule_id=REPEATED_QUESTION_RULE_ID,
                    speaker=event.speaker,
                    original=EvidenceClaim(
                        claim="Original information request",
                        transcript_turn_id=event.original_turn.transcript_turn_id,
                        quote=event.original_turn.text,
                        start_ms=event.original_turn.start_ms,
                        end_ms=event.original_turn.end_ms,
                    ),
                    repeated=EvidenceClaim(
                        claim="Repeated information request",
                        transcript_turn_id=event.repeated_turn.transcript_turn_id,
                        quote=event.repeated_turn.text,
                        start_ms=event.repeated_turn.start_ms,
                        end_ms=event.repeated_turn.end_ms,
                    ),
                )
                for event in detect_repeated_questions(turns)
            ]
            if analysis.repeated_questions:
                log_event(
                    request.app.state.logger,
                    "repeated_questions_detected",
                    "Repeated information requests detected",
                    context={
                        "call_id": call_id,
                        "event_count": len(analysis.repeated_questions),
                        "rule_id": REPEATED_QUESTION_RULE_ID,
                    },
                )
            analysis.silence_windows = [
                SilenceWindowEvent(
                    before=EvidenceClaim(
                        claim="Speech before silence",
                        transcript_turn_id=window.before_turn.transcript_turn_id,
                        quote=window.before_turn.text,
                        start_ms=window.before_turn.start_ms,
                        end_ms=window.before_turn.end_ms,
                    ),
                    after=EvidenceClaim(
                        claim="Speech after silence",
                        transcript_turn_id=window.after_turn.transcript_turn_id,
                        quote=window.after_turn.text,
                        start_ms=window.after_turn.start_ms,
                        end_ms=window.after_turn.end_ms,
                    ),
                    duration_ms=window.duration_ms,
                )
                for window in detect_silence_windows(turns)
            ]
            balance = calculate_conversation_balance(turns)
            analysis.conversation_balance = ConversationBalance(**balance.__dict__)
            log_event(
                request.app.state.logger,
                "conversation_timing_calculated",
                "Silence windows and attributed talk balance calculated",
                context={
                    "call_id": call_id,
                    "silence_window_count": len(analysis.silence_windows),
                    "agent_talk_ms": balance.agent_talk_ms,
                    "customer_talk_ms": balance.customer_talk_ms,
                },
            )
            analysis = persist_analysis(connection, call["id"], analysis)
        except AnalysisProviderError as error:
            log_event(
                request.app.state.logger,
                "analysis_provider_failed",
                "Local structured analysis provider failed",
                context={"call_id": call_id, "reason": str(error)},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local analysis model is unavailable. Start Ollama and try again.",
            ) from None
        except (
            json.JSONDecodeError,
            ValidationError,
            ClaimValidationError,
            SummaryValidationError,
        ) as error:
            failure_reason = (
                str(error)
                if isinstance(error, (ClaimValidationError, SummaryValidationError))
                else "invalid_model_output"
            )
            log_event(
                request.app.state.logger,
                "analysis_schema_failed",
                "Structured analysis schema failed",
                context={
                    "call_id": call_id,
                    "model_version": request.app.state.settings.ollama_model,
                    "reason": failure_reason,
                    "summary_word_count": (
                        error.word_count if isinstance(error, SummaryValidationError) else None
                    ),
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
            "summary_word_count": count_summary_words(analysis.summary),
            "mood_shift_count": len(analysis.mood_shifts),
            "false_resolution_detected": analysis.false_resolution is not None,
            "repeated_question_count": len(analysis.repeated_questions),
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
