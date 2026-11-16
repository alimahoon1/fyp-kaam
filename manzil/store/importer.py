"""Import existing run folders and perception results into the experiment store (W5).

Two kinds of run folder are recognised:

- **batch runs** (``manzil.experiments.runner``): ``manifest.json`` + ``metrics.json`` and, for
  emergency runs, ``mission.json``. The committed ones live under ``results/**/runs/*/``.
- **live dashboard runs** (``manzil.api.live``): ``summary.json`` whose ``source`` names the
  dashboard, under ``runs/live/*/``.

Perception results are the prepared V.4/V.5 tracking outputs in ``results/vision/tracking/``
(UA-DETRAC test sequences, processed on Kaggle): one VideoJob per sequence, with the counts and
the per-second queue proxy as Observations and the ground truth alongside.

Importing is idempotent: a run whose files did not change is skipped (content checksum).
Nothing is invented: a value missing from a file stays missing.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from manzil.experiments.compare import METRICS
from manzil.store.repository import (
    ExperimentRepository,
    MetricValue,
    MissionRecord,
    ObservationRecord,
    PriorityEventRecord,
    RouteVersionRecord,
    RunRecord,
    VideoJobRecord,
)

LIVE_SOURCE_PREFIX = "Manzil dashboard live run"


def metric_unit(name: str) -> str:
    if name in METRICS:
        return METRICS[name][1]
    for suffix, unit in (("_veh_s", "veh*s"), ("_ms", "ms"), ("_s", "s"), ("_veh", "veh"),
                         ("_mps", "m/s"), ("_pct", "%")):  # fmt: skip
        if name.endswith(suffix):
            return unit
    return "count"


def arm_name(cfg: dict) -> str:
    """The experiment arm, named as ``manzil.experiments.batch`` names it."""
    if cfg.get("label"):
        return cfg["label"]
    name = cfg.get("controller") or "?"
    if cfg.get("plan") not in (None, "", "auto"):
        name += f":{cfg['plan']}"
    for k, v in cfg.get("controller_params") or []:
        name += f",{k}={v}"
    return name


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _study(run_dir: Path, repo_root: Path) -> str:
    parent = run_dir.parent
    if parent.name == "runs":
        parent = parent.parent
    return _rel(parent, repo_root)


def _status(termination: str) -> str:
    if termination in ("completed", "finished"):
        return "completed"
    if termination == "stopped":
        return "stopped"
    return "failed"


def _numeric_metrics(metrics: dict, version, window) -> tuple[list[MetricValue], dict]:
    values, extra = [], {}
    for k, v in metrics.items():
        if k in ("metric_version", "run_id", "window_s"):
            continue
        if isinstance(v, bool):
            v = int(v)
        if v is None or isinstance(v, (int, float)):
            values.append(MetricValue(k, None if v is None else float(v), metric_unit(k),
                                      version, window[0], window[1]))  # fmt: skip
        else:
            extra[k] = v
    return values, extra


def _mission(index: int, vehicle_id: str, records: dict, metrics: dict, status) -> MissionRecord:
    cfg = records.get("config", {})
    rvs = [
        RouteVersionRecord(
            version=int(r["route_version"]),
            edge_ids=list(r["edge_ids"]),
            trigger=r.get("trigger", ""),
            cost_s=r.get("cost_s"),
            snapshot_step=r.get("snapshot_step"),
            compute_ms=r.get("compute_ms"),
        )
        for r in records.get("route_versions", [])
    ]
    events = [
        PriorityEventRecord(
            intersection_id=e["tls"],
            state=e["state"],
            time_s=e.get("time_s"),
            step=e.get("step"),
            route_version=e.get("route_version"),
            reason=e.get("reason"),
        )
        for e in records.get("corridor_events", [])
    ]
    return MissionRecord(
        index=index,
        vehicle_id=vehicle_id,
        origin=cfg.get("origin"),
        destination=cfg.get("destination"),
        status=status,
        corridor=cfg.get("corridor"),
        routing=cfg.get("routing"),
        metrics={k: v for k, v in metrics.items() if k.startswith(("amb_", "route", "corridor",
                                                                   "recovery", "mission"))},
        config=cfg,
        route_versions=rvs,
        priority_events=events,
    )  # fmt: skip


def read_batch_run(run_dir: Path, repo_root: Path) -> RunRecord:
    files = [run_dir / n for n in ("manifest.json", "metrics.json", "mission.json")]
    manifest = json.loads(files[0].read_text(encoding="utf-8"))
    metrics = json.loads(files[1].read_text(encoding="utf-8")) if files[1].is_file() else {}
    cfg = manifest.get("config", {})
    version = manifest.get("metric_version", metrics.get("metric_version"))
    window = metrics.get("window_s") or [cfg.get("warmup_s"), None]
    values, extra = _numeric_metrics(metrics, version, window)
    versions = manifest.get("versions", {})
    git = versions.get("git", {})
    missions = []
    if files[2].is_file():
        records = json.loads(files[2].read_text(encoding="utf-8"))
        missions.append(_mission(1, "ambulance", records, metrics, metrics.get("mission_status")))
    termination = manifest.get("termination", "unknown")
    rel = _rel(run_dir, repo_root)
    return RunRecord(
        run_key=rel,
        run_id=manifest.get("run_id", run_dir.name),
        study=_study(run_dir, repo_root),
        source="batch",
        status=_status(termination),
        termination=termination,
        config=cfg,
        content_sha256=_sha(*files),
        scenario=cfg.get("scenario"),
        network_id=manifest.get("network", {}).get("id"),
        demand_generator=manifest.get("demand", {}).get("generator"),
        profile=cfg.get("profile"),
        seed=cfg.get("seed"),
        controller=cfg.get("controller"),
        label=cfg.get("label") or None,
        arm=arm_name(cfg),
        warmup_s=cfg.get("warmup_s"),
        measure_s=cfg.get("measure_s"),
        metric_version=version,
        config_digest=manifest.get("config_digest"),
        created_at=manifest.get("created_at_utc"),
        git_commit=git.get("commit"),
        git_dirty=git.get("dirty"),
        sumo_version=versions.get("sumo"),
        wall_time_s=manifest.get("wall_time_s"),
        metrics=values,
        extra=extra,
        missions=missions,
        artifacts=[
            {
                "type": f.stem,
                "uri": _rel(f, repo_root),
                "sha256": _sha(f),
                "provenance": "written by manzil.experiments.runner",
            }
            for f in files
            if f.is_file()
        ],  # fmt: skip
    )


def read_live_run(run_dir: Path, repo_root: Path) -> RunRecord:
    f = run_dir / "summary.json"
    s = json.loads(f.read_text(encoding="utf-8"))
    cfg = s.get("config", {})
    termination = s.get("termination", "unknown")
    end = s.get("sim_time_s")
    metrics = {
        "vehicles_departed": s.get("vehicles_departed"),
        "vehicles_arrived": s.get("vehicles_arrived"),
        "safety_violations": s.get("safety_violations"),
        "sim_time_s": end,
        "closures": len(s.get("closures", [])),
        "missions": len(s.get("missions", [])),
        "controller_fallback_decisions": s.get("controller_decisions", {}).get("fallback"),
    }
    values = [
        MetricValue(k, None if v is None else float(v), "veh" if k.startswith("vehicles") else
                    ("s" if k.endswith("_s") else "count"), None, 0.0, end)
        for k, v in metrics.items()
    ]  # fmt: skip
    missions = [
        _mission(i + 1, m.get("vehicle_id", f"ambulance_{i + 1}"), m, m.get("metrics") or {},
                 (m.get("metrics") or {}).get("mission_status"))
        for i, m in enumerate(s.get("missions", []))
    ]  # fmt: skip
    versions = s.get("versions", {})
    return RunRecord(
        run_key=_rel(run_dir, repo_root),
        run_id=s.get("run_id", run_dir.name),
        study=_study(run_dir, repo_root),
        source="live",
        status=_status(termination),
        termination=termination,
        config=cfg,
        content_sha256=_sha(f),
        scenario=cfg.get("scenario"),
        network_id=s.get("network_id"),
        demand_generator=s.get("demand_generator"),
        profile=cfg.get("profile"),
        seed=cfg.get("seed"),
        controller=cfg.get("controller"),
        label="live",
        arm=f"live:{cfg.get('controller')}",
        warmup_s=cfg.get("warmup_s", 0.0),
        measure_s=cfg.get("duration_s"),
        metric_version=None,  # live runs keep counts only, not the batch metric set
        created_at=s.get("started_at_utc"),
        git_commit=versions.get("git", {}).get("commit"),
        git_dirty=versions.get("git", {}).get("dirty"),
        sumo_version=versions.get("sumo"),
        wall_time_s=s.get("wall_time_s"),
        metrics=values,
        extra={
            "closures": s.get("closures", []),
            "pauses": s.get("pauses", []),
            "faults": s.get("faults", []),
            "warnings": s.get("warnings", []),
        },
        missions=missions,
        artifacts=[
            {
                "type": "summary",
                "uri": _rel(f, repo_root),
                "sha256": _sha(f),
                "provenance": "written by manzil.api.live",
            }
        ],  # fmt: skip
    )


def find_run_folders(root: Path) -> list[tuple[str, Path]]:
    out = []
    for m in sorted(root.rglob("manifest.json")):
        out.append(("batch", m.parent))
    for s in sorted(root.rglob("summary.json")):
        try:
            src = json.loads(s.read_text(encoding="utf-8")).get("source", "")
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            continue
        if isinstance(src, str) and src.startswith(LIVE_SOURCE_PREFIX):
            out.append(("live", s.parent))
    return out


def import_runs(repo: ExperimentRepository, root: Path, repo_root: Path) -> dict:
    """Import every run folder below ``root``. Returns counts and any errors (kept, not hidden)."""
    counts: dict[str, int] = defaultdict(int)
    errors = []
    for kind, d in find_run_folders(Path(root)):
        try:
            rec = read_batch_run(d, repo_root) if kind == "batch" else read_live_run(d, repo_root)
            counts[repo.save_run(rec)] += 1
        except Exception as exc:  # a broken folder is reported, the rest still imports
            errors.append({"folder": _rel(d, repo_root), "error": f"{type(exc).__name__}: {exc}"})
    return {"root": _rel(Path(root), repo_root), **counts, "errors": errors}


# ----- perception ----------------------------------------------------------------------------
TRACKING_KERNEL = "mibrahimsalman022/manzil-yolo-track (kaggle/yolo_track/, version 1)"
TRACKING_LABELS = "UA-DETRAC official test annotations (human-made dataset ground truth)"


def import_tracking(repo: ExperimentRepository, tracking_dir: Path, repo_root: Path) -> dict:
    """One VideoJob per sequence of the V.4/V.5 tracking results (prepared, not live)."""
    tracking_dir = Path(tracking_dir)
    summary = json.loads((tracking_dir / "summary.json").read_text(encoding="utf-8"))
    settings = summary.get("settings", {})
    versions = summary.get("versions", {})
    queues: dict[str, list[dict]] = defaultdict(list)
    with (tracking_dir / "queue.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            queues[r["sequence"]].append(r)
    files = sorted(p for p in tracking_dir.iterdir() if p.is_file())
    counts: dict[str, int] = defaultdict(int)
    with (tracking_dir / "counts.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        seq = r["sequence"]
        num = {k: float(v) for k, v in r.items() if k != "sequence" and v != ""}
        obs = []
        for q in queues.get(seq, []):
            obs.append(ObservationRecord(
                entity_id=f"{seq}/view", observed_at_s=float(q["second"]),
                name="queue_proxy", value=float(q["pred_queue"]),
                reference=float(q["true_queue"]), unit="stopped veh in view (image proxy)",
            ))  # fmt: skip
        for cls in ("car", "bus", "truck", "motorcycle"):
            obs.append(ObservationRecord(
                entity_id=f"{seq}/line", observed_at_s=num["seconds"], name=f"count_{cls}",
                value=num[f"pred_{cls}"], reference=num[f"true_{cls}"], unit="veh",
            ))  # fmt: skip
        for d in ("down", "up"):
            obs.append(ObservationRecord(
                entity_id=f"{seq}/line", observed_at_s=num["seconds"], name=f"count_{d}",
                value=num[f"pred_{d}"], reference=num[f"true_{d}"], unit="veh",
            ))  # fmt: skip
        artifacts = [
            {"type": "frame" if p.suffix == ".png" else "video",
             "uri": _rel(p, repo_root), "sha256": _sha_file(p),
             "provenance": f"rendered by {TRACKING_KERNEL}"}
            for p in files if seq in p.name and p.suffix in (".png", ".mp4")
        ]  # fmt: skip
        job = VideoJobRecord(
            job_id=f"detrac/{seq}",
            dataset="UA-DETRAC test (held-out split)",
            clip=seq,
            clip_checksum=None,  # clips stay on Kaggle; the dataset version identifies them
            model_version="YOLO11s fine-tuned (V.3), models/yolo/manzil_yolo11s_best.pt",
            model_sha256=summary.get("weights_sha256"),
            tracker=f"ByteTrack ({settings.get('tracker')}),"
                    f" Ultralytics {versions.get('ultralytics')}",
            status="processed",
            label_status=TRACKING_LABELS,
            frames=int(num["frames"]),
            seconds=num["seconds"],
            fps=num.get("fps"),
            produced_by=f"{TRACKING_KERNEL} on {summary.get('device')}, 12 Nov 2026",
            summary={
                "true_total": num["true_total"], "pred_total": num["pred_total"],
                "abs_error": num["abs_error"], "true_queue_mean": num["true_queue_mean"],
                "pred_queue_mean": num["pred_queue_mean"],
                "queue_mae_per_frame": num["queue_mae_per_frame"],
                "processing_fps": num.get("fps"),
                "settings": settings, "versions": versions,
                "calibration": "none: counts are line crossings in image space; the queue is"
                               " a stopped-vehicle proxy in view, not a per-lane queue length",
                "results_dir": _rel(tracking_dir, repo_root),
            },
            observations=obs,
            artifacts=artifacts,
        )  # fmt: skip
        counts[repo.save_video_job(job)] += 1
    return {"root": _rel(tracking_dir, repo_root), **counts}


def _sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def import_all(repo: ExperimentRepository, repo_root: Path, extra_roots=()) -> dict:
    """Default import: committed results, local live runs, and the tracking results."""
    report = {"runs": [], "perception": []}
    for root in (repo_root / "results", repo_root / "runs" / "live", *extra_roots):
        if Path(root).is_dir():
            report["runs"].append(import_runs(repo, Path(root), repo_root))
    tracking = repo_root / "results" / "vision" / "tracking"
    if (tracking / "counts.csv").is_file():
        report["perception"].append(import_tracking(repo, tracking, repo_root))
    return report
