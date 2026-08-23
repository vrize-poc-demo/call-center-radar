from sqlite3 import Connection

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/calls", tags=["traceability"])

TRACE_SCHEMA_VERSION = "call-trace-v1"
ANALYSIS_RULE_VERSION = "analysis-rules-v1"


class TraceEvent(BaseModel):
    event_id: int
    event_type: str
    status: str
    request_id: str | None
    model_version: str | None
    rule_version: str | None
    validation_result: str | None
    failure_reason: str | None
    created_at: str


class CallTrace(BaseModel):
    call_id: str
    job_id: str
    trace_id: str
    schema_version: str = TRACE_SCHEMA_VERSION
    events: list[TraceEvent]


def record_trace_event(
    connection: Connection,
    *,
    trace_id: str,
    event_type: str,
    event_status: str,
    request_id: str | None = None,
    call_db_id: int | None = None,
    processing_job_db_id: int | None = None,
    model_version: str | None = None,
    rule_version: str | None = None,
    validation_result: str | None = None,
    failure_reason: str | None = None,
) -> None:
    """Persist identifiers and version markers without call content or PII."""
    connection.execute(
        """
        INSERT INTO trace_events (
            trace_id, request_id, call_id, processing_job_id, event_type, status,
            model_version, rule_version, validation_result, failure_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trace_id,
            request_id,
            call_db_id,
            processing_job_db_id,
            event_type,
            event_status,
            model_version,
            rule_version,
            validation_result,
            failure_reason,
        ),
    )


def record_call_trace_event(
    connection: Connection,
    *,
    call_db_id: int,
    event_type: str,
    event_status: str,
    request_id: str | None = None,
    model_version: str | None = None,
    rule_version: str | None = None,
    validation_result: str | None = None,
    failure_reason: str | None = None,
) -> None:
    job = connection.execute(
        """
        SELECT id, trace_id
        FROM processing_jobs
        WHERE call_id = ? AND trace_id IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        (call_db_id,),
    ).fetchone()
    if job is None:
        return
    record_trace_event(
        connection,
        trace_id=job["trace_id"],
        request_id=request_id,
        call_db_id=call_db_id,
        processing_job_db_id=job["id"],
        event_type=event_type,
        event_status=event_status,
        model_version=model_version,
        rule_version=rule_version,
        validation_result=validation_result,
        failure_reason=failure_reason,
    )


def load_call_trace(connection: Connection, call_id: str) -> CallTrace | None:
    job = connection.execute(
        """
        SELECT calls.call_id, processing_jobs.job_id, processing_jobs.trace_id
        FROM calls
        JOIN processing_jobs ON processing_jobs.call_id = calls.id
        WHERE calls.call_id = ? AND processing_jobs.trace_id IS NOT NULL
        ORDER BY processing_jobs.id DESC
        LIMIT 1
        """,
        (call_id,),
    ).fetchone()
    if job is None:
        return None
    rows = connection.execute(
        """
        SELECT id AS event_id, event_type, status, request_id, model_version,
               rule_version, validation_result, failure_reason, created_at
        FROM trace_events
        WHERE trace_id = ?
        ORDER BY id
        """,
        (job["trace_id"],),
    ).fetchall()
    return CallTrace(
        call_id=job["call_id"],
        job_id=job["job_id"],
        trace_id=job["trace_id"],
        events=[TraceEvent(**dict(row)) for row in rows],
    )


@router.get("/{call_id}/trace", response_model=CallTrace)
def get_call_trace(call_id: str, request: Request) -> CallTrace:
    with request.app.state.database.connect() as connection:
        trace = load_call_trace(connection, call_id)
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call trace not found.",
        )
    return trace
