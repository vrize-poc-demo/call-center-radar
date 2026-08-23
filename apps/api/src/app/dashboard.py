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


class AgentSummary(BaseModel):
    agent_name: str
    calls_handled: int = Field(ge=0)
    difficult_calls: int = Field(ge=0)
    estimated_satisfaction: int = Field(ge=0, le=100)
    average_handle_time_ms: int | None = Field(default=None, ge=0)
    calls_with_handle_time: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    resolved_rate: int = Field(ge=0, le=100)
    average_priority: int | None = Field(default=None, ge=0, le=100)
    treatment_signal_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    false_resolution_count: int = Field(ge=0)
    high_risk_count: int = Field(ge=0)
    coaching_note: str
    recent_call_ids: list[str]


class AgentSummaryReadModel(BaseModel):
    agents: list[AgentSummary]


def risk_level(score: int | None) -> str:
    if score is None:
        return "unscored"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def estimate_call_satisfaction(
    mood: str,
    resolution: str,
    false_resolution: bool,
    treatment_signal_count: int,
) -> int:
    """Estimate satisfaction from already persisted, explainable call outcomes."""
    score = {"positive": 82, "neutral": 68, "mixed": 55, "negative": 42}.get(mood, 55)
    if resolution == "resolved":
        score += 10
    elif resolution == "unresolved":
        score -= 12
    if false_resolution:
        score -= 14
    if treatment_signal_count:
        score -= min(12, treatment_signal_count * 6)
    return max(0, min(100, score))


def coaching_note(
    difficult_calls: int,
    calls_handled: int,
    treatment_signal_count: int,
    false_resolution_count: int,
    unresolved_count: int,
) -> str:
    if calls_handled == 0:
        return "No analyzed calls yet."
    if treatment_signal_count:
        return (
            "Review difficult interactions supportively and check whether the agent needs backup."
        )
    if false_resolution_count:
        return "Coach around resolution confirmation before closing the conversation."
    if unresolved_count:
        return "Review follow-up paths for unresolved customer needs."
    if difficult_calls:
        return "Monitor the difficult-call mix and look for repeatable support moments."
    return "No coaching concern stands out from analyzed evidence."


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


@router.get("/agents", response_model=AgentSummaryReadModel)
def get_agent_summary_read_model(request: Request) -> AgentSummaryReadModel:
    """Summarize agent-level patterns without reading transcripts or scoring employees."""
    try:
        with request.app.state.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT calls.call_id, COALESCE(NULLIF(calls.agent_name, ''), 'Unknown agent')
                       AS agent_name,
                       COALESCE(radar_priority_scores.score, 0) AS radar_priority,
                       call_analyses.mood, call_analyses.resolution,
                       call_analyses.analyzed_at,
                       false_resolution.analysis_id IS NOT NULL AS false_resolution,
                       COUNT(treatment_signals.id) AS treatment_signal_count,
                       CASE
                         WHEN calls.started_at_ms IS NOT NULL
                          AND calls.ended_at_ms IS NOT NULL
                          AND calls.ended_at_ms >= calls.started_at_ms
                         THEN calls.ended_at_ms - calls.started_at_ms
                         ELSE transcript_duration.handle_time_ms
                       END AS handle_time_ms
                FROM call_analyses
                JOIN calls ON calls.id = call_analyses.call_id
                LEFT JOIN radar_priority_scores ON radar_priority_scores.call_id = calls.id
                LEFT JOIN call_analysis_false_resolution_signals AS false_resolution
                  ON false_resolution.analysis_id = call_analyses.id
                LEFT JOIN call_analysis_treatment_signals AS treatment_signals
                  ON treatment_signals.analysis_id = call_analyses.id
                LEFT JOIN (
                  SELECT call_id, MAX(end_ms) AS handle_time_ms
                  FROM transcript_turns
                  GROUP BY call_id
                ) AS transcript_duration ON transcript_duration.call_id = calls.id
                GROUP BY call_analyses.id
                ORDER BY call_analyses.analyzed_at DESC, calls.id DESC
                """
            ).fetchall()
    except sqlite3.Error:
        log_event(
            request.app.state.logger,
            "agent_summary_load_failed",
            "Agent summary data could not be loaded",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent summary data is temporarily unavailable.",
        ) from None

    grouped: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "difficult": 0,
            "satisfaction": [],
            "handle_times": [],
            "resolved": 0,
            "priority_scores": [],
            "treatment": 0,
            "unresolved": 0,
            "false_resolution": 0,
            "high_risk": 0,
            "recent": [],
        }
    )
    for row in rows:
        group = grouped[row["agent_name"]]
        treatment_count = row["treatment_signal_count"]
        false_resolution = bool(row["false_resolution"])
        high_risk = row["radar_priority"] >= 60
        unresolved = row["resolution"] == "unresolved"
        resolved = row["resolution"] == "resolved"
        difficult = high_risk or unresolved or false_resolution or treatment_count > 0
        group["calls"] += 1
        group["difficult"] += int(difficult)
        group["treatment"] += treatment_count
        group["unresolved"] += int(unresolved)
        group["resolved"] += int(resolved)
        group["false_resolution"] += int(false_resolution)
        group["high_risk"] += int(high_risk)
        group["priority_scores"].append(row["radar_priority"])
        if row["handle_time_ms"] is not None:
            group["handle_times"].append(row["handle_time_ms"])
        group["satisfaction"].append(
            estimate_call_satisfaction(
                row["mood"],
                row["resolution"],
                false_resolution,
                treatment_count,
            )
        )
        if len(group["recent"]) < 3:
            group["recent"].append(row["call_id"])

    agents = [
        AgentSummary(
            agent_name=agent_name,
            calls_handled=group["calls"],
            difficult_calls=group["difficult"],
            estimated_satisfaction=round(sum(group["satisfaction"]) / len(group["satisfaction"])),
            average_handle_time_ms=(
                round(sum(group["handle_times"]) / len(group["handle_times"]))
                if group["handle_times"]
                else None
            ),
            calls_with_handle_time=len(group["handle_times"]),
            resolved_count=group["resolved"],
            resolved_rate=round(group["resolved"] / group["calls"] * 100),
            average_priority=round(sum(group["priority_scores"]) / len(group["priority_scores"])),
            treatment_signal_count=group["treatment"],
            unresolved_count=group["unresolved"],
            false_resolution_count=group["false_resolution"],
            high_risk_count=group["high_risk"],
            coaching_note=coaching_note(
                group["difficult"],
                group["calls"],
                group["treatment"],
                group["false_resolution"],
                group["unresolved"],
            ),
            recent_call_ids=group["recent"],
        )
        for agent_name, group in grouped.items()
    ]
    agents.sort(key=lambda agent: (-agent.difficult_calls, -agent.calls_handled, agent.agent_name))
    log_event(
        request.app.state.logger,
        "agent_summary_loaded",
        "Agent summary data loaded",
        context={
            "agent_count": len(agents),
            "call_count": len(rows),
            "difficult_call_count": sum(agent.difficult_calls for agent in agents),
        },
    )
    return AgentSummaryReadModel(agents=agents)


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
