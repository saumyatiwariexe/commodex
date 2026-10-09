from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_readyz():
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

def test_get_contracts():
    response = client.get("/api/v1/contracts")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "meta" in data

def test_get_signals():
    response = client.get("/api/v1/signals?as_of=2026-10-09")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["reason"] == "no_signals_generated_for_date"
