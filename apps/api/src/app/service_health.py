from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI

ServiceStatus = Literal["healthy", "degraded", "unhealthy"]


@dataclass(frozen=True)
class ServiceCheck:
    key: str
    label: str
    status: ServiceStatus
    detail: str
    action_label: str | None = None
    action_hint: str | None = None


def build_service_health(app: FastAPI) -> dict[str, object]:
    """Build a UI-safe operational health report without exposing call content."""

    checks = [
        _database_check(app),
        _processing_worker_check(app),
        _transcription_runtime_check(),
    ]
    ollama_check, model_check = _ollama_checks(app)
    checks.extend([ollama_check, model_check])
    return {
        "status": _overall_status(checks),
        "services": [asdict(check) for check in checks],
    }


def _database_check(app: FastAPI) -> ServiceCheck:
    try:
        app.state.database.check_connection()
    except Exception:
        return ServiceCheck(
            key="database",
            label="SQLite data store",
            status="unhealthy",
            detail="SQLite is not reachable. Uploaded calls cannot be saved.",
            action_label="Check data path",
            action_hint="Confirm CALL_RADAR_DATABASE_PATH is writable, then restart the API.",
        )
    return ServiceCheck(
        key="database",
        label="SQLite data store",
        status="healthy",
        detail="SQLite is reachable and ready to persist calls.",
    )


def _processing_worker_check(app: FastAPI) -> ServiceCheck:
    if not app.state.settings.processing_worker_enabled:
        return ServiceCheck(
            key="processing_worker",
            label="Processing worker",
            status="degraded",
            detail="The API is running, but automatic background processing is disabled.",
            action_label="Enable worker",
            action_hint="Set CALL_RADAR_PROCESSING_WORKER_ENABLED=true and restart the API.",
        )
    worker = getattr(app.state, "processing_worker", None)
    is_running = bool(getattr(worker, "is_running", False))
    if not is_running:
        return ServiceCheck(
            key="processing_worker",
            label="Processing worker",
            status="unhealthy",
            detail="The background worker is not running, so queued calls will not advance.",
            action_label="Restart API",
            action_hint="Restart npm run dev or docker compose up --build app.",
        )
    return ServiceCheck(
        key="processing_worker",
        label="Processing worker",
        status="healthy",
        detail="The background worker is running and ready to process queued calls.",
    )


def _transcription_runtime_check() -> ServiceCheck:
    missing = []
    if shutil.which("ffmpeg") is None:
        missing.append("ffmpeg")
    if shutil.which("ffprobe") is None:
        missing.append("ffprobe")
    if find_spec("faster_whisper") is None:
        missing.append("faster-whisper")
    if missing:
        return ServiceCheck(
            key="transcription_runtime",
            label="Transcription runtime",
            status="unhealthy",
            detail=f"Missing local audio/transcription dependency: {', '.join(missing)}.",
            action_label="Install dependencies",
            action_hint="Run ./scripts/setup-dev.sh or use docker compose up --build.",
        )
    return ServiceCheck(
        key="transcription_runtime",
        label="Transcription runtime",
        status="healthy",
        detail="FFmpeg, ffprobe, and faster-whisper are available.",
    )


def _ollama_checks(app: FastAPI) -> tuple[ServiceCheck, ServiceCheck]:
    settings = app.state.settings
    base_url = settings.ollama_base_url.rstrip("/")
    try:
        request = Request(f"{base_url}/api/tags", method="GET")
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return (
            ServiceCheck(
                key="ollama_server",
                label="Local LLM server",
                status="unhealthy",
                detail="Ollama is not reachable, so LLM-backed analysis will fail.",
                action_label="Start Ollama",
                action_hint="Run ollama serve, or docker compose up -d ollama.",
            ),
            ServiceCheck(
                key="ollama_model",
                label="Analysis model",
                status="unhealthy",
                detail=f"Cannot verify model {settings.ollama_model} until Ollama is reachable.",
                action_label="Start Ollama first",
                action_hint="Start Ollama, then pull the configured model.",
            ),
        )

    models = payload.get("models", [])
    model_names = {
        model.get("name")
        for model in models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    }
    if settings.ollama_model in model_names:
        model_check = ServiceCheck(
            key="ollama_model",
            label="Analysis model",
            status="healthy",
            detail=f"Configured model {settings.ollama_model} is available.",
        )
    else:
        model_check = ServiceCheck(
            key="ollama_model",
            label="Analysis model",
            status="degraded",
            detail=f"Ollama is running, but model {settings.ollama_model} is not installed.",
            action_label="Pull model",
            action_hint=(
                f"Run ollama pull {settings.ollama_model}, or docker compose run --rm ollama-model."
            ),
        )
    return (
        ServiceCheck(
            key="ollama_server",
            label="Local LLM server",
            status="healthy",
            detail="Ollama is reachable.",
        ),
        model_check,
    )


def _overall_status(checks: list[ServiceCheck]) -> ServiceStatus:
    if any(check.status == "unhealthy" and check.key == "database" for check in checks):
        return "unhealthy"
    if any(check.status != "healthy" for check in checks):
        return "degraded"
    return "healthy"
