"""Tables and plot for the W4 corridor completion study.

Reads ``<root>/<study>/results.csv`` (written by ``emergency_w4_study``) for the studies
``fixed_time``, ``dqn`` and ``stress_spillback`` and writes into ``<root>``:

- ``key_table.csv`` / ``key_table.md``: per study, profile and arm the mean over seeds of the
  key metrics, the paired difference against ``v2`` (mean, 95 % CI) and how many seeds improved
  (lower is better for every metric listed).
- ``response_and_cost.png``: paired change vs ``v2`` in ambulance response time (s) and in
  cross-street queueing (%), mean with 95 % CI, per arm and study.

Usage::

    python -m manzil.experiments.emergency_w4_report results/fyp2/corridor
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from manzil.experiments.compare import t95  # noqa: E402

STUDIES = ("fixed_time", "dqn", "stress_spillback")
REFERENCE = "v2"
KEY = [
    ("amb_travel_time_s", "Response time (s)"),
    ("amb_insertion_delay_s", "Insertion wait (s)"),
    ("amb_waiting_s", "Time stopped (s)"),
    ("amb_red_crossings", "Red-light crossings"),
    ("cross_street_wait_veh_s", "Cross-street queueing, dispatch + 600 s (veh·s)"),
    ("fixed_window_queue_mean_veh", "Network queue, dispatch + 600 s (veh)"),
    ("waiting_time_mean_s", "Mean waiting, all trips (s)"),
    ("recovery_time_mean_s", "Recovery time, mean (s)"),
    ("downstream_deferrals", "Activations deferred"),
    ("downstream_flushes", "Junctions flushed"),
    ("compensations", "Compensation plans"),
    ("teleports", "Teleports"),
    ("collisions", "Collisions"),
    ("safety_violations", "Safety violations"),
]
# Categorical slots 1-4 of the reference palette (dataviz skill), fixed order per study cell.
CELLS = [
    (("fixed_time", "medium"), "fixed-time, medium", "#2a78d6"),
    (("fixed_time", "heavy"), "fixed-time, heavy", "#eb6834"),
    (("dqn", "medium"), "DQN, medium", "#1baf7a"),
    (("dqn", "heavy"), "DQN, heavy", "#eda100"),
]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _f(v):
    return None if v in ("", None) else float(v)


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def paired(rows, arm, metric, pct=False):
    """Paired difference arm - v2 over common seeds: (mean, ci_half, n_better, n)."""
    by = {
        a: {r["seed"]: _f(r.get(metric)) for r in rows if r["arm"] == a} for a in (arm, REFERENCE)
    }
    seeds = [s for s in by[arm] if s in by[REFERENCE]]
    pairs = [(by[arm][s], by[REFERENCE][s]) for s in seeds]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None and (b or not pct)]
    if not pairs:
        return None
    d = [100 * (a - b) / b if pct else a - b for a, b in pairs]
    half = t95(len(d) - 1) * st.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    return st.mean(d), half, sum(x < 0 for x in d), len(d)


def key_rows(rows: list[dict], study: str) -> list[dict]:
    out = []
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    for prof in ("medium", "heavy"):
        pr = [r for r in rows if r["profile"] == prof]
        if not pr:
            continue
        for a in arms:
            ar = [r for r in pr if r["arm"] == a]
            row = {"study": study, "profile": prof, "arm": a, "seeds": len(ar)}
            for m, _ in KEY:
                xs = [x for r in ar if (x := _f(r.get(m))) is not None]
                row[m] = round(st.mean(xs), 2) if xs else None
                row[f"{m}_unfinished"] = len(ar) - len(xs) if m == "amb_travel_time_s" else None
                if a != REFERENCE and (p := paired(pr, a, m)):
                    row[f"d_{m}"] = round(p[0], 2)
                    row[f"d_{m}_ci95"] = round(p[1], 2)
                    row[f"d_{m}_better"] = f"{p[2]}/{p[3]}"
            if a != REFERENCE and (p := paired(pr, a, "cross_street_wait_veh_s", pct=True)):
                row["d_cross_street_pct"] = round(p[0], 1)
            out.append({k: v for k, v in row.items() if v is not None})
    return out


def _fmt(row, m, nd=1):
    v = row.get(m)
    return "—" if v is None else f"{v:.{nd}f}"


def markdown(table: list[dict]) -> str:
    head = ("| Study | Demand | Arm | Response (s) | Δ vs v2 (95 % CI), seeds better | "
            "Insertion wait (s) | Cross-street Δ | Network queue Δ (veh) | Mean wait Δ (s) | "
            "Teleports | Collisions | Violations | Red crossings |")  # fmt: skip
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for r in table:
        if "d_amb_travel_time_s" in r:
            d = (f"{r['d_amb_travel_time_s']:+.1f} (±{r['d_amb_travel_time_s_ci95']:.1f}), "
                 f"{r['d_amb_travel_time_s_better']}")  # fmt: skip
        else:
            d = "reference" if r["arm"] == REFERENCE else "—"
        unf = r.get("amb_travel_time_s_unfinished", 0)
        resp = _fmt(r, "amb_travel_time_s") + (f" ({unf} not arrived)" if unf else "")
        cs = f"{r['d_cross_street_pct']:+.1f} %" if "d_cross_street_pct" in r else "—"
        q = (
            f"{r['d_fixed_window_queue_mean_veh']:+.1f}"
            if "d_fixed_window_queue_mean_veh" in r
            else "—"
        )
        w = f"{r['d_waiting_time_mean_s']:+.1f}" if "d_waiting_time_mean_s" in r else "—"
        lines.append(
            f"| {r['study']} | {r['profile']} | {r['arm']} | {resp} | {d} | "
            f"{_fmt(r, 'amb_insertion_delay_s')} | {cs} | {q} | {w} | "
            f"{_fmt(r, 'teleports', 2)} | {_fmt(r, 'collisions', 2)} | "
            f"{_fmt(r, 'safety_violations', 0)} | {_fmt(r, 'amb_red_crossings', 0)} |"
        )  # fmt: skip
    return "\n".join(lines)


def plot(data: dict, path: Path) -> None:
    arms = [a for a in dict.fromkeys(r["arm"] for rows in data.values() for r in rows)
            if a not in (REFERENCE, "off")]  # fmt: skip
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * len(arms) + 2.2), sharey=True)
    panels = [
        ("amb_travel_time_s", False, "Ambulance response time, change vs v2 (s)"),
        ("cross_street_wait_veh_s", True, "Cross-street queueing, change vs v2 (%)"),
    ]
    n = len(CELLS)
    for ax, (metric, pct, title) in zip(axes, panels, strict=True):
        for k, ((study, prof), label, color) in enumerate(CELLS):
            rows = [r for r in data.get(study, []) if r["profile"] == prof]
            for i, a in enumerate(arms):
                p = paired(rows, a, metric, pct) if rows else None
                if not p:
                    continue
                y = i + (k - (n - 1) / 2) * 0.17
                ax.errorbar(p[0], y, xerr=p[1], fmt="o", ms=6, color=color, ecolor=color,
                            elinewidth=2, capsize=0, mec="white", mew=1,
                            label=label if i == 0 else None)  # fmt: skip
        ax.axvline(0, color=MUTED, lw=1)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.grid(axis="x", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=9, length=0)
    axes[0].set_yticks(range(len(arms)), arms)
    axes[0].invert_yaxis()
    axes[0].legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.06), ncol=4)
    fig.text(0.01, 0.005, "Mean of the paired differences over seeds 10-19, bars = 95 % CI. "
             "Left of 0 = better (faster ambulance / less cross-street queueing).",
             fontsize=8, color=MUTED)  # fmt: skip
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", type=Path)
    a = ap.parse_args(argv)
    data = {s: load(a.root / s / "results.csv") for s in STUDIES
            if (a.root / s / "results.csv").is_file()}  # fmt: skip
    table = [row for s, rows in data.items() for row in key_rows(rows, s)]
    fields = list(dict.fromkeys(k for r in table for k in r))
    with (a.root / "key_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(table)
    md = markdown(table)
    (a.root / "key_table.md").write_text(md + "\n", encoding="utf-8")
    plot(data, a.root / "response_and_cost.png")
    print(md)


if __name__ == "__main__":
    main()
