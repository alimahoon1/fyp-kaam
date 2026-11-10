"""Compare controllers from a batch results table: summary, paired differences, plots (PLAN 2.3).

Runs are matched by (profile, seed), so each seed sees the same vehicles under every
controller and differences are paired (D2 protocol). For each profile and controller the
summary gives mean and sample SD over seeds; for each controller against the reference
(fixed-time) it gives the mean paired difference, its SD, a 95 % t confidence interval and the
percentage change. With only a few seeds the intervals are wide; that is reported, not hidden.

Usage::

    python -m manzil.experiments.compare results/phase2/comparison/results.csv
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from manzil.experiments.batch import check_compatible, read_table

METRICS = {
    # name: (label, unit, lower is better)
    "travel_time_mean_s": ("Mean travel time", "s", True),
    "travel_time_all_mean_s": ("Mean travel time incl. unfinished", "s", True),
    "waiting_time_mean_s": ("Mean waiting time", "s", True),
    "time_loss_mean_s": ("Mean time loss", "s", True),
    "queue_mean_veh": ("Mean approach queue", "veh", True),
    "queue_max_veh": ("Max approach queue", "veh", True),
    "throughput_veh": ("Throughput", "veh", False),
    "unfinished_veh": ("Unfinished at end", "veh", True),
    "phase_changes": ("Phase changes", "count", None),
    "max_red_s": ("Max red", "s", True),
    # Emergency missions (Phase 3)
    "amb_travel_time_s": ("Ambulance travel time", "s", True),
    "amb_excess_delay_s": ("Ambulance excess delay", "s", True),
    "amb_stops": ("Ambulance stops", "count", True),
    "amb_waiting_s": ("Ambulance time stopped", "s", True),
    "route_revisions": ("Route revisions", "count", None),
    "mission_window_queue_mean_veh": ("Network queue, mission + 300 s", "veh", True),
    "recovery_time_mean_s": ("Junction recovery time", "s", True),
}
DEFAULT_TABLE = [
    "travel_time_mean_s", "travel_time_all_mean_s", "waiting_time_mean_s", "queue_mean_veh",
    "queue_max_veh", "throughput_veh", "max_red_s",
]  # fmt: skip
REFERENCE = REFERENCE_DEFAULT = "fixed_time"
PROFILE_ORDER = ("light", "medium", "heavy", "uneven")

# Two-sided 95 % Student t quantiles by degrees of freedom.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
        9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086, 30: 2.042}  # fmt: skip


def t95(df: int) -> float:
    if df <= 0:
        return math.nan
    keys = sorted(k for k in _T95 if k <= df)
    return _T95[keys[-1]] if df <= 30 else 1.96


def mean_sd(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else math.nan
    return m, sd


def _val(r, m):
    v = r.get(m)
    return None if v in ("", None) else float(v)


def summarise(rows: list[dict], reference: str = REFERENCE, metrics=None) -> dict:
    REFERENCE = reference  # noqa: N806 - local alias keeps the code below readable
    metrics = metrics or list(METRICS)
    check_compatible(rows)
    by = defaultdict(dict)  # (profile, controller) -> seed -> row
    for r in rows:
        key = (r["profile"], r.get("arm") or r["controller"])
        if r["seed"] in by[key]:
            raise ValueError(f"duplicate run for {key} seed {r['seed']}")
        by[key][r["seed"]] = r
    profiles = [p for p in PROFILE_ORDER if any(k[0] == p for k in by)]
    controllers = sorted(
        {k[1] for k in by}, key=lambda c: (c != REFERENCE, not c.startswith("fixed"), c)
    )
    out = {"profiles": profiles, "controllers": controllers, "reference": REFERENCE,
           "metrics": metrics, "summary": {}, "paired": {}}  # fmt: skip
    metrics = [m for m in metrics if any(_val(r, m) is not None for r in rows)]
    out["metrics"] = metrics
    for p in profiles:
        for c in controllers:
            runs = by.get((p, c), {})
            if not runs:
                continue
            entry = {"seeds": sorted(runs)}
            for m in metrics:
                vals = [v for r in runs.values() if (v := _val(r, m)) is not None]
                entry[m] = (
                    {"mean": mean_sd(vals)[0], "sd": mean_sd(vals)[1], "n": len(vals)}
                    if vals else None
                )  # fmt: skip
            out["summary"].setdefault(p, {})[c] = entry
            ref = by.get((p, REFERENCE), {})
            if c == REFERENCE or not ref:
                continue
            if set(runs) != set(ref):
                raise ValueError(f"{p}: {c} and {REFERENCE} were not run on the same seeds")
            paired = {}
            for m in metrics:
                pairs = [(_val(runs[s], m), _val(ref[s], m)) for s in sorted(runs)]
                pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
                if not pairs:
                    continue
                diffs = [a - b for a, b in pairs]
                d, sd = mean_sd(diffs)
                half = t95(len(diffs) - 1) * sd / math.sqrt(len(diffs)) if len(diffs) > 1 else None
                base = sum(b for _, b in pairs) / len(pairs)
                paired[m] = {
                    "mean_diff": d,
                    "sd_diff": sd,
                    "ci95": [d - half, d + half] if half is not None else None,
                    "pct_change": 100 * d / base if base else None,
                    "seeds_better": _count_better(diffs, METRICS[m][2]),
                    "n": len(diffs),
                }
            out["paired"].setdefault(p, {})[c] = paired
    return out


def _count_better(diffs, lower_is_better) -> int | None:
    if lower_is_better is None:
        return None
    return sum(1 for d in diffs if (d < 0 if lower_is_better else d > 0))


def _fmt(x, nd=1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def markdown(summary: dict, metrics=None) -> str:
    REFERENCE = summary.get("reference", REFERENCE_DEFAULT)  # noqa: N806
    metrics = [m for m in (metrics or DEFAULT_TABLE) if m in summary["metrics"]]
    lines = []
    for p in summary["profiles"]:
        lines += [f"### {p}", ""]
        head = "| Metric | " + " | ".join(summary["controllers"]) + " |"
        extra = [c for c in summary["controllers"] if c != REFERENCE]
        head += "".join(f" {c} − {REFERENCE} (95 % CI) | Seeds better |" for c in extra)
        lines += [head, "|" + "---|" * (head.count("|") - 1)]
        for m in metrics:
            label, unit, _ = METRICS[m]
            row = f"| {label} ({unit}) |"
            for c in summary["controllers"]:
                s = (summary["summary"][p].get(c) or {}).get(m)
                row += f" {_fmt(s['mean'])} ± {_fmt(s['sd'])} |" if s else " — |"
            for c in extra:
                d = summary["paired"].get(p, {}).get(c, {}).get(m)
                if not d:
                    row += " — | — |"
                    continue
                ci = d["ci95"]
                ci_s = f"[{_fmt(ci[0])}, {_fmt(ci[1])}]" if ci else "n/a"
                pct = f", {d['pct_change']:+.1f} %" if d["pct_change"] is not None else ""
                better = "—" if d["seeds_better"] is None else f"{d['seeds_better']}/{d['n']}"
                row += f" {d['mean_diff']:+.1f} {ci_s}{pct} | {better} |"
            lines.append(row)
        lines.append("")
    return "\n".join(lines)


def plot(rows: list[dict], summary: dict, path: Path, metrics=None, title=None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = metrics or DEFAULT_TABLE[:4]
    profiles, controllers = summary["profiles"], summary["controllers"]
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
    width = 0.8 / len(controllers)
    for ax, m in zip(axes.flat, metrics, strict=False):
        label, unit, _ = METRICS[m]
        for ci, c in enumerate(controllers):
            xs, means, sds = [], [], []
            for pi, p in enumerate(profiles):
                s = summary["summary"][p].get(c)
                if not s or not s.get(m):
                    continue
                x = pi + (ci - (len(controllers) - 1) / 2) * width
                xs.append(x)
                means.append(s[m]["mean"])
                sds.append(0 if math.isnan(s[m]["sd"]) else s[m]["sd"])
                seeds = [
                    v
                    for r in rows
                    if r["profile"] == p
                    and (r.get("arm") or r["controller"]) == c
                    and (v := _val(r, m)) is not None
                ]
                ax.scatter([x] * len(seeds), seeds, s=9, color="black", zorder=3, alpha=0.6)
            ax.bar(xs, means, width, yerr=sds, capsize=3, label=c, color=colors[ci % 4])
        ax.set_xticks(range(len(profiles)), profiles)
        ax.set_title(label)
        ax.set_ylabel(unit)
        ax.grid(axis="y", alpha=0.3)
    axes.flat[0].legend()
    n = len(next(iter(next(iter(summary["summary"].values())).values()))["seeds"])
    fig.suptitle(
        f"{title or 'Synthetic 3×3 grid (SUMO)'}: bars = mean over {n} seeds, "
        "error bars = SD, dots = seeds"
    )
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("table", type=Path)
    ap.add_argument("--out-dir", type=Path, default=None, help="default: next to the table")
    a = ap.parse_args(argv)
    out = a.out_dir or a.table.parent
    rows = read_table(a.table)
    s = summarise(rows)
    (out / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    (out / "summary.md").write_text(markdown(s) + "\n")
    plot(rows, s, out / "comparison.png")
    print(markdown(s))


if __name__ == "__main__":
    main()
