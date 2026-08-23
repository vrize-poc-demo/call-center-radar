from fastapi.testclient import TestClient

from app.config import Settings
from app.dashboard import coaching_note, estimate_call_satisfaction
from app.main import create_app


def test_estimates_satisfaction_from_evidence_without_employee_scoring() -> None:
    assert estimate_call_satisfaction("positive", "resolved", False, 0) == 92
    assert estimate_call_satisfaction("negative", "unresolved", True, 2) == 4


def test_returns_supportive_agent_summary_from_persisted_analysis(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        with app.state.database.connect() as connection:
            _insert_agent_call(
                connection,
                call_id="vipin-hard",
                agent_name="Vipin",
                mood="negative",
                resolution="unresolved",
                priority=90,
                treatment_signals=2,
            )
            _insert_agent_call(
                connection,
                call_id="vipin-stable",
                agent_name="Vipin",
                mood="positive",
                resolution="resolved",
                priority=20,
                treatment_signals=0,
            )
            _insert_agent_call(
                connection,
                call_id="susmitha-stable",
                agent_name="Susmitha",
                mood="neutral",
                resolution="resolved",
                priority=10,
                treatment_signals=0,
            )
        response = client.get("/api/dashboard/agents")

    assert response.status_code == 200
    agents = response.json()["agents"]
    vipin = agents[0]
    assert vipin["agent_name"] == "Vipin"
    assert vipin["calls_handled"] == 2
    assert vipin["difficult_calls"] == 1
    assert vipin["treatment_signal_count"] == 2
    assert vipin["unresolved_count"] == 1
    assert vipin["high_risk_count"] == 1
    assert vipin["estimated_satisfaction"] == 55
    assert vipin["coaching_note"] == (
        "Review difficult interactions supportively and check whether the agent needs backup."
    )
    assert vipin["recent_call_ids"] == ["vipin-stable", "vipin-hard"]
    assert agents[1]["agent_name"] == "Susmitha"
    assert agents[1]["coaching_note"] == "No coaching concern stands out from analyzed evidence."


def test_coaching_note_order_stays_supportive() -> None:
    assert coaching_note(0, 0, 0, 0, 0) == "No analyzed calls yet."
    assert coaching_note(1, 2, 0, 1, 1) == (
        "Coach around resolution confirmation before closing the conversation."
    )


def _insert_agent_call(
    connection,
    *,
    call_id: str,
    agent_name: str,
    mood: str,
    resolution: str,
    priority: int,
    treatment_signals: int,
) -> None:
    call_db_id = connection.execute(
        "INSERT INTO calls (call_id, source_metadata_path, agent_name) VALUES (?, ?, ?)",
        (call_id, "test-metadata.json", agent_name),
    ).lastrowid
    analysis_id = connection.execute(
        """
        INSERT INTO call_analyses (
            call_id, intent, mood, resolution, summary, manager_brief,
            recommended_action, model_version
        ) VALUES (?, 'Support request', ?, ?, 'Summary', 'Brief', 'Action', 'test-v1')
        """,
        (call_db_id, mood, resolution),
    ).lastrowid
    connection.execute(
        "INSERT INTO radar_priority_scores (call_id, score, scoring_version) VALUES (?, ?, ?)",
        (call_db_id, priority, "test-v1"),
    )
    for index in range(treatment_signals):
        connection.execute(
            """
            INSERT INTO call_analysis_treatment_signals (
                analysis_id, rule_id, label, transcript_turn_id
            ) VALUES (?, ?, ?, ?)
            """,
            (
                analysis_id,
                "customer_abusive_language_v1",
                "Abusive language toward agent",
                f"{call_id}-turn-{index}",
            ),
        )
