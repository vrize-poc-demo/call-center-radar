import wave

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "call_radar.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024 * 1024,
    )


def create_wav(path, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * channels * 16)


def create_queued_job(app, tmp_path, audio_bytes: bytes, filename: str = "call.wav") -> str:
    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": (filename, audio_bytes, "audio/wav")},
        )
    assert response.status_code == 201
    return response.json()["job_id"]


def test_pipeline_completes_valid_mono_wav_and_persists_events(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path, channels=1)
    job_id = create_queued_job(app, tmp_path, wav_path.read_bytes())

    with TestClient(app) as client:
        response = client.post(f"/api/calls/{job_id}/process")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": job_id,
        "status": "completed",
        "audio_channels": 1,
        "failure_reason": None,
    }
    with app.state.database.connect() as connection:
        events = connection.execute(
            "SELECT from_status, to_status FROM processing_job_events ORDER BY id"
        ).fetchall()
    assert [(event["from_status"], event["to_status"]) for event in events] == [
        ("queued", "transcribing"),
        ("transcribing", "analyzing"),
        ("analyzing", "completed"),
    ]


def test_pipeline_marks_invalid_audio_failed_and_persists_reason(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    job_id = create_queued_job(app, tmp_path, b"not a wav")

    with TestClient(app) as client:
        response = client.post(f"/api/calls/{job_id}/process")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["failure_reason"] == "invalid_audio"
