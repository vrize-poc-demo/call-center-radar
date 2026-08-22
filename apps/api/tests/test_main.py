from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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
        assert client.get("/api/health").json() == {
            "status": "ok",
            "database": "reachable",
        }


def test_api_accepts_supported_local_vite_ports(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=tmp_path / "call_radar.db",
            sample_data_dir=tmp_path / "samples",
        )
    )

    with TestClient(app) as client:
        for port in (5174, 5175):
            for method in ("GET", "POST"):
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
