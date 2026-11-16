"""W4 corridor completion: downstream check, bounded compensation, sublane give-way."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from manzil.control.safety import SafetyConfig, SafetyFilter, SafetyMonitor
from manzil.corridor.coordinator import CorridorCoordinator, CorridorParams, _Request
from manzil.experiments.emergency import MissionConfig
from manzil.experiments.emergency_w4_study import ARMS, STRESS, V2
from manzil.experiments.runner import RunConfig, run
from manzil.routing.graph import RoutingGraph
from manzil.sim.adapter import SimulationAdapter
from manzil.sim.contracts import ApproachState, EdgeState, Owner

TLS = "B1"
SAFETY = SafetyConfig(min_green_s=10, yellow_s=3, all_red_s=2, corridor_min_green_s=5)


def _coordinator(grid_model, **params):
    f = SafetyFilter(grid_model, SAFETY)
    f.reset()
    c = CorridorCoordinator(grid_model, RoutingGraph(grid_model), f, CorridorParams(**params))
    return c, f


def _snap(t, approaches=None, edges=None):
    return SimpleNamespace(sim_time_s=float(t), effective_step=int(t),
                           approaches=approaches or {}, edges=edges or {})  # fmt: skip


# ----- configuration --------------------------------------------------------------------------
def test_defaults_are_corridor_v2():
    """Every W4 addition is off by default, so earlier results are unchanged."""
    m = MissionConfig()
    assert (m.downstream, m.compensation, m.sublane) == ("off", False, False)
    p = CorridorParams()
    assert (p.downstream, p.compensation) == ("off", False)
    assert ARMS["v2"] == V2 and V2.corridor_min_green_s == 5.0


def test_bad_w4_settings_rejected():
    with pytest.raises(ValueError):
        CorridorParams(downstream="sometimes")
    with pytest.raises(ValueError):
        CorridorParams(downstream_occupancy=0)
    with pytest.raises(ValueError):
        CorridorParams(compensation_max_s=0)
    assert MissionConfig(downstream="x").validate()
    assert MissionConfig(sublane=True, lateral_resolution_m=0).validate()


# ----- downstream check -----------------------------------------------------------------------
def test_exit_blocked_rule(grid_model):
    c, _ = _coordinator(grid_model)
    edge = grid_model.net.getEdge("B1C1")
    storage = edge.getLaneNumber() * edge.getLength() / 7.5  # about 50 vehicles
    full = int(storage * 0.8)
    assert c.exit_blocked(_snap(0, edges={"B1C1": EdgeState("B1C1", full, 3, 0.5)}), "B1C1")
    # Full but moving (nobody halting), or only half full: not blocked.
    assert not c.exit_blocked(_snap(0, edges={"B1C1": EdgeState("B1C1", full, 0, 8.0)}), "B1C1")
    half = int(storage * 0.5)
    assert not c.exit_blocked(_snap(0, edges={"B1C1": EdgeState("B1C1", half, 9, 0.1)}), "B1C1")


def test_defer_is_bounded(grid_model):
    c, _ = _coordinator(grid_model, downstream="defer", downstream_max_defer_s=20)
    req = _Request(TLS, "A1B1", "B1C1", 1, 1)
    blocked = {"B1C1": EdgeState("B1C1", 60, 10, 0.0)}
    assert c._defer(req, _snap(100, edges=blocked), 100, 100, 5.0)
    assert c._defer(req, _snap(119, edges=blocked), 119, 119, 1.0)
    assert not c._defer(req, _snap(120, edges=blocked), 120, 120, 0.0)  # 20 s: activate anyway
    assert c.deferrals == 1 and c.events[0]["state"] == "DOWNSTREAM_DEFER"
    # A flushed request is never deferred, and "flush" mode never defers.
    assert not c._defer(_Request(TLS, "A1B1", "B1C1", 1, 1, flush=True), _snap(0, edges=blocked),
                        0, 0, 0.0)  # fmt: skip
    c2, _ = _coordinator(grid_model, downstream="flush")
    assert not c2._defer(_Request(TLS, "A1B1", "B1C1", 1, 1), _snap(0, edges=blocked), 0, 0, 0.0)


# ----- bounded compensation -------------------------------------------------------------------
def test_compensation_serves_denied_phase_then_returns_control(grid_model):
    x = grid_model.intersections[TLS]
    amb_phase, other = 0, 1
    denied = {lk.from_edge for lk in x.links
              if x.green_phases[other].state[lk.index] in "Gg"
              and x.green_phases[amb_phase].state[lk.index] not in "Gg"}  # fmt: skip
    apps = {TLS: tuple(ApproachState(TLS, a.edge_id, 6, 5 if a.edge_id in denied else 0,
                                     0.0, None, 0.0) for a in x.approaches)}  # fmt: skip
    c, f = _coordinator(grid_model, compensation=True, compensation_max_s=20)
    m = SafetyMonitor(grid_model, SAFETY)
    f.set_owner(TLS, Owner.CORRIDOR, 0, 0)
    m.observe(0, f.states(), f.owners())
    req = _Request(TLS, "A1B1", "B1C1", amb_phase, 1, activated_s=0.0)
    c._release(req, 12, 12, "PASSAGE", _snap(12, apps))
    assert f.owner(TLS) is Owner.CORRIDOR  # kept for the compensation plan
    assert c.status()[TLS] == "COMPENSATION"
    released = None
    for t in range(12, 60):
        c._compensate(_snap(t, apps))
        f.tick(t, t)
        m.observe(t, f.states(), f.owners())
        if released is None and f.owner(TLS) is Owner.NORMAL:
            released = t
    # Switch at once (green 0 had its full 10 s), 3 s yellow + 2 s all-red, phase 1 green from
    # 17 s, served for as long as the junction was held (12 s), then normal control again.
    assert released == 29
    assert c.compensation_green_s == [12.0]
    assert f.showing(TLS) == other
    assert m.violations == []


def test_compensation_waits_for_full_min_green_and_skips_empty(grid_model):
    x = grid_model.intersections[TLS]
    c, f = _coordinator(grid_model, compensation=True)
    f.set_owner(TLS, Owner.CORRIDOR, 0, 0)
    empty = {TLS: tuple(ApproachState(TLS, a.edge_id, 0, 0, 0.0, None, 0.0)
                        for a in x.approaches)}  # fmt: skip
    # Nobody waits for another phase: plain release, as in v2.
    c._release(_Request(TLS, "A1B1", "B1C1", 0, 1, activated_s=0.0), 3, 3, "PASSAGE",
               _snap(3, empty))  # fmt: skip
    assert f.owner(TLS) is Owner.NORMAL and c.compensating == 0
    # With a queue, a green that started 4 s ago is kept to the normal 10 s (no truncation).
    full = {TLS: tuple(ApproachState(TLS, a.edge_id, 6, 4, 0.0, None, 0.0)
                       for a in x.approaches)}  # fmt: skip
    f.set_owner(TLS, Owner.CORRIDOR, 4, 4)
    c._release(_Request(TLS, "A1B1", "B1C1", 0, 1, activated_s=0.0), 4, 4, "PASSAGE",
               _snap(4, full))  # fmt: skip
    for t in range(4, 10):
        c._compensate(_snap(t, full))
        f.tick(t, t)
        assert f.mode(TLS) == "green" and f.showing(TLS) == 0
    c._compensate(_snap(10, full))
    f.tick(10, 10)
    assert f.mode(TLS) == "yellow"


# ----- sublane model --------------------------------------------------------------------------
def test_sublane_option_reaches_sumo(grid_model, light_cfg):
    sim = SimulationAdapter(grid_model)
    sim.sublane_model(0.8)
    sim.start(["-c", str(light_cfg), "--no-step-log", "true"])
    try:
        assert float(sim._conn.simulation.getOption("lateral-resolution")) == 0.8
        with pytest.raises(RuntimeError):
            sim.sublane_model(0.8)
    finally:
        sim.stop()


# ----- real SUMO runs -------------------------------------------------------------------------
SHORT = {"profile": "heavy", "seed": 10, "warmup_s": 900.0, "measure_s": 600.0}


@pytest.fixture(scope="module")
def comp_run(tmp_path_factory):
    d = tmp_path_factory.mktemp("w4comp")
    mission = replace(ARMS["comp"], downstream="both")
    r = run(RunConfig(**SHORT, mission=mission, label="comp"), d)
    return r, json.loads((d / "mission.json").read_text())


def test_compensation_run_keeps_decision_11_and_safety(comp_run):
    r, rec = comp_run
    m = r.metrics
    assert m["mission_status"] == "ARRIVED"
    assert m["amb_signal_crossings"] >= 4 and m["amb_red_crossings"] == 0
    assert m["safety_violations"] == 0 and r.violations == []
    assert m["collisions"] == 0
    assert m["compensations"] >= 1 and m["compensation_unfinished"] == 0
    states = [e["state"] for e in rec["corridor_events"]]
    assert states.count("COMPENSATION") == states.count("COMPENSATION_DONE")


def test_no_compensation_after_cancellation(grid_model):
    x = grid_model.intersections[TLS]
    full = {TLS: tuple(ApproachState(TLS, a.edge_id, 6, 4, 0.0, None, 0.0)
                       for a in x.approaches)}  # fmt: skip
    c, f = _coordinator(grid_model, compensation=True)
    f.set_owner(TLS, Owner.CORRIDOR, 0, 0)
    c._cancel(_Request(TLS, "A1B1", "B1C1", 0, 1, activated_s=0.0), 70, 70, "timeout",
              _snap(70, full))  # fmt: skip
    assert f.owner(TLS) is Owner.NORMAL and c.compensating == 0


def test_give_way_with_sublane_still_obeys_red(tmp_path):
    """Decision 11 holds with the bluelight device + sublane model. (Collisions with this arm
    are a measured result, reported in results/fyp2/corridor/, not asserted here.)"""
    r = run(RunConfig(**SHORT, mission=ARMS["giveway_sl"], label="gw"), tmp_path)
    m = r.metrics
    assert m["amb_speed_mode"] == 31  # bluelight device's speed mode 7 undone
    assert m["amb_signal_crossings"] >= 4 and m["amb_red_crossings"] == 0
    assert m["safety_violations"] == 0
    rec = json.loads((tmp_path / "mission.json").read_text())
    assert rec["config"]["sublane"] and rec["config"]["give_way"]


def test_stress_case_triggers_downstream_check(tmp_path):
    mission = replace(ARMS["ds_both"], **STRESS)
    cfg = RunConfig(profile="heavy", seed=10, warmup_s=900.0, measure_s=900.0, mission=mission)
    r = run(cfg, tmp_path)
    m = r.metrics
    assert m["downstream_deferrals"] + m["downstream_flushes"] >= 1
    assert m["safety_violations"] == 0 and m["amb_red_crossings"] == 0
    events = json.loads((tmp_path / "mission.json").read_text())["corridor_events"]
    for e in events:  # a deferred junction activates within downstream_max_defer_s
        if e["state"] == "DOWNSTREAM_DEFER":
            act = [a for a in events if a["tls"] == e["tls"] and a["state"] == "SAFE_TRANSITION"
                   and a["time_s"] >= e["time_s"]]  # fmt: skip
            assert not act or act[0]["time_s"] - e["time_s"] <= 20.0


def test_comp_exit_waits_until_ambulance_left_exit(tmp_path):
    r = run(RunConfig(**SHORT, mission=ARMS["comp_exit"], label="comp_exit"), tmp_path)
    m = r.metrics
    assert m["mission_status"] == "ARRIVED" and m["safety_violations"] == 0
    assert m["amb_red_crossings"] == 0 and m["compensations"] >= 1
    rec = json.loads((tmp_path / "mission.json").read_text())
    events, crossings = rec["corridor_events"], rec["signal_crossings"]
    for e in (e for e in events if e["state"] == "COMPENSATION"):
        passage = max(p["time_s"] for p in events
                      if p["tls"] == e["tls"] and p["state"] == "PASSAGE"
                      and p["time_s"] <= e["time_s"])  # fmt: skip
        # Compensation starts after the ambulance crossed the next stop line (or arrived).
        later = [c["time_s"] for c in crossings if c["time_s"] > passage]
        assert not later or e["time_s"] >= later[0]
