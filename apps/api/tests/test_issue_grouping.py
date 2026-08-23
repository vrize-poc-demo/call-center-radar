from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.dashboard import calculate_issue_trend, categorize_intent
from app.main import create_app


def test_groups_known_intents_into_a_small_explainable_taxonomy() -> None:
    assert categorize_intent("Payment refund request") == (
        "billing_and_payments",
        "Billing and payments",
    )
    assert categorize_intent("Account login issue") == ("account_access", "Account access")
    assert categorize_intent("Support request") == ("technical_support", "Technical support")
    assert categorize_intent("Appointment request") == ("service_requests", "Service requests")
    assert categorize_intent("General enquiry") == ("other", "Other")


def test_calculates_explainable_window_trends() -> None:
    assert calculate_issue_trend(1, 0) == "not_enough_data"
    assert calculate_issue_trend(3, 1) == "emerging"
    assert calculate_issue_trend(1, 3) == "declining"
    assert calculate_issue_trend(2, 2) == "stable"


def test_issue_radar_groups_persisted_analyses_and_selects_a_representative_call(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    app = create_app(settings)
    current = datetime.now(UTC).replace(microsecond=0)
    previous = current - timedelta(days=8)

    with TestClient(app) as client:
        with app.state.database.connect() as connection:
            _insert_analysis(connection, "call-current-high", "Support request", current, 90)
            _insert_analysis(connection, "call-current-low", "Support request", current, 10)
            _insert_analysis(connection, "call-previous", "Support request", previous, None)
            _insert_analysis(connection, "call-billing", "Payment refund", current, None)
        response = client.get("/api/dashboard/issues")

    assert response.status_code == 200
    payload = response.json()
    assert payload["grouping_version"] == "issue-grouping-v1"
    assert payload["trend_window_days"] == 7
    support = next(
        category for category in payload["categories"] if category["key"] == "technical_support"
    )
    assert support == {
        "key": "technical_support",
        "label": "Technical support",
        "call_count": 3,
        "current_window_count": 2,
        "previous_window_count": 1,
        "trend": "emerging",
        "representative_call_id": "call-current-high",
        "related_call_ids": ["call-current-high", "call-current-low", "call-previous"],
    }
    billing = next(
        category for category in payload["categories"] if category["key"] == "billing_and_payments"
    )
    assert billing["trend"] == "not_enough_data"


def _insert_analysis(
    connection, call_id: str, intent: str, analyzed_at: datetime, priority: int | None
) -> None:
    call_db_id = connection.execute(
        "INSERT INTO calls (call_id, source_metadata_path) VALUES (?, ?)",
        (call_id, "test-metadata.json"),
    ).lastrowid
    connection.execute(
        """
        INSERT INTO call_analyses (
            call_id, intent, mood, resolution, summary, manager_brief,
            recommended_action, model_version, analyzed_at
        ) VALUES (?, ?, 'neutral', 'unclear', 'Summary', 'Brief', 'Action', 'test-v1', ?)
        """,
        (call_db_id, intent, analyzed_at.isoformat()),
    )
    if priority is not None:
        connection.execute(
            "INSERT INTO radar_priority_scores (call_id, score, scoring_version) VALUES (?, ?, ?)",
            (call_db_id, priority, "test-v1"),
        )
