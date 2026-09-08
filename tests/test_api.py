"""API endpoint tests using FastAPI TestClient."""

import os
os.environ["USE_DOCKER_SANDBOX"] = "false"

from backend.app.database import init_db
init_db()

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.simulator import sim_state

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_simulator_metrics():
    resp = client.get("/simulator/metrics?seconds_ago=300&interval_s=60")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "accuracy" in data[0]


def test_simulator_git_commits():
    resp = client.get("/simulator/git/commits")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


def test_simulator_deployments():
    resp = client.get("/simulator/deployments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_simulator_inject_and_reset():
    resp = client.post("/simulator/inject?fault_type=preprocessing_mismatch")
    assert resp.status_code == 200
    assert "preprocessing_mismatch" in resp.json()["active_faults"]

    resp = client.post("/simulator/reset")
    assert resp.status_code == 200
    assert resp.json()["active_faults"] == []


def test_simulator_predict():
    resp = client.post("/simulator/predict", json={"features": [0.5, 0.3, 0.7, 0.4, 0.6]})
    assert resp.status_code == 200
    data = resp.json()
    assert "prediction" in data
    assert "probability" in data


def test_list_incidents_empty():
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_incident_not_found():
    resp = client.get("/api/incidents/nonexistent")
    assert resp.status_code == 404


def test_memory_search():
    resp = client.get("/api/memory/search?query=preprocessing")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
