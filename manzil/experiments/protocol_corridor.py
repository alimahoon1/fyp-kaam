"""Corridor v2 on new seeds: confirm the task 3.7 development-stage estimate (W3).

Task 3.7 chose corridor v2 (``v1`` + 5 s emergency minimum-green truncation) on seeds 0-4
(``results/phase3/corridor_v2/``). Choosing a variant on the same seeds that report its effect
can overstate it. This reruns exactly the same setup (``corridor_v2_study.configs``: 3x3 grid,
dynamic routing, dispatch 1,200 s, ``left0A0`` -> ``C2top2``, 900 + 900 s, medium and heavy,
fixed-time and DQN background signals) with arms ``off``, ``v1`` and ``v2`` on **new** seeds
(default 20-29, never used in task 3.7), and puts the new paired differences next to the
development ones.

Usage::

    python -m manzil.experiments.protocol_corridor --out results/fyp2/protocol/corridor_v2_newseeds
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from manzil.experiments.batch import check_compatible, read_table, run_batch, write_table
from manzil.experiments.compare import summarise
from manzil.experiments.corridor_v2_study import configs  # also registers metric labels
from manzil.experiments.protocol import EVAL_SEEDS, _fmt
from manzil.experiments.runner import REPO_ROOT

ARMS = ["off", "v1", "v2"]
DEV_DIR = REPO_ROOT / "results" / "phase3" / "corridor_v2"
KEY_METRICS = [
    "amb_travel_time_s", "amb_waiting_s", "amb_stops", "amb_red_crossings",
    "fixed_window_queue_mean_veh", "cross_street_wait_veh_s", "waiting_time_mean_s",
    "safety_violations",
]  # fmt: skip
CONTRASTS = [("v2", "off"), ("v2", "v1")]


def contrast_rows(rows: list[dict], stage: str, controller: str) -> list[dict]:
    out = []
    for arm, ref in CONTRASTS:
        sub = [r for r in rows if r["arm"] in (arm, ref)]
        s = summarise(sub, reference=ref, metrics=KEY_METRICS)
        for p in s["profiles"]:
            for m in KEY_METRICS:
                d = s["paired"].get(p, {}).get(arm, {}).get(m)
                a = (s["summary"][p].get(arm) or {}).get(m)
                b = (s["summary"][p].get(ref) or {}).get(m)
                if not d or not a or not b:
                    continue
                ci = d["ci95"] or [None, None]
                out.append({
                    "stage": stage, "controller": controller, "profile": p,
                    "contrast": f"{arm} - {ref}", "metric": m, "n_seeds": d["n"],
                    "seeds": " ".join(map(str, s["summary"][p][arm]["seeds"])),
                    "mean_ref": round(b["mean"], 3), "mean_arm": round(a["mean"], 3),
                    "mean_diff": round(d["mean_diff"], 3),
                    "ci95_low": None if ci[0] is None else round(ci[0], 3),
                    "ci95_high": None if ci[1] is None else round(ci[1], 3),
                    "pct_change": None if d["pct_change"] is None else round(d["pct_change"], 2),
                    "seeds_better": d["seeds_better"],
                })  # fmt: skip
    return out


def markdown(table: list[dict]) -> str:
    idx = {(r["stage"], r["controller"], r["profile"], r["contrast"], r["metric"]): r
           for r in table}  # fmt: skip
    lines = []
    keys = sorted({(r["controller"], r["profile"], r["contrast"]) for r in table},
                  key=lambda k: (k[0], k[1] != "medium", k[2]))  # fmt: skip
    for ctrl, prof, con in keys:
        lines += [f"### {ctrl} background, {prof}: {con}", "",
                  "| Metric | Development, seeds 0-4: Δ [95 % CI], better | "
                  "New seeds: Δ [95 % CI], better | New seeds: ref → arm |",
                  "|---|---|---|---|"]  # fmt: skip
        for m in KEY_METRICS:
            cells = []
            for stage in ("development", "confirmation"):
                r = idx.get((stage, ctrl, prof, con, m))
                if r is None:
                    cells.append("—")
                    continue
                pct = "" if r["pct_change"] in (None, "") else f" ({r['pct_change']:+.1f} %)"
                better = "" if r["seeds_better"] in (None, "") else (
                    f", {r['seeds_better']}/{r['n_seeds']}")  # fmt: skip
                cells.append(f"{r['mean_diff']:+.1f} [{_fmt(r['ci95_low'])}, "
                             f"{_fmt(r['ci95_high'])}]{pct}{better}")  # fmt: skip
            new = idx.get(("confirmation", ctrl, prof, con, m))
            means = f"{_fmt(new['mean_ref'])} → {_fmt(new['mean_arm'])}" if new else "—"
            lines.append(f"| {m} | {cells[0]} | {cells[1]} | {means} |")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--controllers", nargs="+", default=["fixed_time", "dqn"])
    ap.add_argument("--profiles", nargs="+", default=["medium", "heavy"])
    ap.add_argument("--seeds", nargs="+", type=int, default=list(EVAL_SEEDS))
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--report-only", action="store_true", help="reuse existing results.csv")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if set(a.seeds) & set(range(5)):
        raise SystemExit("seeds 0-4 were the development seeds; use new seeds")
    table = []
    for ctrl in a.controllers:
        out = a.out / ctrl
        if not a.report_only:
            rows = run_batch(configs(ARMS, a.profiles, a.seeds, ctrl), out, a.workers)
            check_compatible(rows)
            write_table(rows, out / "results.csv")
        rows = read_table(out / "results.csv")
        table += contrast_rows(rows, "confirmation", ctrl)
        dev = [r for r in read_table(DEV_DIR / ctrl / "results.csv") if r["arm"] in ARMS]
        table += contrast_rows(dev, "development", ctrl)
    write_table(table, a.out / "contrasts.csv")
    md = markdown(table)
    (a.out / "contrasts.md").write_text(md + "\n")
    totals = {}
    for ctrl in a.controllers:
        rows = read_table(a.out / ctrl / "results.csv")
        totals[ctrl] = {k: sum(int(r[k]) for r in rows)
                        for k in ("safety_violations", "amb_red_crossings", "teleports",
                                  "collisions")}  # fmt: skip
        totals[ctrl]["runs"] = len(rows)
    (a.out / "totals.json").write_text(json.dumps(totals, indent=2) + "\n")
    print(json.dumps(totals))
    print(md)


if __name__ == "__main__":
    main()
