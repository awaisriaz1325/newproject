from fastapi.testclient import TestClient

from compback_api.main import create_app


def test_liveness_and_security_headers() -> None:
    client = TestClient(create_app())
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-Id" in r.headers


def test_readiness_with_database() -> None:
    client = TestClient(create_app())
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["database"] == "up"
