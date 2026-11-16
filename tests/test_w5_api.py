"""W5 API: G01 validation, pause/resume (FR-02), FR-16 warnings (fallback, invalid, stale,
disconnected), planned mission and incident, store/analytics/export/perception endpoints.
Live runs are real SUMO runs (TraCI backend); stale and disconnected are produced by really
freezing (SIGSTOP) or killing (SIGKILL) that SUMO process."""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from manzil.api.app import create_app  # noqa: E402

HAS_TORCH = importlib.util.find_spec("torch") is not None
MISSION = {"origin": "left0A0", "destination": "C2top2", "dispatch_s": 40, "corridor": True}


@pytest.fixture()
def client(tmp_path):
    app = create_app(runs_dir=tmp_path / "live", serve_dashboard=False)
    with TestClient(app) as c:
        c.session = app.state.session
        c.tmp = tmp_path
        yield c
        app.state.session.stop()


def _start(client, until=30, **kw):
    body = {"controller": "fixed_time", "profile": "light", "duration_s": 900, "speed": 0, **kw}
    r = client.post("/api/run/start", json=body)
    assert r.status_code == 200, r.text
    return client.session.wait_for(lambda s: s["status"] == "running" and s["sim_time_s"] >= until)


def _codes(state) -> set[str]:
    return {w["code"] for w in state.get("warnings", [])}


def _sumo_pids(tmp_path: Path) -> list[int]:
    """The SUMO processes of this run: their command line names the test's run folder (the
    PyPI ``sumo`` launcher is a Python script that starts the real binary as its child)."""
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if "sumo" in cmd and f"{tmp_path}/live/" in cmd:
            out.append(int(p.name))
    if not out:
        raise LookupError("SUMO process not found")
    return out


# ----- G01 validation --------------------------------------------------------------------------
def test_validate_lists_checks_and_start_refuses_errors(client):
    ok = client.post(
        "/api/run/validate",
        json={
            "controller": "fixed_time",
            "profile": "heavy",
            "duration_s": 600,
            "mission": MISSION,
            "incident": {"edge_id": "B1C1", "time_s": 50},
        },
    )
    body = ok.json()
    assert body["ok"] is True
    fields = {c["field"] for c in body["checks"]}
    assert {
        "scenario",
        "profile",
        "controller",
        "seed",
        "duration_s",
        "mission",
        "incident",
        "perception",
    } <= fields
    assert any(c["level"] == "warning" and "warm-up" in c["message"] for c in body["checks"])

    bad = {
        "controller": "fixed_time",
        "duration_s": 600,
        "mission": {"origin": "left0A0", "destination": "left0A0", "dispatch_s": 900},
        "incident": {"edge_id": "nope", "time_s": 10},
    }
    v = client.post("/api/run/validate", json=bad).json()
    errors = [c for c in v["checks"] if c["level"] == "error"]
    assert v["ok"] is False and {c["field"] for c in errors} == {"mission", "incident"}
    r = client.post("/api/run/start", json=bad)
    assert r.status_code == 422 and "same road" in r.json()["detail"]
    assert client.get("/api/state").json()["status"] == "idle"


# ----- FR-02 pause / resume --------------------------------------------------------------------
def test_pause_and_resume(client):
    _start(client)
    assert client.post("/api/run/resume").status_code == 409  # not paused
    p = client.post("/api/run/pause")
    assert p.status_code == 200 and p.json()["status"] == "paused"
    t0 = client.session.state["sim_time_s"]
    time.sleep(1.2)
    s = client.get("/api/state").json()
    assert s["status"] == "paused" and s["sim_time_s"] == t0  # SUMO is not stepped
    assert "stale" not in _codes(s) and s["age_s"] < 1.5  # paused but fresh
    # commands still work while paused, between steps
    r = client.post("/api/roads/close", json={"edge_id": "B1C1"})
    assert r.status_code == 200 and client.session.state["status"] == "paused"
    assert client.post("/api/run/pause").status_code == 409
    assert client.post("/api/run/resume").json()["status"] == "running"
    client.session.wait_for(lambda x: x["sim_time_s"] > t0 + 20)
    assert client.session.state["pauses"][0]["sim_time_s"] == t0
    final = client.post("/api/run/stop").json()
    summary = json.loads((client.tmp / "live" / final["run_id"] / "summary.json").read_text())
    assert summary["pauses"][0]["wall_s"] >= 1.0 and summary["closures"][0]["edge_id"] == "B1C1"


# ----- G01 planned mission + incident; G02 history; G03 approaches -----------------------------
def test_planned_mission_and_incident_run_at_their_time(client):
    s = _start(
        client,
        until=60,
        profile="medium",
        mission=MISSION,
        incident={"edge_id": "B1C1", "time_s": 45},
    )
    assert s["closed_edges"] == ["B1C1"]
    amb = s["ambulance"]
    assert amb is not None and amb["dispatch_s"] == 40 and amb["origin"] == "left0A0"
    assert s["scheduled"] == {"mission": None, "incident": None}
    assert s["history"] and s["history"][0][0] == 10  # every 10 simulated seconds
    a0 = {a["approach_id"]: a for a in s["approaches"]["A0"]}
    assert "left0A0" in a0 and {"count", "queue", "wait_s", "speed_mps"} <= set(a0["left0A0"])
    assert s["source_mode"] == "sumo" and s["effective_step"] == int(s["sim_time_s"])
    assert all(a["intervention"] for a in s["applied_controls"])


# ----- FR-16 invalid (ambulance without a route) -----------------------------------------------
def test_no_route_is_shown_as_invalid(client):
    _start(client)
    for e in ("C1C2", "B2C2"):  # both roads into C2: the exit C2top2 cannot be reached
        assert client.post("/api/roads/close", json={"edge_id": e}).status_code == 200
    assert client.post("/api/ambulance", json=MISSION).status_code == 200
    s = client.session.wait_for(lambda x: (x.get("ambulance") or {}).get("status") == "NO_ROUTE")
    w = [x for x in s["warnings"] if x["code"] == "invalid"]
    assert w and "NO_ROUTE" in w[0]["message"]


# ----- FR-16 + FR-20 fallback (operator fault injection) ---------------------------------------
@pytest.mark.skipif(not HAS_TORCH, reason="DQN needs PyTorch")
def test_rl_loss_fault_shows_fallback(client):
    _start(client, controller="dqn")
    assert "fallback" not in _codes(client.get("/api/state").json())
    r = client.post("/api/run/fault", json={"kind": "rl_loss"})
    assert r.status_code == 200 and r.json()["kind"] == "rl_loss"
    assert client.post("/api/run/fault", json={"kind": "rl_loss"}).status_code == 409
    t = r.json()["sim_time_s"]
    s = client.session.wait_for(lambda x: x["sim_time_s"] >= t + 30)
    fb = next(w for w in s["warnings"] if w["code"] == "fallback")
    assert fb["since_s"] >= t and s["controller_decisions"]["fallback"] > 0
    assert s["stats"]["safety_violations"] == 0  # holding the phase stays safe
    run_id = client.post("/api/run/stop").json()["run_id"]
    run = client.get(f"/api/runs/{client.tmp.as_posix()}/live/{run_id}")
    assert run.status_code == 200, run.text  # imported into the store when it stopped
    assert run.json()["metrics"]["controller_fallback_decisions"]["value"] > 0


def test_fault_needs_dqn_and_known_kind(client):
    _start(client)
    assert client.post("/api/run/fault", json={"kind": "rl_loss"}).status_code == 409
    assert client.post("/api/run/fault", json={"kind": "meteor"}).status_code == 422


# ----- FR-16 stale and disconnected (real process signals) -------------------------------------
@pytest.mark.skipif(sys.platform != "linux", reason="finds the SUMO process through /proc")
def test_frozen_sumo_makes_the_state_stale_then_killed_sumo_is_disconnected(client):
    _start(client, speed=20)
    pids = _sumo_pids(client.tmp)
    for pid in pids:
        os.kill(pid, signal.SIGSTOP)  # SUMO stops answering: the worker blocks inside TraCI
    try:
        time.sleep(3.0)
        s = client.get("/api/state").json()
        assert "stale" in _codes(s) and s["age_s"] > 2.0
        with client.websocket_connect("/ws/state") as ws:
            assert "stale" in _codes(ws.receive_json())
    finally:
        for pid in pids:
            os.kill(pid, signal.SIGKILL)  # then the connection is lost for good
    s = client.session.wait_for(lambda x: x["status"] == "error", timeout=60)
    assert "disconnected" in _codes(s)
    summary = json.loads((client.tmp / "live" / s["run_id"] / "summary.json").read_text())
    assert summary["termination"].startswith("error")
    runs = client.get("/api/runs", params={"source": "live"}).json()
    assert runs[0]["status"] == "failed"  # kept in the store, not dropped


# ----- store, analytics, export, perception endpoints ------------------------------------------
def test_store_runs_compare_and_export(client):
    s = client.get("/api/store/summary").json()
    assert s["runs"] > 300 and s["video_jobs"] == 40
    runs = client.get(
        "/api/runs", params={"study": "results/phase4/comparison", "profile": "heavy"}
    ).json()
    assert len(runs) == 15 and {r["arm"] for r in runs} == {"fixed_time", "adaptive", "dqn"}
    keys = [r["run_key"] for r in runs]
    c = client.post("/api/compare", json={"run_keys": keys, "metrics": ["waiting_time_mean_s"]})
    body = c.json()
    assert c.status_code == 200 and body["reference"] == "fixed_time" and body["warnings"] == []
    g = body["metrics"]["waiting_time_mean_s"]["groups"]
    assert g["dqn"]["n"] == 5 and g["dqn"]["ci95"] is not None
    assert client.post("/api/compare", json={"run_keys": ["nope"]}).status_code == 404
    assert client.post("/api/compare", json={"run_keys": keys, "group_by": "x"}).status_code == 422

    e = client.post("/api/export", json={"run_keys": keys, "format": "json"})
    assert e.status_code == 200 and "attachment" in e.headers["content-disposition"]
    assert e.json()["run_count"] == 15
    csv_ = client.post("/api/export", json={"run_keys": keys, "format": "csv"})
    assert csv_.headers["content-type"].startswith("text/csv")
    assert len(csv_.text.strip().splitlines()) == 16
    one = client.get(f"/api/runs/{keys[0]}").json()
    assert one["config"]["profile"] == "heavy" and one["metrics"]
    assert client.get("/api/runs/results/nope").status_code == 404


def test_perception_endpoints_and_file_guard(client):
    jobs = client.get("/api/perception/jobs").json()
    assert len(jobs) == 40 and all(j["status"] == "processed" for j in jobs)
    job = client.get("/api/perception/jobs/detrac/MVI_40714").json()
    assert job["model_sha256"] and job["artifacts"]
    obs = client.get(
        "/api/perception/jobs/detrac/MVI_40714/observations", params={"name": "queue_proxy"}
    ).json()
    assert obs and {o["name"] for o in obs} == {"queue_proxy"}
    frame = next(a["uri"] for a in job["artifacts"] if a["type"] == "frame")
    r = client.get(f"/api/files/{frame}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    for bad in ("pyproject.toml", "../etc/passwd", "results/vision/tracking/summary.json"):
        assert client.get(f"/api/files/{bad}").status_code == 404
