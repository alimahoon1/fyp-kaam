"""Batch runner: controller x demand profile x seed in parallel -> one results table (PLAN 2.2).

Each run is a normal ``runner.run`` in its own worker process (libsumo allows one simulation per
process). The table has one row per run: the config fields plus every metric. Before results are
compared, ``check_compatible`` refuses to mix runs whose network, demand generator, durations or
metric version differ (FR-18).

Usage::

    python -m manzil.experiments.batch --arms fixed_time fixed_time:equal adaptive \\
        --seeds 0 1 2 3 4 --out results/phase2/comparison
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import shutil
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

from manzil.experiments.runner import CONTROLLERS, RunConfig, run
from manzil.scenarios.demand import PROFILES

RAW_FILES = ("tripinfo.xml", "statistics.xml", "demand")


def _run_one(args: tuple[RunConfig, str, bool]) -> dict:
    config, out_dir, keep_raw = args
    run_dir = Path(out_dir)
    result = run(config, run_dir)
    if not keep_raw:
        for name in RAW_FILES:
            p = run_dir / name
            shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    m = result.manifest
    if config.label:
        arm = config.label
    elif config.plan == "auto" or config.controller != "fixed_time":
        arm = config.controller
    else:
        arm = f"fixed_time:{config.plan}"
    return {
        "arm": arm,
        **{k: (json.dumps(v, sort_keys=True) if isinstance(v, dict) else v)
           for k, v in asdict(config).items() if k != "controller_params"},
        "controller_params": json.dumps(dict(config.controller_params), sort_keys=True),
        "plan_used": m["controller"].get("plan_name", ""),
        "network_id": m["network"]["id"],
        "demand_generator": m["demand"]["generator"],
        "termination": m["termination"],
        "wall_time_s": m["wall_time_s"],
        "run_dir": str(run_dir),
        **{k: (json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v)
           for k, v in result.metrics.items() if k not in ("run_id", "window_s")},
    }  # fmt: skip


def run_batch(
    configs: list[RunConfig], out_root: Path, workers: int = 0, keep_raw: bool = False
) -> list[dict]:
    """Run every config; returns table rows in the same order as ``configs``."""
    out_root = Path(out_root)
    runs_dir = out_root / "runs"
    jobs = []
    for i, c in enumerate(configs):
        c.validate()
        name = f"{i:03d}_{c.label or c.controller}_{c.profile}_s{c.seed}"
        jobs.append((c, str(runs_dir / name), keep_raw))
    workers = workers or min(len(jobs), mp.cpu_count())
    if workers <= 1:
        return [_run_one(j) for j in jobs]
    with ProcessPoolExecutor(workers, mp_context=mp.get_context("spawn")) as pool:
        return list(pool.map(_run_one, jobs))


def check_compatible(rows: list[dict]) -> None:
    """FR-18: rows compared within one profile must share network, demand and protocol."""
    keys = ("network_id", "demand_generator", "warmup_s", "measure_s", "metric_version")
    by_profile: dict[str, set] = {}
    for r in rows:
        if r["termination"] != "completed":
            raise ValueError(f"run {r['run_dir']} did not complete: {r['termination']}")
        by_profile.setdefault(r["profile"], set()).add(tuple(r[k] for k in keys))
    bad = {p: v for p, v in by_profile.items() if len(v) > 1}
    if bad:
        raise ValueError(f"incompatible runs within a profile ({keys}): {bad}")


def write_table(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def read_table(path: Path) -> list[dict]:
    def conv(v: str):
        for t in (int, float):
            try:
                return t(v)
            except ValueError:
                pass
        return v

    with Path(path).open(encoding="utf-8") as f:
        return [{k: conv(v) for k, v in r.items()} for r in csv.DictReader(f)]


def parse_arm(arm: str) -> tuple[str, str]:
    """``"adaptive"`` -> (adaptive, auto); ``"fixed_time:equal"`` -> (fixed_time, equal)."""
    controller, _, plan = arm.partition(":")
    if controller not in CONTROLLERS:
        raise ValueError(f"unknown controller in arm {arm!r}")
    return controller, plan or "auto"


def grid(base: RunConfig, arms, profiles, seeds) -> list[RunConfig]:
    out = []
    for p in profiles:
        for arm in arms:
            controller, plan = parse_arm(arm)
            out += [
                replace(base, controller=controller, plan=plan, profile=p, seed=s) for s in seeds
            ]
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--arms",
        nargs="+",
        default=list(CONTROLLERS),
        help='controllers to compare; "fixed_time:<plan>" fixes one plan for every profile',
    )
    ap.add_argument("--profiles", nargs="+", default=sorted(PROFILES), choices=sorted(PROFILES))
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--warmup", type=float, default=900.0)
    ap.add_argument("--measure", type=float, default=3600.0)
    ap.add_argument("--workers", type=int, default=0, help="0 = one per CPU")
    ap.add_argument("--keep-raw", action="store_true", help="keep tripinfo and demand files")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    base = RunConfig(warmup_s=a.warmup, measure_s=a.measure)
    configs = grid(base, a.arms, a.profiles, a.seeds)
    rows = run_batch(configs, a.out, a.workers, a.keep_raw)
    check_compatible(rows)
    write_table(rows, a.out / "results.csv")
    print(f"{len(rows)} runs -> {a.out / 'results.csv'}")


if __name__ == "__main__":
    main()
