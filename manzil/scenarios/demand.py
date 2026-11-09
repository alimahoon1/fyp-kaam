"""Seeded demand profiles: light, medium, heavy, uneven (PLAN task 1.2).

Network-agnostic: entry and exit roads are found from the ``.net.xml`` (edges that start or end at
a dead-end fringe node), never from hard-coded IDs. Each entry road gets a Poisson arrival
stream at the profile's rate; each trip goes to a uniformly chosen exit (no U-turn back to the
same fringe node). ``duarouter`` turns the trips into explicit routes so every run with the same
seed loads exactly the same vehicles.

Usage::

    python -m manzil.scenarios.demand --profile light --seed 0
    python -m manzil.scenarios.demand --all --seed 0
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import sumolib

from manzil.sumo_env import sumo_binary

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NET = REPO_ROOT / "scenarios" / "grid3x3" / "grid3x3.net.xml"


@dataclass(frozen=True)
class DemandProfile:
    """Arrival rates in vehicles per hour per entry road.

    ``major_rate`` applies to entry roads whose heading is mainly north-south, ``minor_rate`` to
    the rest. Balanced profiles use the same rate for both; the uneven profile makes one axis
    much busier than the other (the D2 starvation case, where the quiet approach must still get
    served).

    Rates were calibrated on the 3x3 grid with SUMO's default 90 s static signals (see
    ``scenarios/grid3x3/README.md``): saturation starts at about 650-750 veh/h per entry road.
    """

    name: str
    major_rate_vph: float
    minor_rate_vph: float
    description: str


PROFILES: dict[str, DemandProfile] = {
    p.name: p
    for p in (
        DemandProfile("light", 200, 200, "Free-flowing traffic; queues clear every cycle."),
        DemandProfile("medium", 400, 400, "Busy but stable traffic."),
        DemandProfile("heavy", 600, 600, "Near saturation for default signals; long queues."),
        DemandProfile("uneven", 800, 100, "Heavy north-south, light east-west (starvation case)."),
    )
}


@dataclass(frozen=True)
class FringeEdge:
    edge_id: str
    node_id: str  # the dead-end fringe node at the outer end of the road
    north_south: bool  # heading mainly along the y axis


def _is_dead_end(node) -> bool:
    return node.getType() == "dead_end"


def _north_south(edge) -> bool:
    (x0, y0), (x1, y1) = edge.getFromNode().getCoord(), edge.getToNode().getCoord()
    return abs(y1 - y0) > abs(x1 - x0)


def fringe_edges(net) -> tuple[list[FringeEdge], list[FringeEdge]]:
    """Return (entry, exit) roads: edges leaving / entering a dead-end node, sorted by ID."""
    entries, exits = [], []
    for edge in net.getEdges():
        if not edge.allows("passenger"):
            continue
        if _is_dead_end(edge.getFromNode()):
            entries.append(FringeEdge(edge.getID(), edge.getFromNode().getID(), _north_south(edge)))
        if _is_dead_end(edge.getToNode()):
            exits.append(FringeEdge(edge.getID(), edge.getToNode().getID(), _north_south(edge)))
    if not entries or not exits:
        raise ValueError("network has no dead-end fringe roads to insert or remove traffic")
    key = lambda f: f.edge_id  # noqa: E731
    return sorted(entries, key=key), sorted(exits, key=key)


@dataclass(frozen=True)
class Trip:
    trip_id: str
    depart: float
    from_edge: str
    to_edge: str


def generate_trips(net, profile: DemandProfile, seed: int, duration_s: float) -> list[Trip]:
    """Poisson arrivals per entry road over [0, duration_s), seeded and deterministic."""
    rng = np.random.default_rng(seed)
    entries, exits = fringe_edges(net)
    raw: list[tuple[float, str, str]] = []
    for entry in entries:  # sorted order keeps the random stream stable
        rate = profile.major_rate_vph if entry.north_south else profile.minor_rate_vph
        if rate <= 0:
            continue
        mean_gap = 3600.0 / rate
        targets = [x for x in exits if x.node_id != entry.node_id]
        t = rng.exponential(mean_gap)
        while t < duration_s:
            dest = targets[rng.integers(len(targets))]
            raw.append((round(t, 2), entry.edge_id, dest.edge_id))
            t += rng.exponential(mean_gap)
    raw.sort()
    return [Trip(f"{profile.name}_{i}", d, f, to) for i, (d, f, to) in enumerate(raw)]


VTYPE_ID = "car"


def write_trips(trips: list[Trip], path: Path) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<routes>",
        f'    <vType id="{VTYPE_ID}" vClass="passenger"/>',
    ]
    for t in trips:
        lines.append(
            f'    <trip id={quoteattr(t.trip_id)} type="{VTYPE_ID}" depart="{t.depart:.2f}" '
            f"from={quoteattr(t.from_edge)} to={quoteattr(t.to_edge)} "
            'departLane="best" departSpeed="max"/>'
        )
    lines.append("</routes>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def route_trips(net_file: Path, trips_file: Path, routes_file: Path) -> None:
    """Shortest-path routes with duarouter; fails loudly if any trip has no route."""
    subprocess.run(
        [
            sumo_binary("duarouter"),
            "--net-file", str(net_file),
            "--route-files", str(trips_file),
            "--output-file", str(routes_file),
            "--no-step-log", "true",
            "--no-warnings", "true",
            "--write-trips.junctions", "false",
        ],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    alt = routes_file.with_suffix("").with_suffix(".rou.alt.xml")
    alt.unlink(missing_ok=True)  # duarouter's alternatives file is not used


def write_sumocfg(net_file: Path, routes_file: Path, cfg_file: Path, seed: int, end_s: float):
    def rel(p: Path) -> str:
        return Path(os.path.relpath(p, cfg_file.parent)).as_posix()

    cfg_file.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<configuration>\n"
        "    <input>\n"
        f'        <net-file value="{rel(net_file)}"/>\n'
        f'        <route-files value="{rel(routes_file)}"/>\n'
        "    </input>\n"
        "    <time>\n"
        '        <begin value="0"/>\n'
        f'        <end value="{end_s:g}"/>\n'
        "    </time>\n"
        "    <random_number>\n"
        f'        <seed value="{seed}"/>\n'
        "    </random_number>\n"
        "</configuration>\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class DemandFiles:
    profile: str
    seed: int
    duration_s: float
    vehicles: int
    routes: Path
    sumocfg: Path
    manifest: Path


def build_demand(
    profile_name: str,
    seed: int,
    duration_s: float = 3600.0,
    net_file: Path = DEFAULT_NET,
    out_dir: Path | None = None,
) -> DemandFiles:
    """Write trips, routes, a runnable ``.sumocfg`` and a small JSON manifest for one profile."""
    profile = PROFILES[profile_name]
    net_file = Path(net_file)
    out_dir = Path(out_dir) if out_dir else net_file.parent / "demand"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{profile.name}_seed{seed}"

    net = sumolib.net.readNet(str(net_file))
    trips = generate_trips(net, profile, seed, duration_s)
    trips_file = out_dir / f"{stem}.trips.xml"
    routes_file = out_dir / f"{stem}.rou.xml"
    write_trips(trips, trips_file)
    route_trips(net_file, trips_file, routes_file)
    cfg_file = out_dir / f"{stem}.sumocfg"
    write_sumocfg(net_file, routes_file, cfg_file, seed, end_s=duration_s)

    manifest = out_dir / f"{stem}.json"
    manifest.write_text(
        json.dumps(
            {
                "profile": asdict(profile),
                "seed": seed,
                "duration_s": duration_s,
                "vehicles": len(trips),
                "network": net_file.name,
                "generator": "manzil.scenarios.demand (Poisson per entry road, numpy PCG64)",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return DemandFiles(profile.name, seed, duration_s, len(trips), routes_file, cfg_file, manifest)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", choices=sorted(PROFILES))
    group.add_argument("--all", action="store_true", help="build every profile")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--duration", type=float, default=3600.0, help="demand window in s")
    parser.add_argument("--net", type=Path, default=DEFAULT_NET)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    names = sorted(PROFILES) if args.all else [args.profile]
    for name in names:
        files = build_demand(name, args.seed, args.duration, args.net, args.out_dir)
        print(f"{name}: {files.vehicles} vehicles -> {files.sumocfg}")


if __name__ == "__main__":
    main()
