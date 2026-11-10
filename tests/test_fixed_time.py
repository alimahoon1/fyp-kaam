"""Task 1.6: fixed-time controller follows its declared cycle exactly through the safety filter."""

import csv

import pytest

from manzil.control.fixed_time import JunctionPlan, SignalTiming
from manzil.control.safety import SafetyConfig
from manzil.experiments.runner import RunConfig, run
from manzil.scenarios.demand import DEFAULT_NET, PROFILES

SIGNALS = DEFAULT_NET.parent / "signals.json"


def test_schedule_windows():
    plan = JunctionPlan((30.0, 20.0))
    clearance = 5.0
    assert plan.cycle_s(clearance) == 60.0
    assert [plan.phase_at(t, clearance) for t in (0, 29, 30, 34, 35, 54, 55, 59, 60)] == [
        0, 0, 1, 1, 1, 1, 0, 0, 0,
    ]  # fmt: skip
    shifted = JunctionPlan((30.0, 20.0), offset_s=35.0)
    assert shifted.phase_at(0, clearance) == 1


def test_signal_file_loads_and_every_profile_has_a_plan(grid_model):
    timing = SignalTiming.load(SIGNALS)
    assert timing.safety == SafetyConfig(min_green_s=10, yellow_s=3, all_red_s=2, max_red_s=90)
    for profile in PROFILES:
        name = timing.resolve_plan("auto", profile)
        ctrl = timing.fixed_time_controller(grid_model, name)
        ctrl.reset(grid_model, timing.safety)  # validates against min green


def test_plan_below_min_green_is_rejected(grid_model):
    timing = SignalTiming.load(SIGNALS)
    ctrl = timing.fixed_time_controller(grid_model, "equal")
    ctrl.plans = {t: JunctionPlan((5.0, 35.0)) for t in ctrl.plans}
    with pytest.raises(ValueError, match="minimum green"):
        ctrl.reset(grid_model, timing.safety)


def test_phase_zero_is_north_south_everywhere(grid_model):
    """signals.json relies on this when it gives the uneven plan a longer phase 0."""
    for x in grid_model.intersections.values():
        ns = {a.edge_id: a.north_south for a in x.approaches}
        for phase, expected in ((0, True), (1, False)):
            served = {ns[x.links[i].from_edge] for i in x.green_phases[phase].green_links()}
            assert served == {expected}


def test_full_run_follows_declared_cycle(tmp_path):
    cfg = RunConfig(profile="uneven", seed=0, plan="uneven", warmup_s=100, measure_s=500)
    result = run(cfg, tmp_path)
    assert result.manifest["termination"] == "completed"
    assert result.violations == []
    durations = {}
    rows = list(csv.DictReader((tmp_path / "signal_events.csv").open()))
    by_tls = {}
    for r in rows:
        by_tls.setdefault(r["intersection_id"], []).append(r)
    for evs in by_tls.values():
        for a, b in zip(evs, evs[1:], strict=False):
            key = (a["kind"], a["phase_id"])
            durations.setdefault(key, set()).add(float(b["sim_time_s"]) - float(a["sim_time_s"]))
    assert durations[("yellow", "")] == {3.0}
    assert durations[("all_red", "")] == {2.0}
    assert durations[("green", "0")] == {45.0}
    assert durations[("green", "1")] == {25.0}
