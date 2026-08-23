from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "call_radar.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )


def create_call(client: TestClient) -> str:
    response = client.post(
        "/api/calls",
        data={"agent_name": "Agent", "customer_name": "Customer"},
        files={"audio": ("sample.wav", b"audio", "audio/wav")},
    )
    assert response.status_code == 201
    return response.json()["call_id"]


def test_save_and_retrieve_transcript_turns_in_timestamp_order(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        call_id = create_call(client)
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {"speaker": "customer", "start_ms": 500, "end_ms": 700, "text": "Hello"},
                    {"speaker": "agent", "start_ms": 0, "end_ms": 400, "text": "Welcome"},
                ]
            },
        )
        loaded = client.get(f"/api/calls/{call_id}/transcript")

    assert saved.status_code == 200
    assert all(turn["transcript_turn_id"].startswith("turn_") for turn in saved.json()["turns"])
    assert loaded.status_code == 200
    assert [turn["text"] for turn in loaded.json()["turns"]] == ["Welcome", "Hello"]


def test_rejects_turn_with_invalid_timing(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        call_id = create_call(client)
        response = client.put(
            f"/api/calls/{call_id}/transcript",
            json={"turns": [{"speaker": "agent", "start_ms": 20, "end_ms": 10, "text": "No"}]},
        )

    assert response.status_code == 422


def test_accepts_unknown_speaker_for_mono_transcription(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        call_id = create_call(client)
        response = client.put(
            f"/api/calls/{call_id}/transcript",
            json={"turns": [{"speaker": "unknown", "start_ms": 0, "end_ms": 10, "text": "Hi"}]},
        )

    assert response.status_code == 200
    assert response.json()["turns"][0]["speaker"] == "unknown"
