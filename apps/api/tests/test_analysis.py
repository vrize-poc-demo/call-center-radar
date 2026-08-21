import pytest
from fastapi.testclient import TestClient

from app.analysis import parse_model_output
from app.config import Settings
from app.main import create_app


def test_parses_structured_analysis_output() -> None:
    analysis = parse_model_output(
        '{"intent":"Support","mood":"negative","resolution":"unresolved",'
        '"summary":"A summary","manager_brief":"A brief",'
        '"recommended_action":"Follow up","claims":[],"model_version":"test-v1"}'
    )

    assert analysis.resolution == "unresolved"
    assert analysis.model_version == "test-v1"


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
