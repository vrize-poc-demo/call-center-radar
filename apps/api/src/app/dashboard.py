import sqlite3
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.logging import log_event

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

ISSUE_GROUPING_VERSION = "issue-grouping-v1"
TREND_WINDOW_DAYS = 7
MINIMUM_TREND_CALLS = 2

IssueTrend = Literal["emerging", "declining", "stable", "not_enough_data"]


class IssueCategory(BaseModel):
    key: str
    label: str
    call_count: int = Field(ge=1)
    current_window_count: int = Field(ge=0)
    previous_window_count: int = Field(ge=0)
    trend: IssueTrend
    representative_call_id: str
    related_call_ids: list[str]


class IssueRadarReadModel(BaseModel):
    grouping_version: str
    trend_window_days: int = Field(ge=1)
    categories: list[IssueCategory]


class TriageAnalysis(BaseModel):
    intent: str
    mood: str
    resolution: str
    summary: str
    manager_brief: str
    recommended_action: str
    model_version: str
    analysis_version: int = Field(ge=1)
    analyzed_at: str
    false_resolution: bool


class TriageCall(BaseModel):
    call_id: str
    created_at: str
    radar_priority: int | None = Field(default=None, ge=0, le=100)
    risk_level: str
    analysis: TriageAnalysis


class TriageReadModel(BaseModel):
    calls: list[TriageCall]


def risk_level(score: int | None) -> str:
    if score is None:
        return "unscored"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def categorize_intent(intent: str) -> tuple[str, str]:
    """Map model intent text into the small, published POC issue taxonomy."""
    normalized = intent.casefold()
    rules = (
        (
            "billing_and_payments",
            "Billing and payments",
            ("billing", "payment", "invoice", "refund", "charge"),
        ),
        ("account_access", "Account access", ("account", "login", "access", "password")),
        (
            "technical_support",
            "Technical support",
            ("technical", "support", "error", "outage", "not working"),
        ),
        (
            "service_requests",
            "Service requests",
            ("service request", "appointment", "delivery", "order"),
        ),
    )
    for key, label, terms in rules:
        if any(term in normalized for term in terms):
            return key, label
    return "other", "Other"


def calculate_issue_trend(current_count: int, previous_count: int) -> IssueTrend:
    """Compare two equal time windows without implying a trend from one call."""
    if current_count + previous_count < MINIMUM_TREND_CALLS:
        return "not_enough_data"
    if current_count > previous_count:
        return "emerging"
    if current_count < previous_count:
        return "declining"
    return "stable"


@router.get("/triage", response_model=TriageReadModel)
def get_triage_read_model(request: Request) -> TriageReadModel:
    """Return persisted, non-transcript dashboard inputs without invoking analysis."""
    try:
        with request.app.state.database.connect() as connection:
            rows = connection.execute(
                """
            SELECT calls.call_id, calls.created_at, radar_priority_scores.score AS radar_priority,
                   call_analyses.intent, call_analyses.mood, call_analyses.resolution,
                   call_analyses.summary,
                   call_analyses.manager_brief, call_analyses.recommended_action,
                   call_analyses.model_version, call_analyses.analysis_version,
                   call_analyses.analyzed_at,
                   false_resolution.analysis_id IS NOT NULL AS false_resolution
            FROM call_analyses
            JOIN calls ON calls.id = call_analyses.call_id
            LEFT JOIN radar_priority_scores ON radar_priority_scores.call_id = calls.id
            LEFT JOIN call_analysis_false_resolution_signals AS false_resolution
              ON false_resolution.analysis_id = call_analyses.id
            ORDER BY call_analyses.analyzed_at DESC, calls.id DESC
                """
            ).fetchall()
    except sqlite3.Error:
        log_event(
            request.app.state.logger,
            "dashboard_triage_load_failed",
            "Dashboard triage data could not be loaded",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard data is temporarily unavailable.",
        ) from None
    result = TriageReadModel(calls=[_to_triage_call(row) for row in rows])
    log_event(
        request.app.state.logger,
        "dashboard_triage_loaded",
        "Dashboard triage data loaded",
        context={"call_count": len(result.calls)},
    )
    return result


@router.get("/issues", response_model=IssueRadarReadModel)
def get_issue_radar_read_model(request: Request) -> IssueRadarReadModel:
    """Group persisted analyses for Issue Radar without reading transcripts or rerunning AI."""
    try:
        with request.app.state.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT calls.call_id, call_analyses.intent,
                       COALESCE(radar_priority_scores.score, 0) AS radar_priority,
                       SUM(CASE
                           WHEN date(call_analyses.analyzed_at) >= date('now', '-6 days')
                           THEN 1 ELSE 0
                       END) OVER (PARTITION BY call_analyses.id) AS current_window_count,
                       SUM(CASE
                           WHEN date(call_analyses.analyzed_at) >= date('now', '-13 days')
                            AND date(call_analyses.analyzed_at) < date('now', '-6 days')
                           THEN 1 ELSE 0
                       END) OVER (PARTITION BY call_analyses.id) AS previous_window_count
                FROM call_analyses
                JOIN calls ON calls.id = call_analyses.call_id
                LEFT JOIN radar_priority_scores ON radar_priority_scores.call_id = calls.id
                ORDER BY radar_priority DESC, call_analyses.analyzed_at DESC, calls.call_id ASC
                """
            ).fetchall()
    except sqlite3.Error:
        log_event(
            request.app.state.logger,
            "issue_radar_load_failed",
            "Issue Radar data could not be loaded",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Issue Radar data is temporarily unavailable.",
        ) from None

    grouped: dict[str, dict] = defaultdict(
        lambda: {"label": "", "call_ids": [], "current": 0, "previous": 0}
    )
    for row in rows:
        category_key, category_label = categorize_intent(row["intent"])
        category = grouped[category_key]
        category["label"] = category_label
        category["call_ids"].append(row["call_id"])
        category["current"] += row["current_window_count"]
        category["previous"] += row["previous_window_count"]

    categories = [
        IssueCategory(
            key=key,
            label=group["label"],
            call_count=len(group["call_ids"]),
            current_window_count=group["current"],
            previous_window_count=group["previous"],
            trend=calculate_issue_trend(group["current"], group["previous"]),
            representative_call_id=group["call_ids"][0],
            related_call_ids=group["call_ids"],
        )
        for key, group in grouped.items()
    ]
    categories.sort(key=lambda category: (-category.call_count, category.label))
    result = IssueRadarReadModel(
        grouping_version=ISSUE_GROUPING_VERSION,
        trend_window_days=TREND_WINDOW_DAYS,
        categories=categories,
    )
    log_event(
        request.app.state.logger,
        "issue_grouping_loaded",
        "Issue categories and trends calculated from persisted analyses",
        context={
            "grouping_version": ISSUE_GROUPING_VERSION,
            "call_count": len(rows),
            "category_count": len(categories),
            "trend_window_days": TREND_WINDOW_DAYS,
            "trends": {category.key: category.trend for category in categories},
        },
    )
    return result


def _to_triage_call(row) -> TriageCall:
    data = dict(row)
    return TriageCall(
        call_id=data["call_id"],
        created_at=data["created_at"],
        radar_priority=data["radar_priority"],
        risk_level=risk_level(data["radar_priority"]),
        analysis=TriageAnalysis(
            intent=data["intent"],
            mood=data["mood"],
            resolution=data["resolution"],
            summary=data["summary"],
            manager_brief=data["manager_brief"],
            recommended_action=data["recommended_action"],
            model_version=data["model_version"],
            analysis_version=data["analysis_version"],
            analyzed_at=data["analyzed_at"],
            false_resolution=bool(data["false_resolution"]),
        ),
    )
