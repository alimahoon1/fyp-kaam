"""FastAPI service for the dashboard (PLAN task 5.1): options, network geometry, run control,
ambulance dispatch, road closure and the state stream, all against a real SUMO run."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from manzil.api.app import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = create_app(runs_dir=tmp_path / "live", serve_dashboard=False)
    with TestClient(app) as c:
        c.session = app.state.session
        yield c
        app.state.session.stop()


def _start(client, **kw):
    body = {"controller": "fixed_time", "profile": "light", "duration_s": 900, "speed": 0, **kw}
    r = client.post("/api/run/start", json=body)
    assert r.status_code == 200, r.text
    return client.session.wait_for(lambda s: s["status"] == "running" and s["sim_time_s"] >= 30)


def test_options_and_health(client):
    assert client.get("/api/health").json()["ok"] is True
    o = client.get("/api/options").json()
    assert {c["id"] for c in o["controllers"]} == {"fixed_time", "adaptive", "dqn"}
    assert {p["id"] for p in o["profiles"]} == {"light", "medium", "heavy", "uneven"}
    assert client.get("/api/state").json()["status"] == "idle"


def test_network_geometry_comes_from_the_net_file(client):
    n = client.get("/api/network").json()
    assert len(n["tls"]) == 9
    assert n["network_id"].startswith("grid3x3.net.xml#")
    edges = {e["id"]: e for e in n["edges"]}
    assert "left0A0" in edges and "C2top2" in edges
    assert all(len(lane["shape"]) >= 2 for e in edges.values() for lane in e["lanes"])
    # every signal link refers to a lane that is drawn
    lanes = {lane["id"] for e in edges.values() for lane in e["lanes"]}
    assert all(lk["from_lane"] in lanes for t in n["tls"] for lk in t["links"])
    xmin, ymin, xmax, ymax = n["bounds"]
    assert xmax > xmin and ymax > ymin


@pytest.mark.parametrize(
    "body",
    [
        {"controller": "nope"},
        {"profile": "rush"},
        {"seed": -1},
        {"duration_s": 10},
        {"speed": -1},
    ],
)
def test_bad_start_requests_are_rejected(client, body):
    assert client.post("/api/run/start", json=body).status_code == 422
    assert client.get("/api/state").json()["status"] == "idle"


def test_commands_need_an_active_run(client):
    assert client.post("/api/ambulance", json={}).status_code == 409
    assert client.post("/api/roads/close", json={"edge_id": "B0B1"}).status_code == 409


def test_live_run_with_signals_vehicles_and_stop(client, tmp_path):
    s = _start(client, controller="adaptive")
    assert s["config"]["controller"] == "adaptive"
    assert set(s["signals"]) == {"A0", "A1", "A2", "B0", "B1", "B2", "C0", "C1", "C2"}
    assert all(set(x["state"]) <= set("GgyrRYu") for x in s["signals"].values())
    assert s["stats"]["departed"] > 0
    assert client.post("/api/run/start", json={}).status_code == 409  # one run at a time
    s = client.session.wait_for(lambda s: s["stats"]["running"] > 0 and s["vehicles"])
    assert len(s["vehicles"]) <= s["stats"]["running"]
    r = client.post("/api/run/stop").json()
    assert r["status"] == "stopped"
    assert r["stats"]["safety_violations"] == 0
    summary = json.loads(next((tmp_path / "live").glob("*/summary.json")).read_text())
    assert summary["termination"] == "stopped" and summary["safety_violations"] == 0


def test_dispatch_close_road_reroute_and_corridor(client, tmp_path):
    _start(client, profile="medium")
    # slow the run so the test can act while the ambulance is still near its origin
    client.post("/api/run/speed", json={"speed": 3})
    r = client.post("/api/ambulance", json={"origin": "left0A0", "destination": "C2top2",
                                            "corridor": True})  # fmt: skip
    assert r.status_code == 200, r.text
    assert client.post("/api/ambulance", json={}).status_code == 409  # one mission at a time
    # wait until the ambulance has entered the network (a full road can delay it)
    s = client.session.wait_for(lambda s: (s["ambulance"]["edge"] or "") != "")
    v1 = s["ambulance"]["route"]
    assert v1[0] == "left0A0" and v1[-1] == "C2top2"
    # close a road on the planned route that the ambulance has not reached yet
    target = v1[3]
    r = client.post("/api/roads/close", json={"edge_id": target})
    assert r.status_code == 200, r.text
    assert client.post("/api/roads/close", json={"edge_id": target}).status_code == 409
    assert client.post("/api/roads/close", json={"edge_id": "nope"}).status_code == 409
    s = client.session.wait_for(lambda s: s["ambulance"]["route_version"] >= 2)
    client.post("/api/run/speed", json={"speed": 0})
    assert target not in s["ambulance"]["route"]
    assert s["ambulance"]["route_triggers"][-1] == "closure"
    assert target in s["closed_edges"]

    seen = set()

    def arrived(st):
        seen.update(st["ambulance"]["corridor"].values())
        return st["ambulance"]["status"] == "ARRIVED"

    s = client.session.wait_for(arrived, timeout=180, poll=0.01)
    a = s["ambulance"]
    assert a["metrics"]["amb_travel_time_s"] > 0
    assert a["metrics"]["corridor_served"] >= 1
    assert any(e["state"] in ("PASSAGE", "IDLE", "RECOVERY") for e in a["corridor_events"])
    assert seen & {"SAFE_TRANSITION", "ACTIVE_PRIORITY", "REQUESTED"}
    assert s["stats"]["safety_violations"] == 0

    # a second ambulance may be dispatched once the first has arrived
    r = client.post("/api/ambulance", json={"origin": "bottom2C0", "destination": "A2left2",
                                            "corridor": False})  # fmt: skip
    assert r.status_code == 200, r.text
    assert r.json()["vehicle_id"] == "ambulance_2"
    client.post("/api/run/stop")
    summary = json.loads(next((tmp_path / "live").glob("*/summary.json")).read_text())
    assert summary["missions"][0]["metrics"]["mission_status"] == "ARRIVED"
    assert summary["closures"][0]["edge_id"] == target


def test_bad_dispatch_is_rejected(client):
    _start(client)
    r = client.post("/api/ambulance", json={"origin": "nope", "destination": "C2top2"})
    assert r.status_code == 409
    r = client.post("/api/ambulance", json={"origin": "A0A1", "destination": "A0A1"})
    assert r.status_code == 409


def test_dqn_controller_runs(client):
    pytest.importorskip("torch")
    s = _start(client, controller="dqn", profile="medium")
    assert s["config"]["controller"] == "dqn"
    assert client.post("/api/run/speed", json={"speed": 5}).json()["speed"] == 5
    assert client.post("/api/run/stop").json()["stats"]["safety_violations"] == 0


def test_state_websocket_streams(client):
    _start(client)
    with client.websocket_connect("/ws/state") as ws:
        a = ws.receive_json()
        b = ws.receive_json()
    assert b["version"] > a["version"]
    assert b["sim_time_s"] >= a["sim_time_s"]
