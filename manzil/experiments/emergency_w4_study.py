"""Corridor completion study (workstream W4): Algorithm 2 additions compared with corridor v2.

Three additions from D2 section 5.6 that corridor v2 (task 3.7) did not have yet, each tested
on its own against ``v2`` and then together:

- ``ds_defer`` / ``ds_flush`` / ``ds_both``: downstream-capacity check before activation
  (``MissionConfig.downstream``; see ``manzil/corridor/coordinator.py``).
- ``comp``: bounded compensation plan in recovery (``MissionConfig.compensation``).
- ``sublane``: SUMO's sublane model only (no give-way). It changes every vehicle's lateral
  behaviour, so it is the fair reference for the give-way arm.
- ``giveway_sl``: ordinary vehicles give way (SUMO bluelight device) with the sublane model,
  so they can form a rescue lane. The ambulance still obeys red lights (speed mode 31, every
  stop-line crossing checked).
- ``all``: v2 + ds_both + comp + giveway_sl.
- ``off``: no corridor, for context.

Main setup = the task 3.7 setup (grid, dynamic routing, no incident, dispatch at 1,200 s from
``left0A0`` to ``C2top2``, 900 s warm-up + 900 s), medium and heavy demand, on **new seeds
10-19** (task 3.7 used 0-4; the dev seeds 100-101 are never used for evaluation).

``--stress`` runs a spillback stress case instead, because the downstream check never fires in
the main setup (no exit on the route fills up): static routing (the ambulance cannot avoid the
problem), an obstruction (speed limit 3 m/s) on ``A2B2`` from 900 s, heavy demand, 1,800 s
measurement so every ambulance arrives.

Usage::

    python -m manzil.experiments.emergency_w4_study --out results/fyp2/corridor/fixed_time
    python -m manzil.experiments.emergency_w4_study --controller dqn --out .../dqn
    python -m manzil.experiments.emergency_w4_study --stress --out .../stress_spillback
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from manzil.experiments.batch import check_compatible, read_table, run_batch, write_table
from manzil.experiments.compare import METRICS, markdown, summarise
from manzil.experiments.corridor_v2_study import EXTRA_LABELS, STUDY_METRICS
from manzil.experiments.emergency import MissionConfig
from manzil.experiments.runner import CONTROLLERS, RunConfig

# Corridor v2 written out explicitly, so a later default change cannot move the reference.
V2 = MissionConfig(routing="dynamic", corridor=True, lookahead=2, activate_eta_s=15.0,
                   corridor_min_green_s=5.0, give_way=False)  # fmt: skip
GIVE_WAY = {"sublane": True, "give_way": True}
ARMS = {
    "off": replace(V2, corridor=False),
    "v2": V2,
    "ds_defer": replace(V2, downstream="defer"),
    "ds_flush": replace(V2, downstream="flush"),
    "ds_both": replace(V2, downstream="both"),
    "comp": replace(V2, compensation=True),
    "sublane": replace(V2, sublane=True),
    "giveway_sl": replace(V2, **GIVE_WAY),
    "all": replace(V2, downstream="both", compensation=True, **GIVE_WAY),
}
DEFAULT_ARMS = list(ARMS)
STRESS_ARMS = ["off", "v2", "ds_defer", "ds_flush", "ds_both", "comp"]
SEEDS = list(range(10, 20))
STRESS = {"routing": "static", "incident": "slowdown", "incident_edge": "A2B2",
          "incident_s": 900.0, "incident_speed_mps": 3.0}  # fmt: skip

W4_METRICS = [
    *STUDY_METRICS, "teleports", "collisions", "downstream_deferrals", "downstream_flushes",
    "compensations", "compensation_green_mean_s", "corridor_timeouts",
]  # fmt: skip
METRICS.update(EXTRA_LABELS)
METRICS.update({
    "downstream_deferrals": ("Activations deferred (exit blocked)", "count", None),
    "downstream_flushes": ("Junctions flushed (exit blocked)", "count", None),
    "compensations": ("Compensation plans run", "count", None),
    "compensation_green_mean_s": ("Compensation green served, mean", "s", None),
    "corridor_timeouts": ("Corridor timeouts", "count", True),
    "collisions": ("Collisions", "count", True),
    "teleports": ("Teleports", "count", True),
})  # fmt: skip


def configs(arms, profiles, seeds, controller="fixed_time", stress=False):
    out = []
    for p in profiles:
        for a in arms:
            mission = replace(ARMS[a], **STRESS) if stress else ARMS[a]
            for s in seeds:
                out.append(RunConfig(profile=p, seed=s, controller=controller, warmup_s=900.0,
                                     measure_s=1800.0 if stress else 900.0, mission=mission,
                                     label=a))  # fmt: skip
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arms", nargs="+", default=None, choices=list(ARMS))
    ap.add_argument("--profiles", nargs="+", default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    ap.add_argument("--controller", default="fixed_time", choices=CONTROLLERS)
    ap.add_argument("--stress", action="store_true", help="spillback stress case (see above)")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--summary-only", action="store_true", help="only rebuild summary files")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    arms = a.arms or (STRESS_ARMS if a.stress else DEFAULT_ARMS)
    profiles = a.profiles or (["heavy"] if a.stress else ["medium", "heavy"])
    if a.summary_only:  # re-summarise an existing results.csv
        rows = read_table(a.out / "results.csv")
    else:
        cfgs = configs(arms, profiles, a.seeds, a.controller, a.stress)
        rows = run_batch(cfgs, a.out, a.workers)
        write_table(rows, a.out / "results.csv")
    check_compatible(rows)
    s = summarise(rows, reference="v2", metrics=W4_METRICS)
    (a.out / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    (a.out / "summary.md").write_text(markdown(s, W4_METRICS) + "\n")
    print(markdown(s, W4_METRICS))


if __name__ == "__main__":
    main()
