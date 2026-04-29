from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoint_does_not_require_claude_key() -> None:
    app = create_app(Settings(APP_ENV="test"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "test",
    }


def test_service_info_endpoint() -> None:
    app = create_app(Settings(APP_ENV="test"))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "Support Agent API"
