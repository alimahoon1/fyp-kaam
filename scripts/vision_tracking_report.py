"""Figures and the MAE table for vision tasks V.4 / V.5 from the Kaggle tracking outputs.

Reads results/vision/tracking/{counts.csv, queue.csv, summary.json} (pulled back from the
`manzil-yolo-track` kernel) and writes, in the same folder:
  * mae_table.csv / mae_table.md - counting error per class and direction, and the queue error;
  * count_pred_vs_true.png       - predicted vs true count per test sequence;
  * count_error_per_sequence.png - signed count error per sequence;
  * queue_sample.png             - stopped-vehicle (queue) estimate vs truth on the sample clip.

    python scripts/vision_tracking_report.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

D = Path(__file__).resolve().parents[1] / "results" / "vision" / "tracking"
PRED, TRUE = "#2a78d6", "#eb6834"  # categorical slots 1 and 2 of the dataviz reference palette
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def read_csv(name):
    with open(D / name) as f:
        return list(csv.DictReader(f))


def fmt(v, pct=False):
    if v is None:
        return "–"
    return f"{100 * v:.1f} %" if pct else f"{v:.2f}"


def main():
    counts = read_csv("counts.csv")
    queue = read_csv("queue.csv")
    summary = json.loads((D / "summary.json").read_text())

    # ---- MAE table
    rows = [("all vehicles", summary["total"])]
    rows += [(n, m) for n, m in summary["per_class"].items()]
    rows += [(f"direction {d}", m) for d, m in summary["per_direction"].items()]
    header = ["group", "clips", "true", "predicted", "MAE", "bias", "RMSE", "WAPE", "MAPE",
              "exact clips"]
    table = []
    for name, m in rows:
        table.append([name, m["n"], m["total_true"], m["total_pred"], fmt(m["mae"]),
                      fmt(m["bias"]), fmt(m["rmse"]), fmt(m["wape"], True), fmt(m["mape"], True),
                      m["exact_clips"]])
    with open(D / "mae_table.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(table)
    q = summary["queue"]
    md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in table]
    qm = q["mean_queue_error"]
    md += ["", "Queue (stopped vehicles), mean over sequences of the per-frame absolute error: "
               f"**{q['mae_per_frame_mean_over_seqs']:.2f} vehicles**; MAE of the per-sequence "
               f"mean queue: {qm['mae']:.2f} (bias {qm['bias']:+.2f})."]
    (D / "mae_table.md").write_text("\n".join(md) + "\n")

    # ---- predicted vs true per sequence
    t = [int(r["true_total"]) for r in counts]
    p = [int(r["pred_total"]) for r in counts]
    hi = max(t + p) * 1.08 + 1
    fig, ax = plt.subplots(figsize=(5.2, 5))
    style(ax)
    ax.plot([0, hi], [0, hi], color=INK2, lw=1, ls="--", label="perfect count")
    ax.scatter(t, p, s=42, color=PRED, edgecolor="white", lw=1.5, zorder=3,
               label="test sequence")
    ax.set_xlim(0, hi)
    ax.set_ylim(0, hi)
    ax.set_xlabel("True line crossings (UA-DETRAC track ids)", color=INK)
    ax.set_ylabel("Counted by YOLO11s + ByteTrack", color=INK)
    m = summary["total"]
    ax.set_title(f"Vehicle counts per test sequence (n = {m['n']})\n"
                 f"MAE {m['mae']:.2f}, WAPE {100 * m['wape']:.1f} %", color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(D / "count_pred_vs_true.png", dpi=150)
    plt.close(fig)

    # ---- signed error per sequence
    order = sorted(range(len(counts)), key=lambda i: t[i])
    err = [p[i] - t[i] for i in order]
    fig, ax = plt.subplots(figsize=(10, 4))
    style(ax)
    ax.bar(range(len(err)), err, color=PRED, width=0.75, edgecolor="white", lw=1)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xticks(range(len(err)))
    ax.set_xticklabels([f"{counts[i]['sequence'][4:]} ({t[i]})" for i in order], rotation=90,
                       fontsize=7)
    ax.set_ylabel("Counted − true", color=INK)
    ax.set_xlabel("Test sequence (true count), sorted by true count", color=INK)
    ax.set_title("Signed counting error per sequence", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(D / "count_error_per_sequence.png", dpi=150)
    plt.close(fig)

    # ---- queue on the sample sequence
    s = summary["sample_sequence"]
    qs = [r for r in queue if r["sequence"] == s]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    style(ax)
    sec = [float(r["second"]) for r in qs]
    ax.plot(sec, [int(r["true_queue"]) for r in qs], color=TRUE, lw=2,
            label="true (DETRAC tracks)")
    ax.plot(sec, [int(r["pred_queue"]) for r in qs], color=PRED, lw=2,
            label="estimated (YOLO + ByteTrack)")
    ax.set_xlabel("Time (s)", color=INK)
    ax.set_ylabel("Stopped vehicles", color=INK)
    ax.set_title(f"Queue estimate (stopped vehicles in view), sequence {s}", color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(D / "queue_sample.png", dpi=150)
    plt.close(fig)
    print((D / "mae_table.md").read_text())


if __name__ == "__main__":
    main()
