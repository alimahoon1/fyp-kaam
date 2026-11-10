"""Emergency experiments (PLAN task 3.6, D2 Table 5.1), signal policy fixed (tuned fixed-time).

1. **routing**: static vs dynamic route, corridor off. An obstruction (speed limit 2 m/s) is
   placed at 1,000 s on ``A1A2``, an edge of the route that static routing chooses on free-flow
   costs, so the comparison asks whether live costs avoid a reported incident.
2. **corridor**: the same dynamic routing without and with the moving green corridor, no
   incident. Ordinary-traffic impact is the network queue from dispatch until 300 s after
   arrival, plus the usual whole-window metrics.

Every arm sees the same seeded background demand. The ambulance departs at 1,200 s from the
south-west corner (``left0A0``) to the north-east exit (``C2top2``). Runs: 900 s warm-up, then
1,800 s (routing) or 900 s (corridor) of measurement.

Usage::

    python -m manzil.experiments.emergency_study --seeds 0 1 2 3 4 --out results/phase3
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from manzil.experiments.batch import check_compatible, run_batch, write_table
from manzil.experiments.compare import markdown, plot, summarise
from manzil.experiments.emergency import MissionConfig
from manzil.experiments.runner import RunConfig

BASE_MISSION = MissionConfig()
OBSTRUCTION = {"incident": "slowdown", "incident_edge": "A1A2", "incident_s": 1000.0}
AMB_METRICS = [
    "amb_travel_time_s", "amb_excess_delay_s", "amb_stops", "amb_waiting_s",
    "route_revisions", "mission_window_queue_mean_veh", "waiting_time_mean_s",
    "queue_mean_veh", "recovery_time_mean_s",
]  # fmt: skip

EXPERIMENTS = {
    "routing": {
        "reference": "static",
        # Long enough for a static-route ambulance stuck behind the obstruction in heavy
        # demand to finish: 1,500 s after dispatch (900 s was not enough on 4 of 5 seeds).
        "measure_s": 1800.0,
        "arms": {
            "static": replace(BASE_MISSION, routing="static", **OBSTRUCTION),
            "dynamic": replace(BASE_MISSION, routing="dynamic", **OBSTRUCTION),
        },
        "plot": ["amb_travel_time_s", "amb_stops", "amb_waiting_s",
                 "mission_window_queue_mean_veh"],
    },
    "corridor": {
        "reference": "corridor_off",
        "measure_s": 900.0,
        "arms": {
            "corridor_off": replace(BASE_MISSION, routing="dynamic", corridor=False),
            "corridor_on": replace(BASE_MISSION, routing="dynamic", corridor=True),
        },
        "plot": ["amb_travel_time_s", "amb_stops", "mission_window_queue_mean_veh",
                 "waiting_time_mean_s"],
    },
}  # fmt: skip


def configs_for(name: str, profiles, seeds, warmup_s=900.0) -> list[RunConfig]:
    exp = EXPERIMENTS[name]
    measure_s = exp["measure_s"]
    return [
        RunConfig(profile=p, seed=s, warmup_s=warmup_s, measure_s=measure_s, mission=m, label=arm)
        for p in profiles
        for arm, m in exp["arms"].items()
        for s in seeds
    ]


def run_study(names, profiles, seeds, out_root: Path, workers=0) -> dict:
    results = {}
    for name in names:
        out = Path(out_root) / name
        rows = run_batch(configs_for(name, profiles, seeds), out, workers)
        check_compatible(rows)
        write_table(rows, out / "results.csv")
        exp = EXPERIMENTS[name]
        s = summarise(rows, reference=exp["reference"], metrics=AMB_METRICS)
        (out / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
        (out / "summary.md").write_text(markdown(s, AMB_METRICS) + "\n")
        plot(rows, s, out / f"{name}.png", exp["plot"], title=f"Emergency experiment: {name}")
        results[name] = s
    return results


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--experiments", nargs="+", default=list(EXPERIMENTS), choices=EXPERIMENTS)
    ap.add_argument("--profiles", nargs="+", default=["medium", "heavy"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    res = run_study(a.experiments, a.profiles, a.seeds, a.out, a.workers)
    for name, s in res.items():
        print(f"## {name}\n")
        print(markdown(s, AMB_METRICS))


if __name__ == "__main__":
    main()
