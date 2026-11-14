"""Tables and plots for the corridor improvement study (PLAN task 3.7).

Reads the ``results.csv`` files written by ``corridor_v2_study`` and writes, next to them:

- ``key_table.csv`` / ``key_table.md``: per background controller, profile and arm, the mean
  over seeds of the key metrics, plus the paired difference against ``v1`` and how many seeds
  improved (lower is better for every metric listed).
- ``stop_reasons.png``: seconds the ambulance stood still, split by reason (stacked bars).
- ``response_and_cost.png``: ambulance response time (per seed + mean) and the
  ordinary-traffic cost (cross-street queueing and network queue, both over the same 600 s).

Usage::

    python -m manzil.experiments.corridor_v2_report results/phase3/corridor_v2
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

KEY = [
    ("amb_travel_time_s", "Response time (s)"),
    ("amb_waiting_s", "Time stopped (s)"),
    ("amb_stopped_red_corridor_s", "Stopped: red, corridor junction (s)"),
    ("amb_stopped_red_outside_lookahead_s", "Stopped: red, outside look-ahead (s)"),
    ("amb_stopped_red_no_corridor_s", "Stopped: red, corridor off (s)"),
    ("amb_stopped_queue_s", "Stopped: queue in front (s)"),
    ("amb_stopped_other_s", "Stopped: other (s)"),
    ("amb_stops", "Stops"),
    ("amb_red_crossings", "Red-light crossings"),
    ("mission_window_queue_mean_veh", "Network queue, mission + 300 s (veh)"),
    ("fixed_window_queue_mean_veh", "Network queue, dispatch + 600 s (veh)"),
    ("cross_street_wait_veh_s", "Cross-street queueing, dispatch + 600 s (veh·s)"),
    ("waiting_time_mean_s", "Mean waiting, all trips (s)"),
    ("teleports", "Teleports"),
    ("safety_violations", "Safety violations"),
]
# Stop-reason groups, in the fixed categorical order of the reference palette (dataviz skill).
GROUPS = [
    ("amb_stopped_red_corridor_s", "red, corridor junction", "#2a78d6"),
    ("amb_stopped_red_outside_lookahead_s", "red, outside look-ahead", "#eb6834"),
    ("amb_stopped_queue_s", "queue in front", "#1baf7a"),
    ("amb_stopped_other_s", "other (inside junction, yielding)", "#eda100"),
    ("amb_stopped_red_no_corridor_s", "red, corridor off", "#e87ba4"),
]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _f(v):
    return None if v in ("", None) else float(v)


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def key_rows(rows: list[dict], study: str, reference: str = "v1") -> list[dict]:
    out = []
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    for prof in ("medium", "heavy"):
        by = {a: {int(r["seed"]): r for r in rows if r["arm"] == a and r["profile"] == prof}
              for a in arms}  # fmt: skip
        if not any(by.values()):
            continue
        for a in arms:
            row = {"study": study, "profile": prof, "arm": a, "seeds": len(by[a])}
            for m, _ in KEY:
                xs = [_f(r.get(m)) for r in by[a].values()]
                xs = [x for x in xs if x is not None]
                row[m] = round(st.mean(xs), 2) if xs else None
                if reference in by and a != reference and xs:
                    pairs = [(_f(by[a][s].get(m)), _f(by[reference][s].get(m)))
                             for s in by[a] if s in by[reference]]  # fmt: skip
                    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
                    if pairs:
                        row[f"{m}_diff"] = round(st.mean(x - y for x, y in pairs), 2)
                        row[f"{m}_better"] = f"{sum(x < y for x, y in pairs)}/{len(pairs)}"
            out.append(row)
    return out


def write_key_table(krows: list[dict], out: Path) -> None:
    fields = list(dict.fromkeys(k for r in krows for k in r))
    with (out / "key_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(krows)
    show = ["amb_travel_time_s", "amb_waiting_s", "amb_stopped_red_corridor_s",
            "amb_stopped_red_outside_lookahead_s", "amb_stopped_queue_s", "amb_stops",
            "cross_street_wait_veh_s", "fixed_window_queue_mean_veh", "teleports",
            "safety_violations"]  # fmt: skip
    labels = dict(KEY)
    lines = []
    for study in dict.fromkeys(r["study"] for r in krows):
        for prof in ("medium", "heavy"):
            rs = [r for r in krows if r["study"] == study and r["profile"] == prof]
            if not rs:
                continue
            lines += [f"### {study}, {prof} (mean of {rs[0]['seeds']} seeds; "
                      "Δ = paired difference vs v1, seeds better)", "",
                      "| Arm | " + " | ".join(labels[m] for m in show) + " |",
                      "|---|" + "---|" * len(show)]  # fmt: skip
            for r in rs:
                cells = []
                for m in show:
                    v = r.get(m)
                    c = "—" if v is None else f"{v:g}"
                    if f"{m}_diff" in r:
                        c += f" (Δ {r[f'{m}_diff']:+g}, {r[f'{m}_better']})"
                    cells.append(c)
                lines.append(f"| {r['arm']} | " + " | ".join(cells) + " |")
            lines.append("")
    (out / "key_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_stop_reasons(studies: dict[str, list[dict]], path: Path) -> None:
    panels = [(s, p) for s in studies for p in ("medium", "heavy")]
    fig, axes = plt.subplots(len(studies), 2, figsize=(12, 3.6 * len(studies)), squeeze=False)
    for ax, (study, prof) in zip(axes.flat, panels, strict=True):
        rows = [r for r in studies[study] if r["profile"] == prof]
        arms = list(dict.fromkeys(r["arm"] for r in rows))
        bottom = [0.0] * len(arms)
        for m, label, color in GROUPS:
            vals = [st.mean(_f(r[m]) or 0 for r in rows if r["arm"] == a) for a in arms]
            ax.bar(arms, vals, bottom=bottom, color=color, label=label, width=0.62,
                   edgecolor="white", linewidth=1.5)  # fmt: skip
            bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
        for i, b in enumerate(bottom):
            ax.text(i, b + max(bottom) * 0.015, f"{b:.0f}", ha="center", va="bottom",
                    fontsize=8, color=INK)  # fmt: skip
        ax.set_title(f"{study} signals, {prof} demand", fontsize=10, color=INK, loc="left")
        ax.set_ylabel("Ambulance time stopped (s, mean of 5 seeds)", fontsize=8, color=MUTED)
        ax.tick_params(axis="x", rotation=30)
        _style(ax)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.suptitle("Why the ambulance stands still, by corridor variant", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False, fontsize=8)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_response_and_cost(studies: dict[str, list[dict]], path: Path) -> None:
    metrics = [("amb_travel_time_s", "Ambulance response time (s)"),
               ("cross_street_wait_veh_s", "Cross-street queueing, 600 s (veh·s)"),
               ("fixed_window_queue_mean_veh", "Network queue, 600 s (veh)")]  # fmt: skip
    rows_n = len(studies) * 2
    fig, axes = plt.subplots(rows_n, 3, figsize=(14, 2.9 * rows_n), squeeze=False)
    r_i = 0
    for study, rows in studies.items():
        for prof in ("medium", "heavy"):
            rs = [r for r in rows if r["profile"] == prof]
            arms = list(dict.fromkeys(r["arm"] for r in rs))
            for c_i, (m, label) in enumerate(metrics):
                ax = axes[r_i][c_i]
                for i, a in enumerate(arms):
                    xs = [_f(r[m]) for r in rs if r["arm"] == a and _f(r[m]) is not None]
                    ax.scatter([i] * len(xs), xs, s=14, color="#86b6ef", zorder=2)
                    if xs:
                        ax.plot([i - 0.28, i + 0.28], [st.mean(xs)] * 2, color="#1c5cab",
                                linewidth=2, zorder=3)  # fmt: skip
                ax.set_xticks(range(len(arms)), arms, rotation=30)
                ax.set_title(f"{label} · {study}, {prof}", fontsize=9, color=INK, loc="left")
                _style(ax)
            r_i += 1
    fig.suptitle("Ambulance benefit vs ordinary-traffic cost (dots = seeds, bar = mean)",
                 y=1.0, fontsize=12)  # fmt: skip
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", type=Path)
    a = ap.parse_args(argv)
    studies = {
        name: load(a.root / name / "results.csv")
        for name in ("fixed_time", "dqn")
        if (a.root / name / "results.csv").is_file()
    }
    krows = []
    for name, rows in studies.items():
        krows += key_rows(rows, name)
    for extra in ("demo_scenario", "dqn_before_fix"):
        p = a.root / extra / "results.csv"
        if p.is_file():
            krows += key_rows(load(p), extra)
    write_key_table(krows, a.root)
    plot_stop_reasons(studies, a.root / "stop_reasons.png")
    plot_response_and_cost(studies, a.root / "response_and_cost.png")
    print(f"wrote key_table.csv/.md, stop_reasons.png, response_and_cost.png in {a.root}")


if __name__ == "__main__":
    main()
