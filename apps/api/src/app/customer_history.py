import sqlite3

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.dashboard import categorize_intent
from app.logging import log_event

router = APIRouter(prefix="/api/calls", tags=["customer-history"])


class HistoryIssue(BaseModel):
    key: str
    label: str
    repeated: bool


class CustomerHistoryCall(BaseModel):
    call_id: str
    created_at: str
    processing_status: str | None
    analysis_status: str
    mood: str | None
    resolution: str | None
    issue: HistoryIssue | None


class CustomerHistory(BaseModel):
    focal_call_id: str
    call_count: int = Field(ge=1)
    calls: list[CustomerHistoryCall]


def customer_match_key(customer_name: str) -> str:
    """Use an exact, case-insensitive POC key; never fuzzy-match people."""
    return " ".join(customer_name.split()).casefold()


@router.get("/{call_id}/customer-history", response_model=CustomerHistory)
def get_customer_history(call_id: str, request: Request) -> CustomerHistory:
    try:
        with request.app.state.database.connect() as connection:
            focal = connection.execute(
                "SELECT customer_match_key FROM calls WHERE call_id = ?", (call_id,)
            ).fetchone()
            if focal is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found.")
            if not focal["customer_match_key"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Customer history is unavailable for this call.",
                )
            rows = connection.execute(
                """
                SELECT calls.call_id, calls.created_at,
                       (SELECT processing_jobs.status FROM processing_jobs
                        WHERE processing_jobs.call_id = calls.id
                        ORDER BY processing_jobs.id DESC LIMIT 1) AS processing_status,
                       call_analyses.intent, call_analyses.mood, call_analyses.resolution
                FROM calls
                LEFT JOIN call_analyses ON call_analyses.call_id = calls.id
                WHERE calls.customer_match_key = ?
                ORDER BY calls.created_at ASC, calls.id ASC
                """,
                (focal["customer_match_key"],),
            ).fetchall()
    except sqlite3.Error:
        log_event(
            request.app.state.logger,
            "customer_history_load_failed",
            "Customer history could not be loaded",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Customer history is temporarily unavailable.",
        ) from None

    issue_keys = [categorize_intent(row["intent"])[0] for row in rows if row["intent"]]
    repeated_keys = {key for key in issue_keys if issue_keys.count(key) > 1}
    calls = []
    for row in rows:
        issue = None
        if row["intent"]:
            key, label = categorize_intent(row["intent"])
            issue = HistoryIssue(key=key, label=label, repeated=key in repeated_keys)
        calls.append(
            CustomerHistoryCall(
                call_id=row["call_id"],
                created_at=row["created_at"],
                processing_status=row["processing_status"],
                analysis_status="analyzed" if row["intent"] else "not_analyzed",
                mood=row["mood"],
                resolution=row["resolution"],
                issue=issue,
            )
        )
    result = CustomerHistory(focal_call_id=call_id, call_count=len(calls), calls=calls)
    log_event(
        request.app.state.logger,
        "customer_history_loaded",
        "Customer history assembled",
        context={"focal_call_id": call_id, "call_count": result.call_count},
    )
    return result
