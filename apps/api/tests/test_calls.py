from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.pipeline import ProcessingResult

VALID_METADATA = b"""{
  "agent": {"metadata": {"agent_name": "Agent One"}},
  "caller": {"metadata": {"first and last name": "Customer One"}}
}"""

VALID_METADATA_WITH_SID = b"""{
  "sid": "sample",
  "agent": {"metadata": {"agent_name": "Agent One"}},
  "caller": {"metadata": {"first and last name": "Customer One"}}
}"""


class RecordingWorker:
    def __init__(self) -> None:
        self.enqueued_job_ids: list[str] = []

    def enqueue(self, job_id: str) -> ProcessingResult:
        self.enqueued_job_ids.append(job_id)
        return ProcessingResult(job_id, "queued", None, None)


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
            files={
                "audio": ("sample.mp3", b"demo audio", "audio/mpeg"),
                "metadata": ("sample.json", VALID_METADATA, "application/json"),
            },
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
                   calls.agent_name, calls.customer_name, processing_jobs.job_id,
                   processing_jobs.status
            FROM calls
            JOIN processing_jobs ON processing_jobs.call_id = calls.id
            """
        ).fetchone()

    assert record is not None
    assert record["call_id"] == payload["call_id"]
    assert record["job_id"] == payload["job_id"]
    assert record["status"] == "queued"
    assert record["source_metadata_path"] == str(settings.upload_dir / f"{payload['call_id']}.json")
    assert record["agent_name"] == "Agent One"
    assert record["customer_name"] == "Customer One"
    assert (settings.upload_dir / f"{payload['call_id']}.mp3").read_bytes() == b"demo audio"
    assert (settings.upload_dir / f"{payload['call_id']}.json").read_bytes() == VALID_METADATA


def test_register_call_wakes_processing_worker_without_extra_process_request(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    worker = RecordingWorker()

    with TestClient(app) as client:
        app.state.processing_worker = worker
        response = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("sample.wav", b"audio bytes", "audio/wav")},
        )

    assert response.status_code == 201
    assert worker.enqueued_job_ids == [response.json()["job_id"]]


def test_register_call_rejects_unsupported_audio_without_creating_records(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            files={
                "audio": ("notes.txt", b"not audio", "text/plain"),
                "metadata": ("sample.json", VALID_METADATA, "application/json"),
            },
        )

    assert response.status_code == 415
    assert response.json()["detail"] == "Only MP3 and WAV audio files are supported."
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM processing_jobs").fetchone()[0] == 0


def test_register_call_rejects_invalid_metadata_without_creating_records(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            files={
                "audio": ("sample.mp3", b"demo audio", "audio/mpeg"),
                "metadata": ("sample.json", b'{"agent": {}}', "application/json"),
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Metadata must be valid JSON with agent and caller names."
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0


def test_register_call_rejects_metadata_that_does_not_match_audio_sid(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            files={
                "audio": ("other-call.mp3", b"demo audio", "audio/mpeg"),
                "metadata": ("sample.json", VALID_METADATA_WITH_SID, "application/json"),
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Metadata sid must match the selected audio filename."
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0


def test_register_call_accepts_duplicate_copy_suffix_when_sid_matches(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            files={
                "audio": ("sample 2.mp3", b"demo audio", "audio/mpeg"),
                "metadata": ("sample 2.json", VALID_METADATA_WITH_SID, "application/json"),
            },
        )

    assert response.status_code == 201
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 1


def test_register_call_rejects_files_over_the_configured_limit(tmp_path) -> None:
    app = create_app(build_settings(tmp_path, max_upload_bytes=4))

    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            files={
                "audio": ("large.wav", b"12345", "audio/wav"),
                "metadata": ("sample.json", VALID_METADATA, "application/json"),
            },
        )

    assert response.status_code == 413
    with app.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 0


def test_call_detail_returns_processing_context_and_audio(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        registered = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("sample.wav", b"audio bytes", "audio/wav")},
        ).json()
        detail = client.get(f"/api/calls/{registered['call_id']}")
        audio = client.get(f"/api/calls/{registered['call_id']}/audio")
        missing = client.get("/api/calls/unknown-call")

    assert detail.status_code == 200
    assert detail.json() == {
        "call_id": registered["call_id"],
        "agent_name": "Agent",
        "customer_name": "Customer",
        "created_at": detail.json()["created_at"],
        "processing_status": "queued",
        "audio_channels": None,
        "failure_reason": None,
        "transcript_turn_count": 0,
    }
    assert audio.status_code == 200
    assert audio.content == b"audio bytes"
    assert missing.status_code == 404


def test_processing_queue_lists_recent_durable_jobs_without_call_content(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        first = client.post(
            "/api/calls",
            data={"agent_name": "Agent One", "customer_name": "Customer One"},
            files={"audio": ("first.wav", b"first audio", "audio/wav")},
        ).json()
        second = client.post(
            "/api/calls",
            data={"agent_name": "Agent Two", "customer_name": "Customer Two"},
            files={"audio": ("second.wav", b"second audio", "audio/wav")},
        ).json()
        with app.state.database.connect() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status = ? WHERE job_id = ?",
                ("completed", first["job_id"]),
            )
            connection.execute(
                "UPDATE processing_jobs SET status = ?, failure_reason = ? WHERE job_id = ?",
                ("failed", "invalid_audio", second["job_id"]),
            )
        response = client.get("/api/calls/processing-queue")

    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["job_id"] for item in items} == {first["job_id"], second["job_id"]}
    completed = next(item for item in items if item["job_id"] == first["job_id"])
    failed = next(item for item in items if item["job_id"] == second["job_id"])
    assert completed == {
        "job_id": first["job_id"],
        "call_id": first["call_id"],
        "customer_name": "Customer One",
        "status": "completed",
        "updated_at": completed["updated_at"],
        "failure_reason": None,
    }
    assert failed["failure_reason"] == "invalid_audio"
    assert "agent_name" not in failed
    assert "transcript" not in failed


def test_terminal_job_can_be_hidden_from_queue_without_deleting_call_data(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        registered = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("sample.wav", b"audio bytes", "audio/wav")},
        ).json()
        with app.state.database.connect() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status = ? WHERE job_id = ?",
                ("completed", registered["job_id"]),
            )

        dismissed = client.delete(f"/api/calls/{registered['job_id']}/queue-item")
        queue = client.get("/api/calls/processing-queue")
        detail = client.get(f"/api/calls/{registered['call_id']}")

    assert dismissed.status_code == 204
    assert queue.json() == {"items": []}
    assert detail.status_code == 200
    assert detail.json()["processing_status"] == "completed"


def test_active_job_cannot_be_removed_from_queue(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        registered = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("sample.wav", b"audio bytes", "audio/wav")},
        ).json()
        response = client.delete(f"/api/calls/{registered['job_id']}/queue-item")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Only completed or failed calls can be removed from the queue."
    )


def test_clear_all_call_data_removes_persisted_rows_and_files(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        registered = client.post(
            "/api/calls",
            files={
                "audio": ("sample.wav", b"audio bytes", "audio/wav"),
                "metadata": ("sample.json", VALID_METADATA, "application/json"),
            },
        ).json()
        with app.state.database.connect() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status = ? WHERE job_id = ?",
                ("completed", registered["job_id"]),
            )

        response = client.delete("/api/calls/data")
        queue = client.get("/api/calls/processing-queue")
        detail = client.get(f"/api/calls/{registered['call_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["calls_deleted"] == 1
    assert payload["processing_jobs_deleted"] == 1
    assert payload["transcript_turns_deleted"] == 0
    assert payload["analysis_rows_deleted"] == 1
    assert payload["upload_files_deleted"] == 2
    assert queue.json() == {"items": []}
    assert detail.status_code == 404
    assert not settings.upload_dir.exists() or not any(settings.upload_dir.iterdir())
