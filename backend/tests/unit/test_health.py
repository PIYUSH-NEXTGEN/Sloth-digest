"""Phase 0 smoke tests: app factory and /health per contracts/openapi.yaml."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["model"]
    assert data["version"]


def test_health_matches_contract_shape() -> None:
    app = create_app()
    client = TestClient(app)
    data = client.get("/health").json()
    assert set(data.keys()) == {"status", "version", "model"}
