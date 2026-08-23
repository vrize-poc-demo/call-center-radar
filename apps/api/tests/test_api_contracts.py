from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_openapi_keeps_trust_sensitive_response_fields_required(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
            upload_dir=tmp_path / "uploads",
        )
    )

    with TestClient(app) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]

    assert set(schemas["CallRegistration"]["required"]) == {
        "call_id",
        "job_id",
        "trace_id",
        "status",
    }
    assert set(schemas["ProcessingStatus"]["required"]) == {
        "job_id",
        "status",
        "audio_channels",
        "failure_reason",
    }
    assert set(schemas["RadarPriority"]["required"]) == {
        "call_id",
        "score",
        "scoring_version",
        "factors",
    }
    assert set(schemas["CallTrace"]["required"]) == {
        "call_id",
        "job_id",
        "trace_id",
        "events",
    }


def test_trace_schema_does_not_expose_call_content_or_participant_fields(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
            upload_dir=tmp_path / "uploads",
        )
    )

    with TestClient(app) as client:
        schemas = client.get("/openapi.json").json()["components"]["schemas"]

    trace_properties = set(schemas["CallTrace"]["properties"])
    event_properties = set(schemas["TraceEvent"]["properties"])
    prohibited_fragments = ("audio", "quote", "text", "transcript", "agent", "customer")

    assert all(
        fragment not in property_name
        for property_name in trace_properties | event_properties
        for fragment in prohibited_fragments
    )
