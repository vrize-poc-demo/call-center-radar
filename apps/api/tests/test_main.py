from fastapi.testclient import TestClient

from app.main import app


def test_api_root_reports_bootstrap_state() -> None:
    response = TestClient(app).get("/api")

    assert response.status_code == 200
    assert response.json() == {
        "service": "call-center-radar-api",
        "status": "bootstrap-ready",
    }
