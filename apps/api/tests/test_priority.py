from fastapi.testclient import TestClient

from app.config import Settings
from app.evidence import EvidenceCandidate
from app.main import create_app
from app.priority import SCORING_VERSION, calculate_priority


def test_calculate_priority_applies_each_explainable_factor_once() -> None:
    candidates = [
        EvidenceCandidate(
            evidence_id="evidence-unresolved",
            rule_id="unresolved_phrase",
            label="Unresolved concern",
            transcript_turn_id="turn-1",
            start_ms=100,
            end_ms=200,
            quote="Still not working",
        ),
        EvidenceCandidate(
            evidence_id="evidence-problem-first",
            rule_id="problem_phrase",
            label="Problem statement",
            transcript_turn_id="turn-1",
            start_ms=100,
            end_ms=200,
            quote="Still not working",
        ),
        EvidenceCandidate(
            evidence_id="evidence-problem-second",
            rule_id="problem_phrase",
            label="Problem statement",
            transcript_turn_id="turn-2",
            start_ms=300,
            end_ms=400,
            quote="I need help",
        ),
    ]

    score, factors = calculate_priority(candidates)

    assert score == 100
    assert [factor.factor_key for factor in factors] == ["unresolved_phrase", "problem_phrase"]
    assert factors[1].evidence_id == "evidence-problem-first"


def test_priority_endpoint_persists_factor_evidence_links(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 0,
                        "end_ms": 500,
                        "text": "This issue is still not working.",
                    }
                ]
            },
        ).json()
        calculated = client.post(f"/api/calls/{call_id}/priority")
        stored = client.get(f"/api/calls/{call_id}/priority")

    assert calculated.status_code == 200
    assert stored.status_code == 200
    assert calculated.json() == stored.json()
    assert stored.json()["score"] == 100
    assert stored.json()["scoring_version"] == SCORING_VERSION
    assert (
        stored.json()["factors"][0]["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
    )
    assert stored.json()["factors"][0]["start_ms"] == 0


def test_priority_requires_a_saved_calculation(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        response = client.get(f"/api/calls/{call_id}/priority")

    assert response.status_code == 404
    assert response.json()["detail"] == "Radar Priority has not been calculated for this call."
