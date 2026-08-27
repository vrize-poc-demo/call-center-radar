import json
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis_provider import GeneratedAnalysis
from app.config import Settings
from app.main import create_app
from app.transcription import AudioInfo, AudioInspectionError, TranscribedTurn


class TraceTranscriber:
    model_version = "fixture-stt:v1"

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]:
        return [
            TranscribedTurn(
                speaker="unknown",
                start_ms=0,
                end_ms=100,
                text="Please help with my account",
            )
        ]


class TraceAnalysisProvider:
    def generate(self, turns) -> GeneratedAnalysis:
        turn = turns[0]
        return GeneratedAnalysis(
            raw_output=json.dumps(
                {
                    "intent": "Account support",
                    "mood": "neutral",
                    "resolution": "unclear",
                    "summary": "The customer requested account support.",
                    "manager_brief": "Review the account request.",
                    "recommended_action": "Confirm the next owner.",
                    "claims": [
                        {
                            "claim": "Account support requested",
                            "transcript_turn_id": turn.transcript_turn_id,
                            "quote": turn.text,
                            "start_ms": turn.start_ms,
                            "end_ms": turn.end_ms,
                        }
                    ],
                }
            ),
            model_version="fixture-analysis:v2",
        )


class InvalidAnalysisProvider:
    def generate(self, turns) -> GeneratedAnalysis:
        return GeneratedAnalysis(
            raw_output='{"intent":"missing required fields"}',
            model_version="bad",
        )


def build_settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "call_radar.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024 * 1024,
    )


def wav_bytes(path: Path) -> bytes:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 16)
    return path.read_bytes()


def register_call(client: TestClient, audio: bytes) -> dict[str, str]:
    response = client.post(
        "/api/calls",
        data={"agent_name": "Agent", "customer_name": "Customer"},
        files={"audio": ("sample.wav", audio, "audio/wav")},
    )
    assert response.status_code == 201
    return response.json()


def test_trace_endpoint_correlates_request_job_model_rules_and_validation(
    tmp_path, monkeypatch
) -> None:
    app = create_app(build_settings(tmp_path))
    audio = wav_bytes(tmp_path / "sample.wav")
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )

    with TestClient(app) as client:
        app.state.transcriber = TraceTranscriber()
        app.state.analysis_provider = TraceAnalysisProvider()
        registered = register_call(client, audio)
        client.post(f"/api/calls/{registered['job_id']}/process")
        completed = app.state.processing_worker.run_once()
        assert completed is not None and completed.status == "completed"
        analysis = client.post(f"/api/calls/{registered['call_id']}/analysis")
        trace = client.get(f"/api/calls/{registered['call_id']}/trace")

    assert analysis.status_code == 200
    assert trace.status_code == 200
    payload = trace.json()
    assert payload["trace_id"] == registered["trace_id"]
    assert payload["job_id"] == registered["job_id"]
    assert payload["schema_version"] == "call-trace-v1"
    assert payload["events"][0]["request_id"].startswith("req_")
    assert any(event["model_version"] == "fixture-stt:v1" for event in payload["events"])
    validated = next(
        event for event in payload["events"] if event["event_type"] == "analysis_validated"
    )
    assert validated["model_version"] == "fixture-analysis:v2"
    assert validated["rule_version"] == "analysis-rules-v1"
    assert validated["validation_result"] == "accepted"
    assert all("quote" not in event and "text" not in event for event in payload["events"])
    assert "Customer" not in json.dumps(payload)


def test_failed_processing_trace_preserves_stable_reason(tmp_path, monkeypatch) -> None:
    app = create_app(build_settings(tmp_path))

    def invalid_audio(_):
        raise AudioInspectionError("decoder details must not be persisted")

    monkeypatch.setattr("app.pipeline.inspect_audio", invalid_audio)
    with TestClient(app) as client:
        registered = register_call(client, b"not audio")
        client.post(f"/api/calls/{registered['job_id']}/process")
        failed = app.state.processing_worker.run_once()
        trace = client.get(f"/api/calls/{registered['call_id']}/trace").json()

    assert failed is not None and failed.failure_reason == "invalid_audio"
    failure = next(event for event in trace["events"] if event["status"] == "failed")
    assert failure["failure_reason"] == "invalid_audio"
    assert "decoder details" not in json.dumps(trace)


def test_rejected_analysis_records_validation_result_and_safe_reason(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    app.state.analysis_provider = InvalidAnalysisProvider()
    with TestClient(app) as client:
        registered = register_call(client, b"audio")
        transcript = client.put(
            f"/api/calls/{registered['call_id']}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 0,
                        "end_ms": 100,
                        "text": "Please help",
                    }
                ]
            },
        )
        assert transcript.status_code == 200
        analysis = client.post(f"/api/calls/{registered['call_id']}/analysis")
        trace = client.get(f"/api/calls/{registered['call_id']}/trace").json()

    assert analysis.status_code == 502
    rejected = next(
        event for event in trace["events"] if event["event_type"] == "analysis_validation_failed"
    )
    assert rejected["status"] == "failed"
    assert rejected["validation_result"] == "rejected"
    assert rejected["failure_reason"] == "invalid_model_output"
    assert rejected["rule_version"] == "analysis-rules-v1"


def test_unknown_call_trace_returns_clear_not_found(tmp_path) -> None:
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/api/calls/unknown/trace")

    assert response.status_code == 404
    assert response.json()["detail"] == "Call trace not found."


def test_legacy_queued_job_receives_trace_id_when_processing_starts(tmp_path, monkeypatch) -> None:
    app = create_app(build_settings(tmp_path))
    app.state.analysis_provider = None
    audio = wav_bytes(tmp_path / "legacy.wav")
    monkeypatch.setattr(
        "app.pipeline.inspect_audio", lambda _: AudioInfo(channels=1, duration_ms=4)
    )
    with TestClient(app) as client:
        app.state.transcriber = TraceTranscriber()
        registered = register_call(client, audio)
        with app.state.database.connect() as connection:
            connection.execute(
                "UPDATE processing_jobs SET trace_id = NULL WHERE job_id = ?",
                (registered["job_id"],),
            )
        client.post(f"/api/calls/{registered['job_id']}/process")
        completed = app.state.processing_worker.run_once()
        trace = client.get(f"/api/calls/{registered['call_id']}/trace")

    assert completed is not None and completed.status == "completed"
    assert trace.status_code == 200
    assert trace.json()["trace_id"] == f"trace_legacy_{registered['job_id']}"
