"""Tasks 3.3-3.5 in real SUMO: dispatch, closure rerouting, corridor lifecycle and safety."""

import json
from collections import defaultdict

import pytest

from manzil.experiments.emergency import MissionConfig
from manzil.experiments.runner import RunConfig, run

SHORT = {"profile": "medium", "seed": 0, "warmup_s": 900.0, "measure_s": 600.0}
ORDER = ["REQUESTED", "SAFE_TRANSITION", "ACTIVE_PRIORITY", "PASSAGE", "RECOVERY", "IDLE"]


def mission_run(tmp_path, **mission):
    r = run(RunConfig(**SHORT, mission=MissionConfig(**mission)), tmp_path)
    return r, json.loads((tmp_path / "mission.json").read_text())


@pytest.fixture(scope="module")
def corridor_run(tmp_path_factory):
    return mission_run(tmp_path_factory.mktemp("corr"), corridor=True)


def test_ambulance_reaches_destination(corridor_run):
    r, rec = corridor_run
    m = r.metrics
    assert m["mission_status"] == "ARRIVED"
    assert m["driven_route"][0] == "left0A0" and m["driven_route"][-1] == "C2top2"
    assert m["amb_travel_time_s"] >= m["amb_free_flow_time_s"] > 0
    assert rec["route_versions"][0]["trigger"] == "dispatch"


def test_corridor_lifecycle_order_and_safety(corridor_run):
    r, rec = corridor_run
    assert r.metrics["safety_violations"] == 0 and r.violations == []
    by_tls = defaultdict(list)
    for e in rec["corridor_events"]:
        by_tls[e["tls"]].append(e["state"])
    assert by_tls, "the corridor never acted"
    for tls, states in by_tls.items():
        assert states == ORDER, (tls, states)  # full Algorithm 2 cycle, in order
    assert r.metrics["corridor_served"] == len(by_tls)
    assert r.metrics["corridor_held_requests"] > 0  # normal control waited while owned


def test_corridor_helps_the_ambulance(corridor_run, tmp_path):
    off, _ = mission_run(tmp_path, corridor=False)
    on = corridor_run[0]
    assert on.metrics["amb_travel_time_s"] < off.metrics["amb_travel_time_s"]
    assert on.metrics["amb_stops"] <= off.metrics["amb_stops"]


def test_closure_triggers_new_route_version_and_cancels_priority(tmp_path):
    r, rec = mission_run(
        tmp_path, corridor=True, incident="closure", incident_edge="C0C1", incident_s=1210.0
    )
    m = r.metrics
    assert m["mission_status"] == "ARRIVED"
    assert m["route_revisions"] >= 1 and m["revision_triggers"][0] == "closure"
    assert "C0C1" not in m["driven_route"]
    versions = [v["route_version"] for v in rec["route_versions"]]
    assert versions == sorted(versions) == list(range(1, len(versions) + 1))
    cancelled = [e for e in rec["corridor_events"] if e["state"] == "CANCELLED"]
    assert any(e["reason"].startswith("route_v2") for e in cancelled)
    assert m["safety_violations"] == 0 and m["teleports"] == 0


def test_priority_timeout_releases_safely(tmp_path):
    r, rec = mission_run(tmp_path, corridor=True, max_priority_s=2.0)
    assert r.metrics["corridor_timeouts"] > 0
    assert r.metrics["safety_violations"] == 0
    assert r.metrics["mission_status"] == "ARRIVED"


def test_bad_mission_config_rejected(tmp_path):
    with pytest.raises(ValueError, match="invalid run config"):
        run(RunConfig(**SHORT, mission=MissionConfig(routing="teleport")), tmp_path)
    with pytest.raises(ValueError, match="not in the routing graph"):
        run(RunConfig(**SHORT, mission=MissionConfig(origin="nowhere")), tmp_path)
