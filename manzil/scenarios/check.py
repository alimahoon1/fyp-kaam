"""Run each demand profile headless and check for gridlock (PLAN task 1.2 "done when").

Signals run SUMO's default static program from ``netgenerate`` (a 90 s cycle per junction). This is
only a sanity check of the demand, not the Manzil fixed-time controller (task 1.6).

A run counts as **gridlock-free** when SUMO teleported no vehicle for being stuck in a jam
(``--time-to-teleport`` 300 s, SUMO's default) and every loaded vehicle arrived before the drain
limit (demand window + ``drain_s``). Other teleports and collisions are reported separately.

Usage::

    python -m manzil.scenarios.check --seeds 0 1 2 3 4 --out results/phase1/demand_check.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

from manzil.scenarios.demand import DEFAULT_NET, PROFILES, build_demand
from manzil.scenarios.grid import content_sha256, sumo_version
from manzil.sumo_env import sumo_binary

TIME_TO_TELEPORT_S = 300


@dataclass(frozen=True)
class CheckResult:
    profile: str
    seed: int
    demand_window_s: float
    vehicles_loaded: int
    vehicles_inserted: int
    vehicles_arrived: int
    still_running_or_waiting: int
    teleports_total: int
    teleports_jam: int
    collisions: int
    sim_end_s: float
    mean_trip_duration_s: float
    mean_waiting_time_s: float
    mean_time_loss_s: float
    mean_depart_delay_s: float
    gridlock_free: bool


def _parse_statistics(path: Path) -> dict[str, ET.Element]:
    root = ET.parse(path).getroot()
    return {child.tag: child for child in root}


def run_check(
    profile: str,
    seed: int,
    duration_s: float = 3600.0,
    drain_s: float = 1800.0,
    net_file: Path = DEFAULT_NET,
    work_dir: Path | None = None,
) -> CheckResult:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(work_dir) if work_dir else Path(tmp)
        files = build_demand(profile, seed, duration_s, net_file, work)
        stats_file = work / f"{profile}_seed{seed}.stats.xml"
        subprocess.run(
            [
                sumo_binary("sumo"),
                "--configuration-file", str(files.sumocfg),
                "--end", str(duration_s + drain_s),
                "--time-to-teleport", str(TIME_TO_TELEPORT_S),
                "--statistic-output", str(stats_file),
                "--duration-log.statistics", "true",
                "--no-step-log", "true",
                "--no-warnings", "true",
            ],
            capture_output=True, text=True, check=True,
        )  # fmt: skip
        s = _parse_statistics(stats_file)

    veh, tele, trips = s["vehicles"], s["teleports"], s["vehicleTripStatistics"]
    loaded, inserted = int(veh.get("loaded")), int(veh.get("inserted"))
    arrived = int(trips.get("count"))
    pending = loaded - arrived  # still driving, waiting to enter, or never inserted
    collisions = int(s["safety"].get("collisions"))
    sim_end = float(s["performance"].get("end"))
    return CheckResult(
        profile=profile,
        seed=seed,
        demand_window_s=duration_s,
        vehicles_loaded=loaded,
        vehicles_inserted=inserted,
        vehicles_arrived=arrived,
        still_running_or_waiting=pending,
        teleports_total=int(tele.get("total")),
        teleports_jam=int(tele.get("jam")),
        collisions=collisions,
        sim_end_s=sim_end,
        mean_trip_duration_s=round(float(trips.get("duration")), 2),
        mean_waiting_time_s=round(float(trips.get("waitingTime")), 2),
        mean_time_loss_s=round(float(trips.get("timeLoss")), 2),
        mean_depart_delay_s=round(float(trips.get("departDelay")), 2),
        gridlock_free=(int(tele.get("jam")) == 0 and pending == 0),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0])
    parser.add_argument("--duration", type=float, default=3600.0)
    parser.add_argument("--drain", type=float, default=1800.0)
    parser.add_argument("--profiles", nargs="*", default=sorted(PROFILES))
    parser.add_argument("--out", type=Path, default=None, help="write results JSON here")
    args = parser.parse_args(argv)

    results = [
        run_check(p, seed, args.duration, args.drain) for p in args.profiles for seed in args.seeds
    ]
    for r in results:
        print(
            f"{r.profile:7s} seed={r.seed} loaded={r.vehicles_loaded:5d} "
            f"arrived={r.vehicles_arrived:5d} pending={r.still_running_or_waiting:4d} "
            f"teleports={r.teleports_total:3d} wait={r.mean_waiting_time_s:6.1f}s "
            f"loss={r.mean_time_loss_s:6.1f}s gridlock_free={r.gridlock_free}"
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "what": "Demand sanity check on the synthetic 3x3 grid, SUMO default static signals",
            "sumo_version": sumo_version(),
            "network": DEFAULT_NET.name,
            "network_content_sha256": content_sha256(DEFAULT_NET),
            "time_to_teleport_s": TIME_TO_TELEPORT_S,
            "drain_s": args.drain,
            "gridlock_free_all": all(r.gridlock_free for r in results),
            "results": [asdict(r) for r in results],
        }
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
