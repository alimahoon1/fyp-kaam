"""W5 experiment store: import of the committed run folders, repository rules, FR-18
comparison and FR-19 export (no SUMO needed; reads the files in results/)."""

from __future__ import annotations

import csv
import io
import json
import math
import sqlite3

import pytest

from manzil.experiments.runner import REPO_ROOT
from manzil.store.__main__ import main as store_cli
from manzil.store.analytics import compare_runs
from manzil.store.export import EXPORT_FORMAT, build_export, to_csv
from manzil.store.importer import arm_name, import_all, import_runs, metric_unit
from manzil.store.repository import (
    MissionRecord,
    RouteVersionRecord,
    RunRecord,
    SqliteRepository,
)

PHASE2 = "results/phase2/comparison"


@pytest.fixture(scope="module")
def repo():
    r = SqliteRepository(":memory:")
    import_all(r, REPO_ROOT)
    yield r
    r.close()


def test_every_committed_run_folder_is_imported(repo):
    manifests = list((REPO_ROOT / "results").rglob("manifest.json"))
    s = repo.summary()
    assert s["runs"] == len(manifests) > 300
    assert s["video_jobs"] == 40  # UA-DETRAC test sequences of V.4/V.5
    assert all(st["completed"] == st["runs"] for st in s["studies"])  # all FYP-I runs completed
    assert {st["study"] for st in s["studies"]} >= {PHASE2, "results/phase4/comparison"}


def test_reimport_is_idempotent(repo):
    rep = import_runs(repo, REPO_ROOT / "results" / "phase2", REPO_ROOT)
    assert rep.get("unchanged") == 60 and not rep.get("added") and rep["errors"] == []


def test_run_record_matches_its_files(repo):
    key = f"{PHASE2}/runs/000_fixed_time_heavy_s0"
    run = repo.get_run(key)
    manifest = json.loads((REPO_ROOT / key / "manifest.json").read_text())
    metrics = json.loads((REPO_ROOT / key / "metrics.json").read_text())
    assert run["config"] == manifest["config"]
    assert run["network_id"] == manifest["network"]["id"]
    assert run["status"] == "completed" and run["termination"] == "completed"
    m = run["metrics"]["travel_time_mean_s"]
    assert m["value"] == metrics["travel_time_mean_s"] and m["unit"] == "s"
    assert m["metric_version"] == 1 and m["interval_s"] == metrics["window_s"]
    assert run["extra"]["safety_interventions"] == metrics["safety_interventions"]
    assert {a["type"] for a in run["artifacts"]} == {"manifest", "metrics"}


def test_mission_route_versions_and_priority_events(repo):
    runs = repo.list_runs(study="results/phase3/routing", label="dynamic")
    assert runs and all(r["has_mission"] for r in runs)
    mission = repo.missions(runs[0]["run_key"])[0]
    versions = [rv["version"] for rv in mission["route_versions"]]
    assert versions == sorted(versions) and versions[0] == 1
    assert mission["route_versions"][0]["trigger"] == "dispatch"
    on = repo.list_runs(study="results/phase3/corridor", label="corridor_on")[0]
    events = repo.missions(on["run_key"])[0]["priority_events"]
    assert events and {"REQUESTED", "ACTIVE_PRIORITY"} <= {e["state"] for e in events}


def test_arms_follow_the_batch_naming(repo):
    assert arm_name({"controller": "fixed_time", "plan": "equal"}) == "fixed_time:equal"
    assert arm_name({"controller": "dqn", "label": "v2"}) == "v2"
    arms = {r["arm"] for r in repo.list_runs(study=PHASE2)}
    assert arms == {"fixed_time", "fixed_time:equal", "adaptive"}
    assert metric_unit("cross_street_wait_veh_s") == "veh*s"
    assert metric_unit("queue_mean_veh") == "veh"


def test_compare_reproduces_the_committed_phase2_summary(repo):
    keys = [r["run_key"] for r in repo.list_runs(study=PHASE2, profile="heavy")]
    c = compare_runs(repo, keys, "arm", ["travel_time_mean_s"])
    summary = json.loads((REPO_ROOT / PHASE2 / "summary.json").read_text())
    want = summary["summary"]["heavy"]
    got = c["metrics"]["travel_time_mean_s"]
    for arm in ("fixed_time", "adaptive", "fixed_time:equal"):
        assert got["groups"][arm]["mean"] == pytest.approx(want[arm]["travel_time_mean_s"]["mean"])
        assert got["groups"][arm]["sd"] == pytest.approx(want[arm]["travel_time_mean_s"]["sd"])
    ref = summary["paired"]["heavy"]["fixed_time:equal"]["travel_time_mean_s"]
    paired = got["paired_vs_reference"]["fixed_time:equal"]
    assert c["reference"] == "fixed_time"
    assert paired["mean"] == pytest.approx(ref["mean_diff"])
    assert paired["mean"] + paired["ci95"] == pytest.approx(ref["ci95"][1])
    assert c["warnings"] == []  # one study, one profile: comparable


def test_compare_warns_on_incompatible_runs(repo):
    a = repo.list_runs(study=PHASE2, profile="heavy", arm="fixed_time")
    b = repo.list_runs(study="results/phase3/corridor", label="corridor_on")  # 900 s window
    c = compare_runs(repo, [r["run_key"] for r in a + b], "arm", ["travel_time_mean_s"])
    codes = {w["code"] for w in c["warnings"]}
    assert "incompatible_measure_s" in codes  # 3,600 s vs 900 s measurement
    assert "mixed_profiles" in codes
    assert "unmatched_seeds" in codes  # corridor seeds 0-9 vs phase 2 seeds 0-4


def _record(key, status, termination, versions=(1,)):
    return RunRecord(
        run_key=key, run_id=key, study="t", source="live", status=status,
        termination=termination, config={}, content_sha256=key + status,
        controller="fixed_time", arm="fixed_time", profile="light", seed=0,
        missions=[MissionRecord(1, "amb", "a", "b", "ARRIVED", True, "dynamic",
                                route_versions=[RouteVersionRecord(v, ["a"], "t")
                                                for v in versions])],
    )  # fmt: skip


def test_failed_runs_are_kept_and_excluded_from_statistics():
    r = SqliteRepository(":memory:")
    r.save_run(_record("ok", "completed", "completed"))
    r.save_run(_record("bad", "failed", "error: FatalTraCIError: connection closed"))
    assert {x["run_key"] for x in r.list_runs()} == {"ok", "bad"}
    c = compare_runs(r, ["ok", "bad"], "arm", [])
    assert c["runs_used"] == 1 and c["excluded"][0]["run_key"] == "bad"
    assert any(w["code"] == "excluded_runs" for w in c["warnings"])


def test_route_versions_must_increase():
    r = SqliteRepository(":memory:")
    with pytest.raises(ValueError, match="not increasing"):
        r.save_run(_record("x", "completed", "completed", versions=(2, 1)))
    with pytest.raises(sqlite3.IntegrityError):  # the schema rejects an unknown status
        r.save_run(_record("y", "weird", "?"))


def test_perception_jobs_keep_provenance_and_ground_truth(repo):
    jobs = {j["job_id"]: j for j in repo.list_video_jobs()}
    job = repo.get_video_job("detrac/MVI_40714")
    assert job["model_sha256"].startswith("0022c8a0") and "ByteTrack" in job["tracker"]
    assert "UA-DETRAC" in job["label_status"] and "calibration" in job["summary"]
    rows = list(csv.DictReader((REPO_ROOT / "results/vision/tracking/counts.csv").open()))
    row = next(x for x in rows if x["sequence"] == "MVI_40714")
    assert jobs["detrac/MVI_40714"]["summary"]["pred_total"] == float(row["pred_total"])
    q = repo.observations("detrac/MVI_40714", "queue_proxy")
    assert q and all(o["reference"] is not None for o in q)
    assert {a["type"] for a in job["artifacts"]} == {"frame", "video"}


def test_export_json_and_csv(repo):
    keys = [r["run_key"] for r in repo.list_runs(study=PHASE2, profile="light")]
    doc = build_export(repo, keys)
    assert doc["format"] == EXPORT_FORMAT and doc["format_version"] == 1
    assert doc["run_count"] == len(keys) == 15
    first = doc["runs"][0]
    assert first["config"]["profile"] == "light" and "travel_time_mean_s" in first["metrics"]
    json.dumps(doc, allow_nan=False)  # strict JSON
    rows = list(csv.DictReader(io.StringIO(to_csv(repo, keys))))
    assert len(rows) == 15 and "travel_time_mean_s[s]" in rows[0]
    by_key = {x["run_key"]: x for x in rows}
    want = repo.metrics([keys[0]])[keys[0]]["travel_time_mean_s"]["value"]
    assert math.isclose(float(by_key[keys[0]]["travel_time_mean_s[s]"]), want)


def test_cli_import_and_export(tmp_path, capsys):
    db = tmp_path / "s.sqlite"
    assert store_cli(["--db", str(db), "import", "--root", str(REPO_ROOT / PHASE2)]) == 0
    out = tmp_path / "e.json"
    assert store_cli(["--db", str(db), "export", "--arm", "adaptive", "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["run_count"] == 20 and {r["config"]["controller"] for r in doc["runs"]} == {
        "adaptive"
    }
    assert "exported 20 runs" in capsys.readouterr().out
