"""W3: held-out demand, protocol runner on any network, paired statistics, fairness metrics."""

import hashlib
import json
import shutil

import pytest
import sumolib

from manzil.control.fixed_time import SignalTiming
from manzil.control.rl_env import RewardParams, TrafficEnv
from manzil.control.safety import Owner
from manzil.experiments import protocol as P
from manzil.experiments.metrics import signal_metrics
from manzil.experiments.runner import RunConfig
from manzil.scenarios.demand import (
    ALL_PROFILES,
    DEFAULT_NET,
    HELDOUT_PROFILES,
    PROFILES,
    fringe_edges,
    generate_trips,
)
from manzil.scenarios.grid import GridSpec, build_grid
from manzil.sim.contracts import SignalEvent


@pytest.fixture(scope="module")
def net():
    return sumolib.net.readNet(str(DEFAULT_NET))


# ------------------------------------------------------------------------------ demand


def test_heldout_profiles_are_separate_from_training_profiles():
    assert set(PROFILES) == {"light", "medium", "heavy", "uneven"}  # training set unchanged
    assert not set(PROFILES) & set(HELDOUT_PROFILES)
    assert set(ALL_PROFILES) == set(PROFILES) | set(HELDOUT_PROFILES)
    assert set(HELDOUT_PROFILES) == {"uneven_ew", "tidal", "peak"}


def test_training_profiles_unchanged_since_phase1(net):
    """Checksums computed with the Phase 1 generator (origin/main before W3)."""
    expected = {"light": "9d1d0da926b1e6d8", "medium": "372fa4c612cf1595",
                "heavy": "6d860d1d08e23be5", "uneven": "9c134ff55138347e"}  # fmt: skip
    for name, digest in expected.items():
        t = generate_trips(net, PROFILES[name], 3, 1200)
        key = repr([(x.trip_id, x.depart, x.from_edge, x.to_edge) for x in t])
        assert hashlib.sha256(key.encode()).hexdigest()[:16] == digest, name


def test_fringe_headings(net):
    entries, _ = fringe_edges(net)
    heads = {e.edge_id: e.heading for e in entries}
    assert heads["left0A0"] == "E" and heads["bottom0A0"] == "N"
    assert heads["right0C0"] == "W" and heads["top0A2"] == "S"
    assert sorted(heads.values()).count("N") == 3


def test_uneven_ew_mirrors_uneven(net):
    entries, _ = fringe_edges(net)
    ns = {e.edge_id for e in entries if e.north_south}
    trips = generate_trips(net, HELDOUT_PROFILES["uneven_ew"], 0, 3600)
    n_ns = sum(t.from_edge in ns for t in trips)
    assert n_ns / len(trips) == pytest.approx(100 / 900, abs=0.03)


def test_tidal_rates_by_heading(net):
    entries, _ = fringe_edges(net)
    head = {e.edge_id: e.heading for e in entries}
    trips = generate_trips(net, HELDOUT_PROFILES["tidal"], 0, 3600)
    per = {h: sum(head[t.from_edge] == h for t in trips) for h in "NESW"}
    for h, rate in (("N", 650), ("E", 650), ("S", 150), ("W", 150)):
        assert per[h] == pytest.approx(3 * rate, rel=0.12), h


def test_peak_profile_is_time_varying(net):
    p = HELDOUT_PROFILES["peak"]
    assert p.multiplier(0.0) == pytest.approx(0.4) and p.multiplier(0.5) == pytest.approx(1.0)
    assert p.multiplier(0.25) == pytest.approx(0.7) and p.multiplier(1.0) == pytest.approx(0.4)
    dur = 4000.0
    trips = generate_trips(net, p, 1, dur)
    start = sum(t.depart < 0.1 * dur for t in trips)
    mid = sum(0.45 * dur <= t.depart < 0.55 * dur for t in trips)
    assert 1.6 < mid / start < 3.2  # expected about 1 / 0.43
    assert generate_trips(net, p, 1, dur) == trips  # seeded


# ------------------------------------------------------------------------ configs and arms


def test_heldout_profile_only_through_protocol_config():
    with pytest.raises(ValueError):
        RunConfig(profile="tidal").validate()  # training/tuning code cannot use it
    P.ProtocolRunConfig(profile="tidal").validate()
    with pytest.raises(ValueError):
        P.ProtocolRunConfig(profile="nonsense").validate()
    with pytest.raises(ValueError):
        P.ProtocolRunConfig(profile="tidal", seed=-1).validate()


def test_arm_parse():
    assert P.Arm.parse("adaptive") == P.Arm("adaptive", "adaptive")
    assert P.Arm.parse("ft_eq=fixed_time:equal") == P.Arm("ft_eq", "fixed_time", "equal")
    a = P.Arm.parse("dqn_s1=dqn@models/x/best.pt")
    assert (a.name, a.controller, a.checkpoint) == ("dqn_s1", "dqn", "models/x/best.pt")
    with pytest.raises(ValueError):
        P.Arm.parse("x=nope")


def test_seed_sets_are_disjoint():
    from manzil.experiments.protocol_train import demand_seed

    train = {demand_seed(k, ep) for k in range(3) for ep in range(1, 201)}
    assert not train & set(P.EVAL_SEEDS) and not train & set(P.DEV_SEEDS)
    assert not set(P.EVAL_SEEDS) & set(range(5))  # FYP-1 evaluation seeds not reused
    assert demand_seed(0, 1) == 1001  # Phase 4 training seeds


def test_fair_reward_variant_changes_only_the_starvation_threshold():
    from dataclasses import asdict

    from manzil.experiments.protocol_train import REWARD_VARIANTS

    base, fair = asdict(REWARD_VARIANTS["base"]), asdict(REWARD_VARIANTS["fair"])
    assert base == asdict(RewardParams())
    assert {k for k in base if base[k] != fair[k]} == {"max_red_s"}
    assert fair["max_red_s"] == 60.0


def test_env_counts_starvation_penalties(grid_model, tmp_path):
    timing = SignalTiming.load(DEFAULT_NET.parent / "signals.json")
    env = TrafficEnv(grid_model, timing, RewardParams(max_red_s=30.0), work_dir=str(tmp_path))
    obs, masks = env.reset("light", 5, 80.0)
    seen, done = 0, False
    while not done:  # always keep phase 0: phase 1 starves after 30 s
        _, _, _, done = env.step(dict.fromkeys(obs, 0))
        seen += env.last_starving
    env.close()
    assert seen > 0


# --------------------------------------------------------------------- fairness metrics


def _ev(t, tls, kind, phase):
    return SignalEvent(0, t, tls, kind, phase, "", Owner.NORMAL)


def test_red_intervals_match_max_red_metric():
    evs = [_ev(0, "J", "green", 0), _ev(30, "J", "yellow", 0), _ev(35, "J", "green", 1),
           _ev(100, "J", "yellow", 1), _ev(105, "J", "green", 0), _ev(120, "J", "yellow", 0),
           _ev(125, "J", "green", 1)]  # fmt: skip
    rows = [{"sim_time_s": e.sim_time_s, "intersection_id": e.intersection_id,
             "kind": e.kind, "phase_id": e.phase_id} for e in evs]  # fmt: skip
    gaps = P.red_intervals(rows, {"J": 2}, 10.0, 200.0)
    # phase 1: red from 10 (window start) to 35; phase 0: 30->105; phase 1: 100->125;
    # phase 0 still red at the end: 120->200.
    assert sorted(gaps) == [25.0, 25.0, 75.0, 80.0]
    assert max(gaps) == signal_metrics(evs, {"J": 2}, 10.0, 200.0)["max_red_s"]
    f = P.fairness_metrics(gaps)
    assert f["red_mean_s"] == 51.25 and f["red_p95_s"] == 80.0
    assert f["red_share_over_60"] == 50.0


# ---------------------------------------------------------------------------- statistics


def _row(arm, profile, seed, tt):
    return {"arm": arm, "profile": profile, "seed": seed, "network_id": "n",
            "demand_generator": "g", "warmup_s": 0, "measure_s": 1, "metric_version": 1,
            "termination": "completed", "travel_time_all_mean_s": tt,
            "throughput_veh": 100.0}  # fmt: skip


def test_paired_summary_and_mean_arm():
    rows = []
    for s, base in enumerate([100.0, 110.0, 120.0, 130.0]):
        rows += [_row("fixed_time", "tidal", s, base), _row("a", "tidal", s, base - 10 + s),
                 _row("b", "tidal", s, base - 4)]  # fmt: skip
    m = ["travel_time_all_mean_s", "throughput_veh"]
    rows += P.mean_arm(rows, "ab", ["a", "b"], m)
    s = P.summarise(rows, "fixed_time", ["fixed_time", "a", "ab"], m)
    assert s["profiles"] == ["tidal"]
    d = s["paired"]["tidal"]["a"]["travel_time_all_mean_s"]
    assert d["mean_diff"] == pytest.approx(-8.5) and d["seeds_better"] == 4 and d["n"] == 4
    lo, hi = d["ci95"]
    assert lo < -8.5 < hi
    dab = s["paired"]["tidal"]["ab"]["travel_time_all_mean_s"]
    assert dab["mean_diff"] == pytest.approx((-8.5 - 4) / 2)
    assert "tidal (held out)" in P.compact_markdown(s, m)
    tv = P.training_variance(rows, ["a", "b"], "fixed_time", m)
    tt = next(r for r in tv if r["metric"] == "travel_time_all_mean_s")
    assert tt["between_range"] == pytest.approx(4.5) and tt["models_better_than_ref"] == 2


def test_unmatched_seeds_are_refused():
    rows = [_row("fixed_time", "light", 0, 1.0), _row("fixed_time", "light", 1, 1.0),
            _row("a", "light", 0, 1.0)]  # fmt: skip
    with pytest.raises(ValueError):
        P.summarise(rows, "fixed_time", ["fixed_time", "a"], ["travel_time_all_mean_s"])


# --------------------------------------------------------------- integration: other network


def test_protocol_runs_on_another_network(tmp_path):
    """A 2x2 grid outside scenarios/: plan selection for a held-out profile, two arms, report."""
    scen = tmp_path / "grid2x2"
    build_grid(scen, GridSpec(size=2))
    shutil.copy(DEFAULT_NET.parent / "signals.json", scen / "signals.json")
    out = tmp_path / "out"
    P.main(["run", "--scenario", "grid2x2", "--scenario-root", str(scen), "--arms", "fixed_time",
            "adaptive", "--profiles", "light", "tidal", "--seeds", "1", "2", "--warmup", "60",
            "--measure", "240", "--workers", "1", "--out", str(out)])  # fmt: skip
    proto = json.loads((out / "protocol.json").read_text())
    assert proto["fixed_time_plans"]["light"] == "light"
    assert proto["fixed_time_plans"]["tidal"] in SignalTiming.load(scen / "signals.json").plans
    assert proto["heldout_profiles"] == ["tidal"]
    rows = P.read_table(out / "results.csv")
    assert len(rows) == 8 and all(r["termination"] == "completed" for r in rows)
    assert {r["network_id"] for r in rows} != {"grid3x3"}
    assert all(r["red_p95_s"] != "" for r in rows)
    assert not list((out / "runs").glob("*/signal_events.csv"))  # detail files removed
    summary = json.loads((out / "summary.json").read_text())
    assert summary["totals"] == {"runs": 8, "failed": 0, "safety_violations": 0,
                                 "teleports": 0, "collisions": 0}  # fmt: skip
    assert (out / "plan_selection.csv").is_file() and (out / "tables.md").is_file()
