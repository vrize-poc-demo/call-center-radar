import pytest
from fastapi.testclient import TestClient

from app.analysis import parse_model_output
from app.config import Settings
from app.main import create_app


def test_parses_structured_analysis_output() -> None:
    analysis = parse_model_output(
        '{"intent":"Support","mood":"negative","resolution":"unresolved",'
        '"summary":"A summary","manager_brief":"A brief",'
        '"recommended_action":"Follow up","claims":[],"mood_shifts":['
        '{"from_mood":"neutral","to_mood":"negative","reason":"Issue raised",'
        '"transcript_turn_id":"turn-1","quote":"Need help","start_ms":0,'
        '"end_ms":1000}],"model_version":"test-v1"}'
    )

    assert analysis.resolution == "unresolved"
    assert analysis.model_version == "test-v1"
    assert analysis.mood_shifts[0].to_mood == "negative"


def test_rejects_malformed_structured_analysis_output() -> None:
    with pytest.raises(ValueError):
        parse_model_output('{"intent":"Support"}')


def test_analyzes_five_calls_with_evidence_backed_claims(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    call_texts = [
        "I need help with this account issue.",
        "This error is still not working.",
        "Please help me resolve the problem.",
        "I cannot access my service.",
        "There is an issue with my payment.",
    ]

    with TestClient(create_app(settings)) as client:
        for index, text in enumerate(call_texts):
            call_id = client.post(
                "/api/calls",
                data={"agent_name": "Demo Agent", "customer_name": f"Customer {index}"},
                files={"audio": (f"call-{index}.wav", b"audio", "audio/wav")},
            ).json()["call_id"]
            saved = client.put(
                f"/api/calls/{call_id}/transcript",
                json={
                    "turns": [
                        {
                            "speaker": "customer",
                            "start_ms": 0,
                            "end_ms": 1000,
                            "text": text,
                        }
                    ]
                },
            ).json()
            response = client.get(f"/api/calls/{call_id}/analysis")

            assert response.status_code == 200
            claim = response.json()["analysis"]["claims"][0]
            assert claim["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
            assert claim["quote"] == text
            assert claim["start_ms"] == 0
            assert claim["end_ms"] == 1000
            shift = response.json()["analysis"]["mood_shifts"][0]
            assert shift["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
            assert shift["quote"] == text


def test_analysis_is_persisted_refreshed_and_exposed_for_dashboard_triage(tmp_path) -> None:
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
                        "start_ms": 100,
                        "end_ms": 900,
                        "text": "This issue is still not working.",
                    }
                ]
            },
        ).json()

        first = client.get(f"/api/calls/{call_id}/analysis")
        cached = client.get(f"/api/calls/{call_id}/analysis")
        refreshed = client.post(f"/api/calls/{call_id}/analysis")
        priority = client.post(f"/api/calls/{call_id}/priority")
        triage = client.get("/api/dashboard/triage")

    assert first.status_code == 200
    assert cached.status_code == 200
    assert first.json()["analysis"] == cached.json()["analysis"]
    assert first.json()["analysis"]["analysis_version"] == 1
    assert refreshed.status_code == 200
    assert refreshed.json()["analysis"]["analysis_version"] == 2
    assert priority.status_code == 200
    assert triage.status_code == 200
    item = triage.json()["calls"][0]
    assert item["call_id"] == call_id
    assert item["analysis"]["analysis_version"] == 2
    assert item["analysis"]["mood"] == "negative"
    assert item["radar_priority"] == 100
    assert item["risk_level"] == "high"
    assert "quote" not in item["analysis"]
    assert (
        first.json()["analysis"]["claims"][0]["transcript_turn_id"]
        == saved["turns"][0]["transcript_turn_id"]
    )


def test_persists_ordered_mood_shift_evidence(tmp_path) -> None:
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
                        "end_ms": 1000,
                        "text": "This issue is not working.",
                    },
                    {
                        "speaker": "customer",
                        "start_ms": 1200,
                        "end_ms": 2000,
                        "text": "Thank you, it is working now.",
                    },
                ]
            },
        ).json()
        analysis = client.get(f"/api/calls/{call_id}/analysis").json()["analysis"]

    assert analysis["mood"] == "positive"
    assert [(shift["from_mood"], shift["to_mood"]) for shift in analysis["mood_shifts"]] == [
        ("neutral", "negative"),
        ("negative", "positive"),
    ]
    assert (
        analysis["mood_shifts"][1]["transcript_turn_id"] == saved["turns"][1]["transcript_turn_id"]
    )


def test_replacing_a_transcript_invalidates_its_persisted_analysis(tmp_path) -> None:
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
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={"turns": [{"speaker": "customer", "start_ms": 0, "end_ms": 1, "text": "Help"}]},
        )
        client.get(f"/api/calls/{call_id}/analysis")
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {"speaker": "customer", "start_ms": 2, "end_ms": 3, "text": "All resolved"}
                ]
            },
        )

        triage = client.get("/api/dashboard/triage")
        regenerated = client.get(f"/api/calls/{call_id}/analysis")

    assert triage.json() == {"calls": []}
    assert regenerated.json()["analysis"]["claims"][0]["quote"] == "All resolved"
