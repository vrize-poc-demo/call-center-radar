from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class TriageAnalysis(BaseModel):
    intent: str
    mood: str
    resolution: str
    manager_brief: str
    recommended_action: str
    model_version: str
    analysis_version: int = Field(ge=1)
    analyzed_at: str


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


@router.get("/triage", response_model=TriageReadModel)
def get_triage_read_model(request: Request) -> TriageReadModel:
    """Return persisted, non-transcript dashboard inputs without invoking analysis."""
    with request.app.state.database.connect() as connection:
        rows = connection.execute(
            """
            SELECT calls.call_id, calls.created_at, radar_priority_scores.score AS radar_priority,
                   call_analyses.intent, call_analyses.mood, call_analyses.resolution,
                   call_analyses.manager_brief, call_analyses.recommended_action,
                   call_analyses.model_version, call_analyses.analysis_version,
                   call_analyses.analyzed_at
            FROM call_analyses
            JOIN calls ON calls.id = call_analyses.call_id
            LEFT JOIN radar_priority_scores ON radar_priority_scores.call_id = calls.id
            ORDER BY call_analyses.analyzed_at DESC, calls.id DESC
            """
        ).fetchall()
    return TriageReadModel(calls=[_to_triage_call(row) for row in rows])


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
            manager_brief=data["manager_brief"],
            recommended_action=data["recommended_action"],
            model_version=data["model_version"],
            analysis_version=data["analysis_version"],
            analyzed_at=data["analyzed_at"],
        ),
    )
