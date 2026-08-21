from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_settings(tmp_path, max_upload_bytes: int = 1024) -> Settings:
    return Settings(
        database_path=tmp_path / "call_radar.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=max_upload_bytes,
    )


def test_register_call_creates_linked_call_and_queued_job(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            data={"agent_name": "Agent One", "customer_name": "Customer One"},
            files={"audio": ("sample.mp3", b"demo audio", "audio/mpeg")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["call_id"]
    assert payload["job_id"].startswith("job_")

    with app.state.database.connect() as connection:
        record = connection.execute(
            """
            SELECT calls.call_id, calls.audio_path, calls.source_metadata_path,
                   processing_jobs.job_id, processing_jobs.status
            FROM calls
            JOIN processing_jobs ON processing_jobs.call_id = calls.id
            """
        ).fetchone()

    assert record is not None
    assert record["call_id"] == payload["call_id"]
    assert record["job_id"] == payload["job_id"]
    assert record["status"] == "queued"
    assert record["source_metadata_path"] == f"upload://{payload['call_id']}"
    assert (settings.upload_dir / f"{payload['call_id']}.mp3").read_bytes() == b"demo audio"


def test_register_call_rejects_unsupported_audio_without_creating_records(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            data={"agent_name": "Agent One", "customer_name": "Customer One"},
            files={"audio": ("notes.txt", b"not audio", "text/plain")},
        )

    assert response.status_code == 415
    assert response.json()["detail"] == "Only MP3 and WAV audio files are supported."
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM processing_jobs").fetchone()[0] == 0


def test_register_call_rejects_blank_required_metadata(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            data={"agent_name": " ", "customer_name": "Customer One"},
            files={"audio": ("sample.mp3", b"demo audio", "audio/mpeg")},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Agent and customer names are required."


def test_register_call_rejects_files_over_the_configured_limit(tmp_path) -> None:
    app = create_app(build_settings(tmp_path, max_upload_bytes=4))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            data={"agent_name": "Agent One", "customer_name": "Customer One"},
            files={"audio": ("large.wav", b"12345", "audio/wav")},
        )

    assert response.status_code == 413
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0
