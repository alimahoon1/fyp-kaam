"""Task 3.7: corridor improvements, the route-index bug fix and the red-light checks."""

import json

import pytest

from manzil.control.safety import CORRIDOR_ID, SafetyConfig, SafetyFilter, SafetyMonitor
from manzil.corridor.coordinator import CorridorCoordinator
from manzil.experiments.emergency import STOP_GROUPS, MissionConfig
from manzil.experiments.runner import RunConfig, run
from manzil.routing.graph import RoutePlan, RoutingGraph
from manzil.sim.contracts import ControlRequest, Owner, VehicleState

TLS = "B1"
SHORT = {"profile": "heavy", "seed": 0, "warmup_s": 900.0, "measure_s": 600.0}


# ----- the route-index bug (found in task 3.7) -----------------------------------------------
def test_upcoming_uses_plan_position_not_sumo_route_index(grid_model):
    """After a reroute SUMO keeps driven edges in its route, so its index is ahead of the plan.

    Route v2 starts at the current edge A0A1; SUMO reports index 1 (left0A0 is still in its
    route). The junction right ahead (A1) must still be the first one requested.
    """
    c = CorridorCoordinator(grid_model, RoutingGraph(grid_model), SafetyFilter(grid_model))
    plan = RoutePlan("m1", 2, ("A0A1", "A1B1", "B1C1", "C1C2", "C2top2"), 0.0, 0, "closure", 0)
    amb = VehicleState("amb", "A0A1", "A0A1_0", 50.0, 10.0, 0.0, route_index=1)
    assert [u[0] for u in c._upcoming(plan, amb)] == ["A1", "B1", "C1", "C2"]
    # Inside junction A1 (last normal edge A0A1): A1 has been passed.
    c._last_edge = "A0A1"
    inside = VehicleState("amb", ":A1_8", ":A1_8_0", 1.0, 10.0, 0.0, route_index=1)
    assert [u[0] for u in c._upcoming(plan, inside)] == ["B1", "C1", "C2"]


# ----- emergency truncation of minimum green -------------------------------------------------
TRUNC = SafetyConfig(min_green_s=10, yellow_s=3, all_red_s=2, corridor_min_green_s=5)


def test_truncation_only_for_the_corridor_and_never_clearance(grid_model):
    x = grid_model.intersections[TLS]
    f = SafetyFilter(grid_model, TRUNC)
    f.reset()
    m = SafetyMonitor(grid_model, TRUNC)
    m.observe(0, f.states(), f.owners())
    # Normal control still needs the full 10 s.
    rec = f.submit(ControlRequest("test", TLS, 1, 6, "normal"), 6, 6)
    assert rec.safety_intervention == "min_green_hold"
    # The corridor may switch after 5 s, but not before.
    f.set_owner(TLS, Owner.CORRIDOR, 6, 6)
    f2 = SafetyFilter(grid_model, TRUNC)
    f2.reset()
    f2.set_owner(TLS, Owner.CORRIDOR, 0, 0)
    assert f2.submit(ControlRequest(CORRIDOR_ID, TLS, 1, 4, "c"), 4, 4).safety_intervention == (
        "min_green_hold"
    )
    rec = f.submit(ControlRequest(CORRIDOR_ID, TLS, 1, 6, "corridor"), 6, 6)
    assert rec.safety_intervention == "corridor_min_green_truncated"
    shown = {}
    for t in range(6, 13):
        shown[t] = f.tick(t, t)[TLS]
        m.observe(t, f.states(), f.owners())
    assert all("y" in shown[t] for t in (6, 7, 8))  # yellow 3 s kept
    assert shown[9] == shown[10] == "r" * x.num_links  # all-red 2 s kept
    assert shown[11] == x.green_phases[1].state
    assert m.violations == []


def test_monitor_flags_truncation_without_corridor_ownership(grid_model):
    from manzil.control.safety import all_red_state, yellow_state

    x = grid_model.intersections[TLS]
    g0, g1 = x.green_phases[0].state, x.green_phases[1].state
    m = SafetyMonitor(grid_model, TRUNC)
    m.observe(0, {TLS: g0}, {TLS: Owner.NORMAL})
    m.observe(6, {TLS: yellow_state(g0, g1)}, {TLS: Owner.NORMAL})  # 6 s green, normal owner
    assert any("left after" in v for v in m.violations)
    m2 = SafetyMonitor(grid_model, TRUNC)
    m2.observe(0, {TLS: g0}, {TLS: Owner.CORRIDOR})
    m2.observe(4, {TLS: yellow_state(g0, g1)}, {TLS: Owner.CORRIDOR})  # below even 5 s
    m2.observe(7, {TLS: all_red_state(g0, g1)}, {TLS: Owner.CORRIDOR})
    assert any("left after" in v for v in m2.violations)


def test_bad_truncation_config_rejected():
    with pytest.raises(ValueError):
        SafetyConfig(min_green_s=10, corridor_min_green_s=12)
    with pytest.raises(ValueError):
        SafetyConfig(min_green_s=10, corridor_min_green_s=0)


# ----- real SUMO: diagnostics, give-way and Decision 11 --------------------------------------
@pytest.fixture(scope="module")
def give_way_run(tmp_path_factory):
    d = tmp_path_factory.mktemp("gw")
    mission = MissionConfig(corridor=True, give_way=True, corridor_min_green_s=5.0)
    r = run(RunConfig(**SHORT, mission=mission), d)
    return r, json.loads((d / "mission.json").read_text())


def test_give_way_ambulance_still_stops_at_red(give_way_run):
    r, rec = give_way_run
    m = r.metrics
    assert m["mission_status"] == "ARRIVED"
    assert m["amb_speed_mode"] == 31  # the bluelight device's 7 (runs reds) was undone
    assert m["amb_signal_crossings"] >= 4  # one per signalised junction on the route
    assert m["amb_red_crossings"] == 0
    assert all(c["state"] not in "rR" for c in rec["signal_crossings"])
    assert m["safety_violations"] == 0 and r.violations == []


def test_stop_reasons_add_up(give_way_run):
    m = give_way_run[0].metrics
    assert sum(m["amb_stop_reasons"].values()) == m["amb_waiting_s"]
    groups = {g for g in STOP_GROUPS.values()}
    assert sum(m[f"amb_stopped_{g}_s"] for g in groups) == m["amb_waiting_s"]
    assert m["cross_street_approaches"] > 0 and m["cross_street_wait_veh_s"] >= 0


def test_plain_ambulance_never_crosses_on_red(tmp_path):
    m = run(RunConfig(**SHORT, mission=MissionConfig(corridor=False)), tmp_path).metrics
    assert m["amb_signal_crossings"] >= 4 and m["amb_red_crossings"] == 0
    assert m["amb_speed_mode"] == 31
    assert m["amb_stopped_red_no_corridor_s"] + m["amb_stopped_queue_s"] > 0
