"""Task 2.1: pressure controller scores phases per Eq 5.2 and respects min/max green, max red."""

from dataclasses import replace

import pytest

from manzil.control.adaptive import AdaptiveController, AdaptiveParams
from manzil.control.safety import SafetyConfig
from manzil.experiments.runner import RunConfig, run
from manzil.sim.contracts import (
    SCHEMA_VERSION,
    ApproachState,
    LaneState,
    SignalState,
    SourceMode,
    TrafficSnapshot,
)

SAFETY = SafetyConfig()
TLS = "B1"


def snapshot(model, t, halting=None, waits=None):
    """A hand-made snapshot: ``halting`` lane -> queue, ``waits`` approach -> wait (s)."""
    halting, waits = halting or {}, waits or {}
    lanes = {}
    for x in model.intersections.values():
        for lane in (*x.incoming_lanes, *x.outgoing_lanes):
            q = halting.get(lane, 0)
            lanes[lane] = LaneState(lane, q, q, 0.0, 0.0, 0.0)
    approaches = {
        tls: tuple(
            ApproachState(tls, a.edge_id, 0, 0, waits.get(a.edge_id, 0.0), None, 0.0)
            for a in x.approaches
        )
        for tls, x in model.intersections.items()
    }
    return TrafficSnapshot(SCHEMA_VERSION, SourceMode.SUMO, 0.0, int(t), float(t), int(t),
                           model.network_id, lanes, {}, 0, 0, 0, approaches)  # fmt: skip


def signal(phase, elapsed):
    return {TLS: SignalState(TLS, "manzil", phase, elapsed, "", (0, 1))}


@pytest.fixture
def ctrl(grid_model):
    c = AdaptiveController(AdaptiveParams(alpha=1.0, beta=0.0, max_green_s=60, max_red_s=90))
    c.reset(grid_model, SAFETY)
    return c


def lanes_of_phase(model, phase):
    x = model.intersections[TLS]
    links = [x.links[i] for i in sorted(x.green_phases[phase].green_links())]
    return sorted({lk.from_lane for lk in links}), sorted({lk.to_lane for lk in links})


def test_score_follows_equation_5_2(grid_model, ctrl):
    in0, out0 = lanes_of_phase(grid_model, 0)
    _, out1 = lanes_of_phase(grid_model, 1)
    exit_lane = out0[0]
    snap = snapshot(grid_model, 20, {in0[0]: 5, in0[1]: 3, exit_lane: 2})
    # Exit lanes can be fed by both phases (a right turn and a through movement), so the
    # downstream queue lowers every phase that feeds it.
    expected1 = -2 if exit_lane in out1 else 0
    assert ctrl.scores(TLS, snap) == [5 + 3 - 2, expected1]
    ctrl.params = replace(ctrl.params, alpha=0.5, beta=0.1)
    x = grid_model.intersections[TLS]
    edge0 = x.links[sorted(x.green_phases[0].green_links())[0]].from_edge
    snap = snapshot(grid_model, 20, {in0[0]: 5, exit_lane: 2}, {edge0: 40.0})
    assert ctrl.scores(TLS, snap) == pytest.approx([5 - 0.5 * 2 + 0.1 * 40, 0.5 * expected1])


def test_switches_to_higher_pressure_after_min_green(grid_model, ctrl):
    in1, _ = lanes_of_phase(grid_model, 1)
    snap = snapshot(grid_model, 20, {in1[0]: 6})
    assert ctrl.decide(snap, signal(0, 5.0)) == []  # before min green: no request
    (req,) = ctrl.decide(snap, signal(0, 12.0))
    assert req.requested_phase == 1 and req.reason.startswith("pressure")


def test_extends_when_current_phase_is_preferred(grid_model, ctrl):
    in0, _ = lanes_of_phase(grid_model, 0)
    (req,) = ctrl.decide(snapshot(grid_model, 20, {in0[0]: 6}), signal(0, 15.0))
    assert req.requested_phase == 0 and req.reason.startswith("extend")


def test_max_green_forces_a_switch(grid_model, ctrl):
    in0, _ = lanes_of_phase(grid_model, 0)
    (req,) = ctrl.decide(snapshot(grid_model, 70, {in0[0]: 9}), signal(0, 60.0))
    assert req.requested_phase == 1 and req.reason.startswith("max_green")


def test_max_red_promotion(grid_model):
    c = AdaptiveController(AdaptiveParams(beta=0.0, max_green_s=200, max_red_s=40))
    c.reset(grid_model, SAFETY)
    in0, _ = lanes_of_phase(grid_model, 0)
    busy = {in0[0]: 9}
    # Phase 0 keeps winning on pressure, so it is extended ...
    (req,) = c.decide(snapshot(grid_model, 20, busy), signal(0, 20.0))
    assert req.reason.startswith("extend")
    # ... until phase 1 has been red for max_red - clearance (40 - 5 = 35 s).
    (req,) = c.decide(snapshot(grid_model, 35, busy), signal(0, 35.0))
    assert req.requested_phase == 1 and req.reason.startswith("max_red")


def test_switch_margin_adds_hysteresis(grid_model):
    c = AdaptiveController(AdaptiveParams(beta=0.0, switch_margin=3.0))
    c.reset(grid_model, SAFETY)
    in1, _ = lanes_of_phase(grid_model, 1)
    (req,) = c.decide(snapshot(grid_model, 20, {in1[0]: 3}), signal(0, 15.0))
    assert req.requested_phase == 0  # 3 is not more than 0 + margin 3
    (req,) = c.decide(snapshot(grid_model, 21, {in1[0]: 4}), signal(0, 16.0))
    assert req.requested_phase == 1


def test_bad_params_rejected(grid_model):
    with pytest.raises(ValueError):
        AdaptiveParams(beta=-1)
    with pytest.raises(ValueError):
        AdaptiveController(AdaptiveParams(max_green_s=5)).reset(grid_model, SAFETY)


def test_full_run_is_safe_and_explained(tmp_path):
    r = run(RunConfig(controller="adaptive", profile="uneven", seed=0, warmup_s=100,
                      measure_s=500), tmp_path)  # fmt: skip
    assert r.manifest["termination"] == "completed"
    assert r.violations == [] and r.metrics["safety_violations"] == 0
    assert r.metrics["controller_decisions"].get("pressure", 0) > 0
    assert r.manifest["controller"]["controller"] == "adaptive"
    applied = (tmp_path / "applied_controls.csv").read_text()
    assert "pressure S=[" in applied  # the explanation is recorded with each switch


def test_min_hold_delays_the_first_decision(grid_model):
    c = AdaptiveController(AdaptiveParams(beta=0.0, min_hold_s=20.0))
    c.reset(grid_model, SAFETY)
    in1, _ = lanes_of_phase(grid_model, 1)
    snap = snapshot(grid_model, 20, {in1[0]: 9})
    assert c.decide(snap, signal(0, 15.0)) == []  # past min green 10 s, but within hold 20 s
    (req,) = c.decide(snap, signal(0, 20.0))
    assert req.requested_phase == 1
