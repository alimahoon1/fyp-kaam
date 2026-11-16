"""Cross-run comparison for G05 (FR-18) on top of the store.

``compare_runs`` groups the selected runs (by controller, label or any run field), and for each
metric gives n, mean, sample SD and a 95 % t interval per group, plus paired differences
against a reference group on runs matched by (profile, seed). Before any number it checks
comparability: runs that differ in network, demand generator, warm-up, measurement length or
metric version produce a warning, and so do unmatched seeds and failed or stopped runs (these
are listed and left out of the statistics, never dropped silently).
"""

from __future__ import annotations

import math
from collections import defaultdict

from manzil.experiments.compare import METRICS, mean_sd, t95
from manzil.store.repository import ExperimentRepository

COMPAT_KEYS = ("scenario", "network_id", "warmup_s", "measure_s", "metric_version")
GROUP_FIELDS = ("arm", "controller", "label", "profile", "study", "source", "seed")


def comparability(runs: list[dict], group_by: str) -> list[dict]:
    warnings = []
    for key in COMPAT_KEYS:
        values = sorted({str(r.get(key)) for r in runs})
        if len(values) > 1:
            warnings.append({
                "code": "incompatible_" + key,
                "level": "error",
                "message": f"runs differ in {key}: {', '.join(values)}; "
                           "numbers below are not a valid comparison",
            })  # fmt: skip
    profiles = sorted({str(r.get("profile")) for r in runs})
    if len(profiles) > 1 and group_by != "profile":
        warnings.append({
            "code": "mixed_profiles", "level": "warning",
            "message": f"runs mix demand profiles ({', '.join(profiles)}); group means pool"
                       " different demand levels. Filter to one profile for a fair comparison.",
        })  # fmt: skip
    seeds: dict[str, set] = defaultdict(set)
    for r in runs:
        if r["status"] == "completed":
            seeds[str(r.get(group_by))].add((r.get("profile"), r.get("seed")))
    if len(seeds) > 1:
        common = set.intersection(*seeds.values())
        for g, s in sorted(seeds.items()):
            if s - common:
                warnings.append({
                    "code": "unmatched_seeds", "level": "warning",
                    "message": f"{group_by}={g}: {len(s - common)} run(s) have no matching"
                               " (profile, seed) in every other group; they are left out of the"
                               " paired differences",
                })  # fmt: skip
    bad = [r for r in runs if r["status"] != "completed"]
    if bad:
        warnings.append({
            "code": "excluded_runs", "level": "warning",
            "message": f"{len(bad)} run(s) did not complete and are excluded from the"
                       " statistics: " + ", ".join(f"{r['run_key']} ({r['termination']})"
                                                   for r in bad[:5])
                       + (" ..." if len(bad) > 5 else ""),
        })  # fmt: skip
    if any(r.get("metric_version") is None for r in runs):
        warnings.append({
            "code": "no_metric_version", "level": "warning",
            "message": "some runs carry no metric version (live dashboard runs keep counts"
                       " only); only metrics present in every run are comparable",
        })  # fmt: skip
    return warnings


def _ci(xs: list[float]) -> dict:
    n = len(xs)
    m, sd = mean_sd(xs) if n else (math.nan, math.nan)
    half = t95(n - 1) * sd / math.sqrt(n) if n > 1 else None
    clean = lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) else v  # noqa: E731
    return {"n": n, "mean": clean(m), "sd": clean(sd) if n > 1 else None,
            "ci95": clean(half), "min": min(xs) if xs else None,
            "max": max(xs) if xs else None}  # fmt: skip


def compare_runs(
    repo: ExperimentRepository,
    run_keys: list[str],
    group_by: str = "arm",
    metrics: list[str] | None = None,
    reference: str | None = None,
) -> dict:
    if group_by not in GROUP_FIELDS:
        raise ValueError(f"group_by must be one of {GROUP_FIELDS}")
    index = {r["run_key"]: r for r in repo.list_runs()}
    missing = [k for k in run_keys if k not in index]
    if missing:
        raise KeyError(f"unknown runs: {missing[:5]}")
    runs = [index[k] for k in run_keys]
    values = repo.metrics(run_keys)
    ok = [r for r in runs if r["status"] == "completed"]
    if metrics is None:  # metrics present in every completed run
        sets = [set(values[r["run_key"]]) for r in ok]
        metrics = sorted(set.intersection(*sets)) if sets else []
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in ok:
        groups[str(r.get(group_by))].append(r)
    names = sorted(groups)
    if reference is None or reference not in groups:
        reference = "fixed_time" if "fixed_time" in groups else (names[0] if names else None)

    out_metrics = {}
    for m in metrics:
        unit = next((values[r["run_key"]][m]["unit"] for r in ok if m in values[r["run_key"]]), "")
        per_group = {}
        for g in names:
            pts = [(r["run_key"], r.get("profile"), r.get("seed"), values[r["run_key"]][m]["value"])
                   for r in groups[g] if m in values[r["run_key"]]]  # fmt: skip
            xs = [p[3] for p in pts if p[3] is not None]
            per_group[g] = {**_ci(xs), "missing": sum(1 for p in pts if p[3] is None),
                            "points": [{"run_key": k, "profile": pr, "seed": s, "value": v}
                                       for k, pr, s, v in pts]}  # fmt: skip
        paired = {}
        if reference is not None:
            ref = {(p["profile"], p["seed"]): p["value"] for p in per_group[reference]["points"]}
            for g in names:
                if g == reference:
                    continue
                diffs = [p["value"] - ref[(p["profile"], p["seed"])]
                         for p in per_group[g]["points"]
                         if (p["profile"], p["seed"]) in ref and p["value"] is not None
                         and ref[(p["profile"], p["seed"])] is not None]  # fmt: skip
                if diffs:
                    paired[g] = _ci(diffs)
        label, _, lower = METRICS.get(m, (m, unit, None))
        out_metrics[m] = {"label": label, "unit": unit, "lower_is_better": lower,
                          "groups": per_group, "paired_vs_reference": paired}  # fmt: skip
    return {
        "group_by": group_by,
        "reference": reference,
        "groups": {g: len(groups[g]) for g in names},
        "runs_selected": len(runs),
        "runs_used": len(ok),
        "excluded": [{"run_key": r["run_key"], "status": r["status"],
                      "termination": r["termination"]} for r in runs if r not in ok],
        "warnings": comparability(runs, group_by),
        "metrics": out_metrics,
    }  # fmt: skip
