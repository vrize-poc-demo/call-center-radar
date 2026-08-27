import json
import threading
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.analysis_provider import GeneratedAnalysis
from app.config import Settings
from app.main import create_app
from app.pipeline import ProcessingPipeline, ProcessingResult
from app.transcription import AudioInfo, AudioInspectionError, TranscribedTurn, TranscriptionError
from app.worker import DurableProcessingWorker


class FakeTranscriber:
    model_version = "fake-transcriber:v1"

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]:
        assert audio_path.is_file()
        speaker = "unknown" if audio_info.channels == 1 else "agent"
        return [TranscribedTurn(speaker=speaker, start_ms=0, end_ms=100, text="Hello there")]


class FailingTranscriber:
    model_version = "fake-transcriber:v1"

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]:
        raise TranscriptionError("model_unavailable")


class RecordingTranscriber(FakeTranscriber):
    def __init__(self) -> None:
        self.processed_paths: list[str] = []

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]:
        self.processed_paths.append(audio_path.name)
        return super().transcribe(audio_path, audio_info)


class BlockingTranscriber(FakeTranscriber):
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]:
        self.started.set()
        assert self.release.wait(timeout=2)
        return super().transcribe(audio_path, audio_info)


class FakeAnalysisProvider:
    def generate(self, turns) -> GeneratedAnalysis:
        turn = turns[0]
        payload = {
            "intent": "Customer asked for help",
            "mood": "neutral",
            "resolution": "resolved",
            "summary": "Customer asked for help and the call was resolved.",
            "manager_brief": "Routine resolved support call.",
            "recommended_action": "No manager action required.",
            "claims": [
                {
                    "claim": "Customer need was discussed",
                    "transcript_turn_id": turn.transcript_turn_id,
                    "quote": turn.text,
                    "start_ms": turn.start_ms,
                    "end_ms": turn.end_ms,
                }
            ],
            "mood_shifts": [],
        }
        return GeneratedAnalysis(raw_output=json.dumps(payload), model_version="fake-llm:v1")


class RecoveringPipeline:
    def __init__(self, state: dict, processed: threading.Event) -> None:
        self.state = state
        self.processed = processed

    def process_next(self):
        self.state["attempts"] += 1
        if self.state["attempts"] == 1:
            raise RuntimeError("boom")
        if self.state["attempts"] == 2:
            self.processed.set()
            return ProcessingResult("job_recovered", "completed", 1, None, 1)
        return None


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
    if not hasattr(app.state, "analysis_provider"):
        app.state.analysis_provider = None
    with TestClient(app) as client:
        response = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": (filename, audio_bytes, "audio/wav")},
        )
    assert response.status_code == 201
    return response.json()["job_id"]


def test_pipeline_completes_valid_mono_wav_and_persists_events(tmp_path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path, channels=1)
    job_id = create_queued_job(app, tmp_path, wav_path.read_bytes())
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )

    with TestClient(app) as client:
        app.state.transcriber = FakeTranscriber()
        response = client.post(f"/api/calls/{job_id}/process")
        completed = app.state.processing_worker.run_once()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert completed is not None
    assert completed.__dict__ == {
        "job_id": job_id,
        "status": "completed",
        "audio_channels": 1,
        "failure_reason": None,
        "transcript_turn_count": 1,
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

    # Resolve the call through the durable job record because job and call IDs are distinct.
    with app.state.database.connect() as connection:
        call_id = connection.execute(
            "SELECT calls.call_id FROM calls "
            "JOIN processing_jobs ON processing_jobs.call_id = calls.id "
            "WHERE processing_jobs.job_id = ?",
            (job_id,),
        ).fetchone()["call_id"]
    with TestClient(app) as client:
        transcript = client.get(f"/api/calls/{call_id}/transcript")
    assert transcript.status_code == 200
    assert transcript.json()["turns"][0]["speaker"] == "unknown"


def test_pipeline_generates_analysis_and_priority_before_completion(tmp_path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    app.state.analysis_provider = FakeAnalysisProvider()
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path, channels=1)
    job_id = create_queued_job(app, tmp_path, wav_path.read_bytes())
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )

    with TestClient(app) as client:
        app.state.transcriber = FakeTranscriber()
        response = client.post(f"/api/calls/{job_id}/process")
        completed = app.state.processing_worker.run_once()
        dashboard = client.get("/api/dashboard/triage")

    assert response.status_code == 202
    assert completed is not None and completed.status == "completed"
    assert dashboard.status_code == 200
    assert dashboard.json()["calls"][0]["analysis"]["summary"] == (
        "Customer asked for help and the call was resolved."
    )
    assert dashboard.json()["calls"][0]["radar_priority"] == 0


def test_pipeline_marks_invalid_audio_failed_and_persists_reason(tmp_path, monkeypatch) -> None:
    app = create_app(build_settings(tmp_path))
    job_id = create_queued_job(app, tmp_path, b"not a wav")

    def invalid_audio(_):
        raise AudioInspectionError("invalid_audio")

    monkeypatch.setattr(
        "app.pipeline.inspect_audio",
        invalid_audio,
    )

    with TestClient(app) as client:
        response = client.post(f"/api/calls/{job_id}/process")
        completed = app.state.processing_worker.run_once()

    assert response.status_code == 202
    assert completed is not None
    assert completed.status == "failed"
    assert completed.failure_reason == "invalid_audio"


def test_pipeline_marks_transcription_failure_as_failed(tmp_path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path, channels=2)
    job_id = create_queued_job(app, tmp_path, wav_path.read_bytes())
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=2, duration_ms=4)
    )

    with TestClient(app) as client:
        app.state.transcriber = FailingTranscriber()
        response = client.post(f"/api/calls/{job_id}/process")
        completed = app.state.processing_worker.run_once()

    assert response.status_code == 202
    assert completed is not None
    assert completed.status == "failed"
    assert completed.failure_reason == "transcription_failed"


def test_worker_claims_multiple_queued_calls_in_fifo_order(tmp_path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path)
    job_ids = [create_queued_job(app, tmp_path, wav_path.read_bytes()) for _ in range(3)]
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )
    transcriber = RecordingTranscriber()

    with TestClient(app) as client:
        app.state.transcriber = transcriber
        responses = [client.post(f"/api/calls/{job_id}/process") for job_id in job_ids]
        results = [app.state.processing_worker.run_once() for _ in job_ids]

    assert [response.status_code for response in responses] == [202, 202, 202]
    assert [result.job_id for result in results if result is not None] == job_ids
    assert all(result is not None and result.status == "completed" for result in results)


def test_duplicate_start_is_idempotent_and_does_not_create_extra_work(
    tmp_path, monkeypatch
) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path)
    job_id = create_queued_job(app, tmp_path, wav_path.read_bytes())
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )

    with TestClient(app) as client:
        app.state.transcriber = FakeTranscriber()
        first = client.post(f"/api/calls/{job_id}/process")
        second = client.post(f"/api/calls/{job_id}/process")
        completed = app.state.processing_worker.run_once()
        no_more_work = app.state.processing_worker.run_once()

    assert first.status_code == second.status_code == 202
    assert completed is not None and completed.status == "completed"
    assert no_more_work is None


def test_recovery_returns_interrupted_work_to_queued_with_audit_event(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    job_id = create_queued_job(app, tmp_path, b"audio")
    with TestClient(app):
        with app.state.database.connect() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status = 'transcribing' WHERE job_id = ?", (job_id,)
            )
        assert app.state.processing_worker.recover_interrupted_jobs() == 1

    with app.state.database.connect() as connection:
        job = connection.execute(
            "SELECT status FROM processing_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        event = connection.execute(
            "SELECT from_status, to_status, reason FROM processing_job_events"
        ).fetchone()
    assert job["status"] == "queued"
    assert tuple(event) == ("transcribing", "queued", "worker_restart_recovery")


def test_worker_failure_marks_interrupted_job_failed_with_audit_event(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    job_id = create_queued_job(app, tmp_path, b"audio")
    with TestClient(app):
        with app.state.database.connect() as connection:
            connection.execute(
                "UPDATE processing_jobs SET status = 'analyzing' WHERE job_id = ?", (job_id,)
            )
        assert app.state.processing_worker.fail_interrupted_jobs("worker_error") == 1

    with app.state.database.connect() as connection:
        job = connection.execute(
            "SELECT status, failure_reason FROM processing_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        event = connection.execute(
            "SELECT from_status, to_status, reason FROM processing_job_events"
        ).fetchone()
    assert tuple(job) == ("failed", "worker_error")
    assert tuple(event) == ("analyzing", "failed", "worker_error")


def test_worker_loop_survives_unexpected_pipeline_error(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    state = {"attempts": 0}
    processed = threading.Event()

    with TestClient(app):
        worker = DurableProcessingWorker(
            app.state.database,
            app.state.logger,
            lambda: RecoveringPipeline(state, processed),
        )

        worker.start()
        try:
            assert processed.wait(timeout=2)
        finally:
            worker.stop()

    assert state["attempts"] >= 2


def test_sqlite_remains_readable_while_transcription_runs(tmp_path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    wav_path = tmp_path / "source.wav"
    create_wav(wav_path)
    job_id = create_queued_job(app, tmp_path, wav_path.read_bytes())
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )
    transcriber = BlockingTranscriber()

    with TestClient(app) as client:
        app.state.transcriber = transcriber
        client.post(f"/api/calls/{job_id}/process")
        thread = threading.Thread(target=app.state.processing_worker.run_once)
        thread.start()
        assert transcriber.started.wait(timeout=1)
        assert client.get("/api/calls/processing-queue").status_code == 200
        transcriber.release.set()
        thread.join(timeout=2)
        assert not thread.is_alive()


def test_invalid_job_transition_is_rejected_without_partial_state_or_event(tmp_path) -> None:
    settings = build_settings(tmp_path)
    app = create_app(settings)
    job_id = create_queued_job(app, tmp_path, b"audio")
    pipeline = ProcessingPipeline(
        app.state.database,
        app.state.logger,
        settings,
        transcriber=FakeTranscriber(),
    )

    with app.state.database.connect() as connection:
        job = connection.execute(
            "SELECT id, job_id, call_id, trace_id, status FROM processing_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        with pytest.raises(ValueError, match="invalid_state_transition"):
            pipeline._transition(connection, job, "completed")

    with app.state.database.connect() as connection:
        saved_status = connection.execute(
            "SELECT status FROM processing_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()["status"]
        transition_count = connection.execute(
            "SELECT COUNT(*) FROM processing_job_events"
        ).fetchone()[0]

    assert saved_status == "queued"
    assert transition_count == 0


def test_processing_unknown_job_returns_stable_not_found_contract(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post("/api/calls/job_unknown/process")

    assert response.status_code == 404
    assert response.json() == {"detail": "Processing job not found."}
