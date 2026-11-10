"""Run metrics (PLAN task 1.7). Definitions are versioned: change ``METRIC_VERSION`` with them.

Measurement window: ``[warmup_s, end_s)``. Definitions (metric version 1):

- **throughput_veh**: vehicles that arrived at their destination inside the window.
- **travel_time_mean_s / waiting_time_mean_s / time_loss_mean_s**: SUMO tripinfo ``duration``,
  ``waitingTime`` and ``timeLoss``, averaged over vehicles that *departed* inside the window and
  arrived before the end. Vehicles that departed but did not finish are counted in
  ``unfinished_veh`` instead, so congestion cannot hide by leaving slow trips out.
- **travel_time_all_mean_s**: like travel time, but over *every* vehicle that departed in the
  window; unfinished vehicles count their time so far (a lower bound). Unlike the mean over
  finished trips, a policy that strands vehicles cannot look fast on it.
- **queue_mean_veh / queue_max_veh**: halting vehicles (speed < 0.1 m/s) on an approach, sampled
  every step; the mean over approaches of the time-average, and the largest single value.
- **phase_changes**: switches started (green -> yellow) inside the window, all junctions.
- **max_red_s**: the longest time any green phase of any junction waited between being served,
  inside the window (a fairness / starvation indicator).
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from manzil.sim.contracts import SignalEvent, TrafficSnapshot

METRIC_VERSION = 1
SAMPLE_INTERVAL_S = 60.0


@dataclass
class QueueCollector:
    warmup_s: float
    _sum: dict[tuple[str, str], float] = field(default_factory=lambda: defaultdict(float))
    _max: int = 0
    _n: int = 0
    samples: list[dict] = field(default_factory=list)
    _interval_queue: float = 0.0
    _interval_n: int = 0

    def record(self, snap: TrafficSnapshot) -> None:
        total = 0
        for tls, approaches in snap.approaches.items():
            for a in approaches:
                total += a.queue
                if snap.sim_time_s >= self.warmup_s:
                    self._sum[(tls, a.approach_id)] += a.queue
                    self._max = max(self._max, a.queue)
        if snap.sim_time_s >= self.warmup_s:
            self._n += 1
        self._interval_queue += total
        self._interval_n += 1
        if snap.sim_time_s % SAMPLE_INTERVAL_S == 0:
            self.samples.append(
                {
                    "time_s": snap.sim_time_s,
                    "queue_total_veh_mean": round(self._interval_queue / self._interval_n, 3),
                    "running_veh": snap.running,
                    "departed_total": snap.departed_total,
                    "arrived_total": snap.arrived_total,
                }
            )
            self._interval_queue, self._interval_n = 0.0, 0

    def summary(self) -> dict:
        if not self._n:
            return {"queue_mean_veh": None, "queue_max_veh": None}
        means = [s / self._n for s in self._sum.values()]
        return {
            "queue_mean_veh": round(sum(means) / len(means), 4),
            "queue_max_veh": self._max,
        }


def trip_metrics(tripinfo: Path, warmup_s: float, end_s: float) -> dict:
    durations, waits, losses, all_durations = [], [], [], []
    throughput = unfinished = 0
    for _, el in ET.iterparse(tripinfo, events=("end",)):
        if el.tag != "tripinfo":
            continue
        depart, arrival = float(el.get("depart")), float(el.get("arrival"))
        finished = arrival >= 0
        if finished and warmup_s <= arrival < end_s:
            throughput += 1
        if depart >= warmup_s and depart < end_s:
            all_durations.append(float(el.get("duration")) if finished else end_s - depart)
            if finished:
                durations.append(float(el.get("duration")))
                waits.append(float(el.get("waitingTime")))
                losses.append(float(el.get("timeLoss")))
            else:
                unfinished += 1
        el.clear()

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "throughput_veh": throughput,
        "completed_trips": len(durations),
        "unfinished_veh": unfinished,
        "travel_time_mean_s": mean(durations),
        "travel_time_all_mean_s": mean(all_durations),
        "waiting_time_mean_s": mean(waits),
        "time_loss_mean_s": mean(losses),
    }


def signal_metrics(events: list[SignalEvent], n_phases: dict[str, int], warmup_s, end_s) -> dict:
    changes = sum(1 for e in events if e.kind == "yellow" and warmup_s <= e.sim_time_s < end_s)
    # Max red: per junction and phase, gaps between the end of one green and the next start.
    max_red = 0.0
    by_tls: dict[str, list[SignalEvent]] = defaultdict(list)
    for e in events:
        by_tls[e.intersection_id].append(e)
    for tls, evs in by_tls.items():
        last_end = dict.fromkeys(range(n_phases[tls]), 0.0)  # every phase is red from t = 0
        current = None
        for e in evs:
            if e.sim_time_s >= end_s:
                break
            if e.kind == "green":
                if e.sim_time_s > warmup_s:
                    gap = e.sim_time_s - max(last_end[e.phase_id], warmup_s)
                    max_red = max(max_red, gap)
                current = e.phase_id
            elif e.kind == "yellow" and current is not None:
                last_end[current] = e.sim_time_s
                current = None
        for p, last in last_end.items():
            if p != current:  # still waiting at the end of the window
                max_red = max(max_red, end_s - max(last, warmup_s))
    return {"phase_changes": changes, "max_red_s": round(max_red, 2)}


def statistics_output(path: Path) -> dict:
    root = ET.parse(path).getroot()
    s = {c.tag: c for c in root}
    return {
        "vehicles_loaded": int(s["vehicles"].get("loaded")),
        "vehicles_inserted": int(s["vehicles"].get("inserted")),
        "teleports": int(s["teleports"].get("total")),
        "teleports_jam": int(s["teleports"].get("jam")),
        "collisions": int(s["safety"].get("collisions")),
        "emergency_braking": int(s["safety"].get("emergencyBraking")),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
