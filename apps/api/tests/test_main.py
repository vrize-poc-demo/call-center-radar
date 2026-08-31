from fastapi.testclient import TestClient

from app import service_health
from app.config import Settings
from app.main import create_app


class _FakeOllamaResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeOllamaResponse":
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload).encode("utf-8")


def test_api_root_and_health_report_ready_state(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
        )
    )

    with TestClient(app) as client:
        assert client.get("/api").json() == {
            "service": "call-center-radar-api",
            "status": "ready",
        }
        health = client.get("/api/health").json()

    assert health["status"] == "degraded"
    assert {service["key"] for service in health["services"]} == {
        "database",
        "processing_worker",
        "transcription_runtime",
        "ollama_server",
        "ollama_model",
    }
    assert health["services"][0] == {
        "key": "database",
        "label": "SQLite data store",
        "status": "healthy",
        "detail": "SQLite is reachable and ready to persist calls.",
        "action_label": None,
        "action_hint": None,
    }


def test_health_reports_ready_local_stack(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service_health.shutil, "which", lambda _: "/usr/bin/tool")
    monkeypatch.setattr(service_health, "find_spec", lambda _: object())
    monkeypatch.setattr(
        service_health,
        "urlopen",
        lambda request, timeout: _FakeOllamaResponse({"models": [{"name": "qwen2.5:7b"}]}),
    )
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
            processing_worker_enabled=True,
        )
    )

    with TestClient(app) as client:
        health = client.get("/api/health").json()

    assert health["status"] == "healthy"
    assert [service["status"] for service in health["services"]] == [
        "healthy",
        "healthy",
        "healthy",
        "healthy",
        "healthy",
    ]


def test_health_explains_missing_local_llm_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(service_health.shutil, "which", lambda _: "/usr/bin/tool")
    monkeypatch.setattr(service_health, "find_spec", lambda _: object())
    monkeypatch.setattr(
        service_health,
        "urlopen",
        lambda request, timeout: _FakeOllamaResponse({"models": []}),
    )
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
            processing_worker_enabled=True,
        )
    )

    with TestClient(app) as client:
        health = client.get("/api/health").json()

    model_check = next(
        service for service in health["services"] if service["key"] == "ollama_model"
    )
    assert health["status"] == "degraded"
    assert model_check["status"] == "degraded"
    assert model_check["action_label"] == "Pull model"
    assert "ollama pull qwen2.5:7b" in model_check["action_hint"]


def test_api_accepts_supported_local_vite_ports(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
        )
    )

    with TestClient(app) as client:
        for port in (5174, 5175):
            for method in ("DELETE", "GET", "POST"):
                origin = f"http://127.0.0.1:{port}"
                response = client.options(
                    "/api/calls/processing-queue",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": method,
                    },
                )

                assert response.status_code == 200
                assert response.headers["access-control-allow-origin"] == origin


def test_each_api_response_has_a_server_generated_request_id(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
        )
    )

    with TestClient(app) as client:
        first = client.get("/api")
        second = client.get("/api/health")

    assert first.headers["x-request-id"].startswith("req_")
    assert second.headers["x-request-id"].startswith("req_")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
