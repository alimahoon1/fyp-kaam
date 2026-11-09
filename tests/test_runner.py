"""Tasks 1.7 and 1.8: a run writes manifest + metrics; the same seed gives the same metrics."""

import json

import pytest

from manzil.experiments.metrics import METRIC_VERSION
from manzil.experiments.runner import RunConfig, run

SHORT = {"warmup_s": 120.0, "measure_s": 480.0}


@pytest.fixture(scope="module")
def first_run(tmp_path_factory):
    return run(RunConfig(profile="medium", seed=3, **SHORT), tmp_path_factory.mktemp("run_a"))


def test_run_writes_all_outputs(first_run):
    names = {p.name for p in first_run.run_dir.iterdir()}
    assert {
        "manifest.json",
        "metrics.json",
        "timeseries.csv",
        "signal_events.csv",
        "applied_controls.csv",
        "tripinfo.xml",
        "statistics.xml",
    } <= names


def test_manifest_records_what_reproduces_the_run(first_run):
    m = json.loads((first_run.run_dir / "manifest.json").read_text())
    assert m["termination"] == "completed"
    assert m["config"]["seed"] == 3 and m["config"]["profile"] == "medium"
    assert m["metric_version"] == METRIC_VERSION
    assert m["versions"]["sumo"].startswith("Eclipse SUMO")
    assert m["network"]["content_sha256"]
    assert m["demand"]["seed"] == 3
    assert m["controller"]["plan_name"] == "medium"
    assert m["signal_timing"]["safety"]["yellow_s"] == 3


def test_metrics_are_plausible(first_run):
    x = first_run.metrics
    assert x["throughput_veh"] > 0 and x["completed_trips"] > 0
    assert x["travel_time_mean_s"] > x["waiting_time_mean_s"] >= 0
    assert 0 <= x["queue_mean_veh"] <= x["queue_max_veh"]
    assert x["phase_changes"] == 9 * 2 * 8  # 480 s / 60 s cycle, two switches per cycle
    assert x["max_red_s"] == 35.0  # 25 s other green + 2 x 5 s clearance
    assert x["safety_violations"] == 0 and x["collisions"] == 0


def test_same_seed_same_metrics(first_run, tmp_path):
    """Task 1.8: an identical config reproduces every metric exactly."""
    again = run(RunConfig(profile="medium", seed=3, **SHORT), tmp_path)
    assert again.metrics == first_run.metrics


def test_traci_backend_gives_the_same_metrics(first_run, tmp_path):
    again = run(RunConfig(profile="medium", seed=3, backend="traci", **SHORT), tmp_path)
    assert again.metrics == first_run.metrics


def test_different_seed_different_metrics(first_run, tmp_path):
    other = run(RunConfig(profile="medium", seed=4, **SHORT), tmp_path)
    assert other.metrics != first_run.metrics


@pytest.mark.parametrize(
    "bad",
    [
        {"profile": "rush"},
        {"controller": "magic"},
        {"seed": -1},
        {"measure_s": 0},
        {"warmup_s": 10.5},
        {"scenario": "nowhere"},
    ],
)
def test_bad_config_rejected_before_start(bad, tmp_path):
    with pytest.raises(ValueError, match="invalid run config"):
        run(RunConfig(**{**SHORT, **bad}), tmp_path)
    assert not (tmp_path / "manifest.json").exists()
