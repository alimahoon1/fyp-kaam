from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_state_contracts():
    assert client.get("/api/health").json()["simulationAdapter"] == "prototype-sim"
    state = client.get("/api/state").json()
    assert state["schemaVersion"] == "1.0"
    assert state["sourceMode"] == "prototype-sim"
    assert len(state["nodes"]) == 6


def test_operator_workflow_and_export():
    reset = client.post("/api/simulation/reset", json={"seed": 104, "scenario": "balanced", "controller": "adaptive"})
    assert reset.status_code == 200
    mission = client.post("/api/emergency/dispatch", json={"origin": "I-01", "destination": "I-06"})
    assert mission.status_code == 200
    assert mission.json()["mission"]["status"] == "ACTIVE"
    stepped = client.post("/api/simulation/step", json={"steps": 12})
    assert stepped.status_code == 200
    exported = client.get("/api/export")
    assert exported.status_code == 200
    assert exported.json()["manifest"]["simulationAdapter"] == "prototype-sim"


def test_mock_perception_is_explicit():
    payload = client.get("/api/perception").json()
    assert payload["sourceMode"] == "mock-perception"
    assert payload["calibrated"] is False
    assert "no YOLO" in payload["notice"]
