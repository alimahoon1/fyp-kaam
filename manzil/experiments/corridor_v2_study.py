"""Corridor improvement study (PLAN task 3.7): why the ambulance still stops, and what helps.

Same setup as the Phase 3 corridor experiment (``emergency_study``, experiment ``corridor``):
3x3 grid, tuned fixed-time signals for ordinary traffic, dynamic routing, no incident, the
ambulance dispatched at 1,200 s from ``left0A0`` to ``C2top2``, 900 s warm-up + 900 s
measurement, medium and heavy demand, seeds 0-4. Every arm sees the same seeded demand.

Arms (one change at a time against ``v1``, then combined):

- ``off``: no corridor (reference for the ordinary-traffic cost).
- ``v1``: the Phase 3 corridor (look-ahead 2, activation at ETA <= 15 s + queue clearance).
- ``early25`` / ``early30``: activation at 25 / 30 s, look-ahead 3.
- ``trunc5``: emergency truncation of minimum green to 5 s for corridor requests only
  (yellow 3 s and all-red 2 s always kept).
- ``giveway``: ordinary vehicles give way (SUMO bluelight device); the ambulance still stops at
  red (speed mode 31 set again, and every stop-line crossing is checked: ``amb_red_crossings``).
- ``early30_trunc5``: early30 + trunc5. ``combined``: early30 + trunc5 + giveway.
- ``v2``: the new default (MissionConfig defaults + scenario signals.json): v1 + trunc5 (and
  the route-index fix, which is in every arm because it is a bug fix, not a parameter).

``--demo`` instead replays the Phase 5 dashboard demo scenario headless: DQN signals, heavy
demand, one 3,600 s run without warm-up (as the live dashboard does), ambulance dispatched at
411 s, road ``B0B1`` (on its first route) closed 2 s later, arms ``off``, ``v1`` and ``v2``.

Usage::

    python -m manzil.experiments.corridor_v2_study --out results/phase3/corridor_v2/fixed_time
    python -m manzil.experiments.corridor_v2_study --controller dqn --out .../dqn
    python -m manzil.experiments.corridor_v2_study --demo --out .../demo_scenario
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from manzil.experiments.batch import check_compatible, run_batch, write_table
from manzil.experiments.compare import METRICS, markdown, summarise
from manzil.experiments.emergency import MissionConfig
from manzil.experiments.runner import CONTROLLERS, RunConfig

# The Phase 3 corridor as it was before task 3.7 (explicit, so a later default change
# does not silently change this reference arm).
V1 = MissionConfig(routing="dynamic", corridor=True, lookahead=2, activate_eta_s=15.0,
                   corridor_min_green_s=10.0, give_way=False)  # fmt: skip
ARMS = {
    "off": replace(V1, corridor=False),
    "v1": V1,
    "early25": replace(V1, lookahead=3, activate_eta_s=25.0),
    "early30": replace(V1, lookahead=3, activate_eta_s=30.0),
    "trunc5": replace(V1, corridor_min_green_s=5.0),
    "giveway": replace(V1, give_way=True),
    "early30_trunc5": replace(V1, lookahead=3, activate_eta_s=30.0, corridor_min_green_s=5.0),
    "combined": replace(V1, lookahead=3, activate_eta_s=30.0, corridor_min_green_s=5.0,
                        give_way=True),
    "v2": MissionConfig(routing="dynamic", corridor=True),  # the defaults chosen in task 3.7
}  # fmt: skip
DEFAULT_ARMS = list(ARMS)

STOP_GROUP_METRICS = [
    "amb_stopped_red_corridor_s", "amb_stopped_red_outside_lookahead_s",
    "amb_stopped_queue_s", "amb_stopped_other_s", "amb_stopped_red_no_corridor_s",
]  # fmt: skip
STUDY_METRICS = [
    "amb_travel_time_s", "amb_excess_delay_s", "amb_waiting_s", "amb_stops",
    *STOP_GROUP_METRICS, "amb_red_crossings",
    "mission_window_queue_mean_veh", "fixed_window_queue_mean_veh", "cross_street_wait_veh_s",
    "waiting_time_mean_s", "recovery_time_mean_s", "safety_violations",
]  # fmt: skip
EXTRA_LABELS = {
    "amb_stopped_red_corridor_s": ("Stopped: red at a corridor junction", "s", True),
    "amb_stopped_red_outside_lookahead_s": ("Stopped: red outside the look-ahead", "s", True),
    "amb_stopped_queue_s": ("Stopped: queue in front", "s", True),
    "amb_stopped_other_s": ("Stopped: other", "s", True),
    "amb_stopped_red_no_corridor_s": ("Stopped: red (corridor off)", "s", True),
    "amb_red_crossings": ("Ambulance stop lines crossed on red", "count", True),
    "fixed_window_queue_mean_veh": ("Network queue, dispatch + 600 s", "veh", True),
    "cross_street_wait_veh_s": ("Cross-street queueing, dispatch + 600 s", "veh·s", True),
    "safety_violations": ("Safety violations", "count", True),
}
METRICS.update(EXTRA_LABELS)


def configs(arms, profiles, seeds, controller="fixed_time", warmup_s=900.0, measure_s=900.0):
    return [
        RunConfig(
            profile=p,
            seed=s,
            controller=controller,
            warmup_s=warmup_s,
            measure_s=measure_s,
            mission=ARMS[a],
            label=a,
        )  # fmt: skip
        for p in profiles
        for a in arms
        for s in seeds
    ]


DEMO_MISSION = {"dispatch_s": 411.0, "incident": "closure", "incident_edge": "B0B1",
                "incident_s": 413.0}  # fmt: skip


def demo_configs(arms, seeds):
    return [
        RunConfig(
            profile="heavy",
            seed=s,
            controller="dqn",
            warmup_s=0.0,
            measure_s=3600.0,
            mission=replace(ARMS[a], **DEMO_MISSION),
            label=a,
        )  # fmt: skip
        for a in arms
        for s in seeds
    ]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arms", nargs="+", default=DEFAULT_ARMS, choices=list(ARMS))
    ap.add_argument("--profiles", nargs="+", default=["medium", "heavy"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--reference", default="v1")
    ap.add_argument("--controller", default="fixed_time", choices=CONTROLLERS,
                    help="background signal control (Phase 3 used fixed_time)")  # fmt: skip
    ap.add_argument("--demo", action="store_true", help="Phase 5 demo scenario (see above)")
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.demo:
        cfgs = demo_configs(["off", "v1", "v2"], a.seeds)
    else:
        cfgs = configs(a.arms, a.profiles, a.seeds, a.controller)
    rows = run_batch(cfgs, a.out, a.workers)
    check_compatible(rows)
    write_table(rows, a.out / "results.csv")
    s = summarise(rows, reference=a.reference, metrics=STUDY_METRICS)
    (a.out / "summary.json").write_text(json.dumps(s, indent=2) + "\n")
    (a.out / "summary.md").write_text(markdown(s, STUDY_METRICS) + "\n")
    print(markdown(s, STUDY_METRICS))


if __name__ == "__main__":
    main()
