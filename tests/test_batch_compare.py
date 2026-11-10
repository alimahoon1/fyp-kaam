"""Tasks 2.2 and 2.3: batch runner table, compatibility check, paired comparison, plot."""

import math

import pytest

from manzil.experiments.batch import check_compatible, grid, read_table, run_batch, write_table
from manzil.experiments.compare import markdown, mean_sd, plot, summarise, t95
from manzil.experiments.runner import RunConfig


@pytest.fixture(scope="module")
def batch(tmp_path_factory):
    out = tmp_path_factory.mktemp("batch")
    base = RunConfig(warmup_s=60, measure_s=240)
    configs = grid(base, ["fixed_time", "adaptive"], ["light"], [0, 1])
    rows = run_batch(configs, out, workers=2)
    write_table(rows, out / "results.csv")
    return out, rows


def test_batch_produces_one_row_per_run(batch):
    out, rows = batch
    assert [(r["controller"], r["seed"]) for r in rows] == [
        ("fixed_time", 0), ("fixed_time", 1), ("adaptive", 0), ("adaptive", 1),
    ]  # fmt: skip
    assert all(r["termination"] == "completed" for r in rows)
    # Raw SUMO files are removed by default; manifest and metrics stay.
    run_dir = out / "runs" / "000_fixed_time_light_s0"
    assert (run_dir / "manifest.json").is_file() and not (run_dir / "tripinfo.xml").exists()


def test_parallel_batch_matches_a_serial_run(batch, tmp_path):
    _, rows = batch
    (serial,) = run_batch([RunConfig(warmup_s=60, measure_s=240, seed=1)], tmp_path, workers=1)
    parallel = next(r for r in rows if r["controller"] == "fixed_time" and r["seed"] == 1)
    for k in ("travel_time_mean_s", "queue_mean_veh", "throughput_veh", "phase_changes"):
        assert serial[k] == parallel[k]


def test_table_round_trip(batch):
    out, rows = batch
    back = read_table(out / "results.csv")
    assert len(back) == len(rows)
    assert back[0]["travel_time_mean_s"] == pytest.approx(rows[0]["travel_time_mean_s"])


def test_incompatible_runs_refused(batch):
    _, rows = batch
    bad = [dict(r) for r in rows]
    bad[0]["measure_s"] = 999.0
    with pytest.raises(ValueError, match="incompatible"):
        check_compatible(bad)


def test_paired_comparison(batch, tmp_path):
    out, _ = batch
    rows = read_table(out / "results.csv")
    s = summarise(rows)
    assert s["controllers"] == ["fixed_time", "adaptive"]
    d = s["paired"]["light"]["adaptive"]["travel_time_mean_s"]
    ref = [r["travel_time_mean_s"] for r in rows if r["controller"] == "fixed_time"]
    ada = [r["travel_time_mean_s"] for r in rows if r["controller"] == "adaptive"]
    assert d["mean_diff"] == pytest.approx(sum(ada) / 2 - sum(ref) / 2)
    assert d["n"] == 2 and d["ci95"][0] <= d["mean_diff"] <= d["ci95"][1]
    assert "### light" in markdown(s)
    plot(rows, s, tmp_path / "c.png")
    assert (tmp_path / "c.png").stat().st_size > 10_000


def test_statistics_helpers():
    m, sd = mean_sd([1.0, 2.0, 3.0])
    assert m == 2.0 and sd == pytest.approx(1.0)
    assert t95(4) == pytest.approx(2.776) and t95(100) == 1.96
    assert math.isnan(mean_sd([5.0])[1])


def test_label_names_the_arm(tmp_path):
    (row,) = run_batch([RunConfig(warmup_s=30, measure_s=60, label="my_arm")], tmp_path, workers=1)
    assert row["arm"] == "my_arm"
    assert (tmp_path / "runs" / "000_my_arm_light_s0" / "manifest.json").is_file()
