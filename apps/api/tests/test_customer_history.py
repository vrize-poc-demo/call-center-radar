from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_customer_history_sequences_exact_name_matches_and_marks_repeated_issues(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "calls.db",
            sample_data_dir=tmp_path / "samples",
            upload_dir=tmp_path / "uploads",
        )
    )
    with TestClient(app) as client:
        with app.state.database.connect() as connection:
            first = _call(connection, "First", " Customer One ", "2026-08-01 09:00:00")
            second = _call(connection, "Second", "customer one", "2026-08-02 09:00:00")
            _analysis(connection, first, "Support request")
            _analysis(connection, second, "Technical error")
        response = client.get("/api/calls/First/customer-history")

    assert response.status_code == 200
    assert [item["call_id"] for item in response.json()["calls"]] == ["First", "Second"]
    assert all(item["issue"]["repeated"] for item in response.json()["calls"])


def _call(connection, call_id, customer_name, created_at):
    return connection.execute(
        "INSERT INTO calls (call_id, source_metadata_path, customer_name, "
        "customer_match_key, created_at) VALUES (?, ?, ?, ?, ?)",
        (call_id, "manual://test", customer_name, "customer one", created_at),
    ).lastrowid


def _analysis(connection, call_id, intent):
    connection.execute(
        "INSERT INTO call_analyses (call_id, intent, mood, resolution, summary, "
        "manager_brief, recommended_action, model_version) VALUES "
        "(?, ?, 'neutral', 'unclear', 'S', 'B', 'A', 'test')",
        (call_id, intent),
    )
