"""Task 1.5: the safety filter enforces min green, yellow, all-red; no conflicting greens ever."""

import random
from dataclasses import dataclass

import pytest

from manzil.control.safety import (
    SafetyConfig,
    SafetyFilter,
    SafetyMonitor,
    all_red_state,
    yellow_state,
)
from manzil.sim.adapter import QUIET_ARGS, SimulationAdapter
from manzil.sim.contracts import ControlRequest

CFG = SafetyConfig(min_green_s=10, yellow_s=3, all_red_s=2)
TLS = "B1"


def req(phase, step=0, tls=TLS):
    return ControlRequest("test", tls, phase, step, "unit test")


@pytest.fixture
def filt(grid_model):
    f = SafetyFilter(grid_model, CFG)
    f.reset()
    return f


def test_transition_states():
    assert yellow_state("GGgrr", "rrrGG") == "yyyrr"
    assert all_red_state("GGgrr", "rrrGG") == "rrrrr"
    # A link green in both phases keeps its green through the change.
    assert yellow_state("GGrr", "GrGG") == "Gyrr"
    assert all_red_state("GGrr", "GrGG") == "Grrr"


def test_switch_held_until_min_green(filt):
    rec = filt.submit(req(1), now=5, step=5)
    assert rec.safety_intervention == "min_green_hold"
    assert rec.applied_phase == 0
    assert filt.signal_state(TLS, 5).phase_id == 0


def test_full_switch_sequence(filt, grid_model):
    x = grid_model.intersections[TLS]
    rec = filt.submit(req(1), now=10, step=10)
    assert rec.safety_intervention == "none" and rec.applied_phase == 1
    shown = {}
    for t in range(10, 17):
        shown[t] = filt.tick(t, t)[TLS]
    assert all("y" in shown[t] for t in (10, 11, 12))  # yellow for exactly 3 s
    assert shown[13] == shown[14] == "r" * x.num_links  # all-red for 2 s
    assert shown[15] == x.green_phases[1].state  # then the new green
    assert filt.signal_state(TLS, 15).phase_id == 1


def test_request_during_transition_cannot_change_it(filt):
    filt.submit(req(1), now=10, step=10)
    filt.tick(10, 10)
    rec = filt.submit(req(0), now=11, step=11)
    assert rec.safety_intervention == "in_transition" and rec.applied_phase == 1
    assert filt.submit(req(1), now=11, step=11) is None  # same target: just a hold


def test_invalid_phase_rejected(filt):
    rec = filt.submit(req(7), now=20, step=20)
    assert rec.safety_intervention == "invalid_phase"
    assert rec.applied_phase == 0


def test_hold_request_is_not_logged(filt):
    assert filt.submit(req(0), now=20, step=20) is None
    assert filt.hold_count == 1 and filt.applied == []


# ----- the monitor catches unsafe sequences ------------------------------------------------
def _monitor(grid_model):
    return SafetyMonitor(grid_model, CFG)


def test_monitor_flags_conflicting_greens(grid_model):
    m = _monitor(grid_model)
    m.observe(0, {TLS: "G" * 16})
    assert any("conflicting" in v for v in m.violations)


def test_monitor_flags_green_to_red_without_yellow(grid_model):
    x = grid_model.intersections[TLS]
    m = _monitor(grid_model)
    m.observe(0, {TLS: x.green_phases[0].state})
    m.observe(20, {TLS: x.green_phases[1].state})
    assert any("without yellow" in v for v in m.violations)


def test_monitor_flags_short_yellow_and_short_green(grid_model):
    x = grid_model.intersections[TLS]
    g0, g1 = x.green_phases[0].state, x.green_phases[1].state
    m = _monitor(grid_model)
    m.observe(0, {TLS: g0})
    m.observe(4, {TLS: yellow_state(g0, g1)})  # green lasted only 4 s
    m.observe(5, {TLS: all_red_state(g0, g1)})  # yellow lasted only 1 s
    assert any("left after" in v for v in m.violations)
    assert any("yellow too short" in v for v in m.violations)


# ----- property test: a random controller can never produce an unsafe state ----------------
@dataclass
class RandomController:
    rng: random.Random

    def requests(self, network, step):
        out = []
        for tls, x in network.intersections.items():
            if self.rng.random() < 0.3:
                phase = self.rng.randrange(-1, len(x.green_phases) + 1)  # includes invalid ids
                out.append(ControlRequest("random", tls, phase, step, "random"))
        return out


def test_random_requests_never_unsafe_without_sumo(grid_model):
    f = SafetyFilter(grid_model, CFG)
    m = SafetyMonitor(grid_model, CFG)
    ctrl = RandomController(random.Random(1))
    m.observe(0, f.reset())
    for t in range(1, 5000):
        for r in ctrl.requests(grid_model, t):
            f.submit(r, t, t)
        m.observe(t, f.tick(t, t))
    assert m.violations == []
    kinds = {a.safety_intervention for a in f.applied}
    assert {"none", "min_green_hold", "in_transition", "invalid_phase"} <= kinds


def test_random_requests_never_unsafe_in_sumo(grid_model, light_cfg):
    """The same check on the states SUMO actually reports back."""
    f = SafetyFilter(grid_model, CFG)
    m = SafetyMonitor(grid_model, CFG)
    ctrl = RandomController(random.Random(2))
    with SimulationAdapter(grid_model) as sim:
        sim.start(["-c", str(light_cfg), *QUIET_ARGS])
        for tls, s in f.reset().items():
            sim.set_signal_state(tls, s)
        for _ in range(600):
            snap = sim.step()
            t = snap.sim_time_s
            m.observe(t, snap.signal_states)  # what SUMO showed during the last step
            for r in ctrl.requests(grid_model, snap.effective_step):
                f.submit(r, t, snap.effective_step)
            for tls, s in f.tick(t, snap.effective_step).items():
                sim.set_signal_state(tls, s)
    assert m.violations == []
    assert sum(e.kind == "yellow" for e in f.events) > 50  # the test really switched a lot


def test_max_red_guard_forces_service(grid_model):
    """D2 5.4.3: the safety layer, not the controller, has the last word on maximum red."""
    cfg = SafetyConfig(min_green_s=10, yellow_s=3, all_red_s=2, max_red_s=40)
    f = SafetyFilter(grid_model, cfg)
    m = SafetyMonitor(grid_model, cfg)
    m.observe(0, f.reset())
    for t in range(1, 200):  # the controller keeps asking for phase 0 forever
        f.submit(req(0, t), t, t)
        m.observe(t, f.tick(t, t))
    forced = [a for a in f.applied if a.safety_intervention == "max_red_forced"]
    assert forced and all(a.controller_id == "safety_filter" for a in forced)
    assert forced[0].effective_step == 35  # 40 s max red - 5 s clearance
    greens = [e for e in f.events if e.intersection_id == TLS and e.kind == "green"]
    gaps = [b.sim_time_s - a.sim_time_s for a, b in zip(greens, greens[1:], strict=False)]
    assert max(gaps) <= 45  # phase 1 never waits more than max red + its own clearance
    assert m.violations == []


def test_max_red_guard_does_not_override_the_corridor(grid_model):
    from manzil.control.safety import CORRIDOR_ID
    from manzil.sim.contracts import Owner

    cfg = SafetyConfig(min_green_s=10, yellow_s=3, all_red_s=2, max_red_s=40)
    f = SafetyFilter(grid_model, cfg)
    f.reset()
    f.set_owner(TLS, Owner.CORRIDOR, 0, 0)
    for t in range(1, 80):
        f.submit(ControlRequest(CORRIDOR_ID, TLS, 0, t, "corridor"), t, t)
        f.tick(t, t)
    assert not any(a.intersection_id == TLS and a.safety_intervention == "max_red_forced"
                   for a in f.applied)  # fmt: skip
