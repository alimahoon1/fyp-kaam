"""Build a SUMO network of a Lahore area from OpenStreetMap (workstream W1).

Pipeline (every step is recorded in ``scenarios/lahore/<area>/network.json``):

1. **Extract**: download the area from the OSM API (``/api/0.6/map``) in small tiles and merge
   them into one raw ``.osm.xml.gz`` (committed, with its SHA-256 and the download date).
2. **Filter and clip**: keep only drivable roads of type ``tertiary`` and above (plus their links)
   and cut every way at the bounding box, so the network ends at the box edge. Signal nodes
   (``highway=traffic_signals``) keep their tags.
3. **netconvert**: with the urban road-type map ``scenarios/lahore/lahore.typ.xml`` (speeds of
   60/50/40 km/h instead of SUMO's rural OSM defaults), junction joining, ramp and roundabout
   guessing, and traffic-light guessing. Lahore's OSM data has very few ``traffic_signals``
   tags, so most signals in the network are *guessed* by netconvert; ``network.json`` reports how
   many came from OSM tags and how many were guessed.

Map data (c) OpenStreetMap contributors, available under the Open Database Licence (ODbL).

Usage::

    python -m manzil.scenarios.osm --fetch   # download raw OSM for the area (needs internet)
    python -m manzil.scenarios.osm           # rebuild scenarios/lahore/ from the committed raw file
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import re
import subprocess
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

from manzil.scenarios.grid import content_sha256, sumo_version
from manzil.sumo_env import sumo_binary

REPO_ROOT = Path(__file__).resolve().parents[2]
LAHORE_DIR = REPO_ROOT / "scenarios" / "lahore"
TYPEMAP = LAHORE_DIR / "lahore.typ.xml"
OSM_API = "https://api.openstreetmap.org/api/0.6/map"
USER_AGENT = "manzil-fyp-research/0.1"

# Road classes kept in the network. Residential and service streets are dropped: the study is
# about signalised arterial junctions, and the side streets would add thousands of unsignalised
# nodes without changing the corridor.
MAJOR_HIGHWAYS = frozenset(
    {
        "trunk", "trunk_link", "primary", "primary_link",
        "secondary", "secondary_link", "tertiary", "tertiary_link",
    }
)  # fmt: skip


@dataclass(frozen=True)
class BBox:
    south: float
    west: float
    north: float
    east: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lon <= self.east

    def as_netconvert(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"


@dataclass(frozen=True)
class Hospital:
    name: str
    lat: float  # emergency entrance (or main gate) position
    lon: float
    osm_ref: str  # OSM element the position came from


@dataclass(frozen=True)
class Area:
    name: str
    title: str
    bbox: BBox
    hospital: Hospital
    tls_guess_threshold: float = 40.0  # min. sum of incoming lane speeds (m/s) for a guessed TLS
    junction_join_dist_m: float = 25.0  # nodes closer than this become one junction
    # Join neighbouring traffic lights into one TLS (netconvert --tls.join). Off by default:
    # the DQN observation layout allows at most 4 approaches and 4 green phases per traffic
    # light, and the joined Ichhra lights have up to 10 approaches. The network reader supports
    # joined lights either way.
    join_tls: bool = False


# Candidate areas measured on 15 Nov 2026 (see results/fyp2/lahore_network/README.md).
AREAS: dict[str, Area] = {
    "ghazi_lgh": Area(
        "ghazi_lgh",
        "Ferozpur Road at Ghazi Chowk, Lahore General Hospital",
        BBox(31.445, 74.335, 31.465, 74.360),
        Hospital("Lahore General Hospital (Emergency Department)", 31.45679, 74.35054,
                 "nominatim: Emergency Department General Hospital"),
    ),
    "model_town": Area(
        "model_town",
        "Ferozpur Road at Model Town / Kot Lakhpat, Ittefaq and Children's Hospitals",
        BBox(31.468, 74.328, 31.490, 74.352),
        Hospital("Children's Hospital Lahore", 31.47988, 74.34390,
                 "nominatim: Children Hospital Lahore"),
    ),
    "ichhra": Area(
        "ichhra",
        "Ferozpur Road at Ichhra, WAPDA Hospital",
        BBox(31.514, 74.313, 31.531, 74.333),
        Hospital("WAPDA Hospital", 31.52382, 74.32281, "osm node: Wapda Hospital"),
    ),
}  # fmt: skip
SELECTED_AREA = "ichhra"  # chosen by Ibrahim on 15 Nov 2026 (W1)


# --------------------------------------------------------------------------- projection


def utm_zone(lon: float) -> int:
    return int((lon + 180.0) // 6.0) + 1


def utm_forward(lat: float, lon: float, zone: int) -> tuple[float, float]:
    """WGS84 lat/lon -> UTM easting/northing (northern hemisphere), Krüger series.

    Accurate to well under a millimetre within a zone; used instead of pyproj (not a
    dependency) to place the hospital and to draw maps in network coordinates.
    """
    a, f = 6378137.0, 1 / 298.257223563
    n = f / (2 - f)
    big_a = a / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    alpha = (n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16, 13 * n**2 / 48 - 3 * n**3 / 5, 61 * n**3 / 240)
    lam0 = math.radians(zone * 6 - 183)
    phi, lam = math.radians(lat), math.radians(lon) - lam0
    e = 2 * math.sqrt(n) / (1 + n)
    t = math.sinh(math.atanh(math.sin(phi)) - e * math.atanh(e * math.sin(phi)))
    xi = math.atan2(t, math.cos(lam))
    eta = math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    terms = list(enumerate(alpha, 1))
    x = eta + sum(al * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, al in terms)
    y = xi + sum(al * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, al in terms)
    return 500000.0 + 0.9996 * big_a * x, 0.9996 * big_a * y


def lonlat_to_net_xy(net, lat: float, lon: float) -> tuple[float, float]:
    """Project lat/lon into the coordinates of a netconvert-built ``sumolib`` net."""
    proj = getattr(net, "_location", {}).get("projParameter", "")
    zone = None
    for part in proj.split():
        if part.startswith("+zone="):
            zone = int(part.split("=")[1])
    if zone is None:
        zone = utm_zone(lon)
    ox, oy = net.getLocationOffset()
    east, north = utm_forward(lat, lon, zone)
    return east + ox, north + oy


# --------------------------------------------------------------------------- extraction


def fetch_tiles(bbox: BBox, out_dir: Path, step: float = 0.01) -> list[Path]:
    """Download ``bbox`` from the OSM API in ``step``-degree tiles (polite: 1 request/s)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = []
    n_lat = math.ceil(round((bbox.north - bbox.south) / step, 6))
    n_lon = math.ceil(round((bbox.east - bbox.west) / step, 6))
    for i in range(n_lat):
        for j in range(n_lon):
            s, w = bbox.south + i * step, bbox.west + j * step
            n, e = min(s + step, bbox.north), min(w + step, bbox.east)
            tile = out_dir / f"tile_{s:.4f}_{w:.4f}.osm"
            if not tile.exists():
                url = f"{OSM_API}?bbox={w:.4f},{s:.4f},{e:.4f},{n:.4f}"
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    tile.write_bytes(resp.read())
                time.sleep(1.0)
            tiles.append(tile)
    return tiles


def merge_osm(files: list[Path]) -> ET.Element:
    """Union of several OSM XML files (tiles overlap on shared ways), sorted by type and id."""
    groups: dict[str, dict[int, ET.Element]] = {"node": {}, "way": {}, "relation": {}}
    for f in files:
        opener = gzip.open if str(f).endswith(".gz") else open
        with opener(f, "rb") as fh:
            for elem in ET.parse(fh).getroot():
                if elem.tag in groups:
                    groups[elem.tag][int(elem.get("id"))] = elem
    root = ET.Element("osm", version="0.6", generator="manzil.scenarios.osm")
    for tag in ("node", "way", "relation"):
        for key in sorted(groups[tag]):
            root.append(groups[tag][key])
    return root


def write_osm(root: ET.Element, path: Path) -> None:
    """Write OSM XML; ``.gz`` paths are gzipped with a fixed mtime so the bytes are stable."""
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if str(path).endswith(".gz"):
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


def read_osm(path: Path) -> ET.Element:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as fh:
        return ET.parse(fh).getroot()


def _tags(elem: ET.Element) -> dict[str, str]:
    return {t.get("k"): t.get("v") for t in elem.findall("tag")}


def filter_and_clip(root: ET.Element, bbox: BBox, keep=MAJOR_HIGHWAYS) -> ET.Element:
    """Keep drivable major roads inside ``bbox``; split ways where they leave the box.

    A way that leaves and re-enters the box becomes several ways; the first keeps the OSM id,
    the others get ids above 10^15 so they cannot collide with real OSM ids. Turn-restriction
    relations are kept only if all their members survive.
    """
    nodes = {n.get("id"): n for n in root.findall("node")}

    def inside(ref: str) -> bool:
        n = nodes.get(ref)
        return n is not None and bbox.contains(float(n.get("lat")), float(n.get("lon")))

    out_ways: list[ET.Element] = []
    used: set[str] = set()
    kept_way_ids: set[str] = set()
    extra_id = 10**15
    for way in root.findall("way"):
        tags = _tags(way)
        if tags.get("highway") not in keep or tags.get("area") == "yes":
            continue
        refs = [nd.get("ref") for nd in way.findall("nd")]
        runs, run = [], []
        for ref in refs:
            if inside(ref):
                run.append(ref)
            else:
                if len(run) >= 2:
                    runs.append(run)
                run = []
        if len(run) >= 2:
            runs.append(run)
        for k, run in enumerate(runs):
            if k == 0:
                way_id = way.get("id")
                kept_way_ids.add(way_id)
            else:
                extra_id += 1
                way_id = str(extra_id)
            new = ET.Element("way", id=way_id, version=way.get("version", "1"))
            for ref in run:
                ET.SubElement(new, "nd", ref=ref)
            for k_, v in tags.items():
                ET.SubElement(new, "tag", k=k_, v=v)
            out_ways.append(new)
            used.update(run)

    out = ET.Element("osm", version="0.6", generator="manzil.scenarios.osm (filtered)")
    for ref in sorted(used, key=int):
        out.append(nodes[ref])
    for way in out_ways:
        out.append(way)
    for rel in root.findall("relation"):
        if _tags(rel).get("type") != "restriction":
            continue
        members = rel.findall("member")
        ok = all(
            (m.get("type") == "way" and m.get("ref") in kept_way_ids)
            or (m.get("type") == "node" and m.get("ref") in used)
            for m in members
        )
        if ok and members:
            out.append(rel)
    return out


def signal_nodes(root: ET.Element) -> list[str]:
    return [
        n.get("id") for n in root.findall("node") if _tags(n).get("highway") == "traffic_signals"
    ]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- netconvert


def netconvert_command(
    area: Area,
    osm_file: Path,
    net_file: Path,
    typemap: Path = TYPEMAP,
    unset_tls: list[str] | tuple[str, ...] = (),
    remove_edges: list[str] | tuple[str, ...] = (),
) -> list[str]:
    cmd = [
        sumo_binary("netconvert"),
        "--osm-files", str(osm_file),
        "--type-files", str(typemap),
        "--keep-edges.in-geo-boundary", area.bbox.as_netconvert(),
        "--remove-edges.isolated", "true",
        "--keep-edges.components", "1",
        "--geometry.remove", "true",
        "--ramps.guess", "true",
        "--roundabouts.guess", "true",
        "--junctions.join", "true",
        "--junctions.join-dist", str(area.junction_join_dist_m),
        "--tls.guess-signals", "true",
        "--tls.guess", "true",
        "--tls.guess.threshold", str(area.tls_guess_threshold),
        "--tls.guess.joining", str(area.join_tls).lower(),
        "--tls.join", str(area.join_tls).lower(),
        "--tls.default-type", "static",
        "--lefthand", "true",  # Pakistan drives on the left
        "--no-turnarounds", "true",
        "--osm.layer-elevation", "5",
    ]  # fmt: skip
    if unset_tls:
        cmd += ["--tls.unset", ",".join(unset_tls)]
    if remove_edges:
        cmd += ["--remove-edges.explicit", ",".join(remove_edges)]
    return cmd + ["--output-file", str(net_file)]


def tls_cleanup_reasons(net_file: Path) -> dict[str, str]:
    """Traffic lights the cleanup removes, with the reason.

    - ``merge``: at most two approaches and only straight movements. These are points where
      two roads merge (e.g. a slip road joining a carriageway); netconvert guesses a signal
      there because the speed sum is high, but they are not signalised junctions.
    - ``one_green``: the program has fewer than two green phases, so there is nothing to
      control (Manzil controllers choose between at least two green phases).
    Only single-junction traffic lights are judged; a joined one is kept as a whole.
    """
    import sumolib

    net = sumolib.net.readNet(str(net_file), withPrograms=True)
    reasons = {}
    for tls in net.getTrafficLights():
        conns = tls.getConnections()
        nodes = {from_lane.getEdge().getToNode().getID() for from_lane, _, _ in conns}
        if len(nodes) != 1:
            continue
        approaches = {from_lane.getEdge().getID() for from_lane, _, _ in conns}
        directions = set()
        for from_lane, to_lane, _ in conns:
            for c in from_lane.getOutgoing():
                if c.getToLane() is to_lane:
                    directions.add(c.getDirection())
        program = next(iter(tls.getPrograms().values()))
        greens = [
            p.state
            for p in program.getPhases()
            if "y" not in p.state.lower() and any(ch in "Gg" for ch in p.state)
        ]
        if len(approaches) <= 2 and directions <= {"s"}:
            reasons[next(iter(nodes))] = "merge"
        elif len(greens) < 2:
            reasons[next(iter(nodes))] = "one_green"
    return reasons


def _strong_core(edges: dict[str, list[str]]) -> set[str]:
    """Largest strongly connected component of a directed edge graph (iterative Kosaraju)."""
    order, seen = [], set()
    for start in sorted(edges):
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(edges[start]))]
        while stack:
            node, it = stack[-1]
            nxt = next((n for n in it if n not in seen), None)
            if nxt is None:
                order.append(node)
                stack.pop()
            else:
                seen.add(nxt)
                stack.append((nxt, iter(edges[nxt])))
    reverse: dict[str, list[str]] = {e: [] for e in edges}
    for e, outs in edges.items():
        for o in outs:
            reverse[o].append(e)
    best, assigned = set(), set()
    for root in reversed(order):
        if root in assigned:
            continue
        comp, todo = {root}, [root]
        assigned.add(root)
        while todo:
            for p in reverse[todo.pop()]:
                if p not in assigned:
                    assigned.add(p)
                    comp.add(p)
                    todo.append(p)
        if len(comp) > len(best):
            best = comp
    return best


def _closure(start: set[str], step: dict[str, list[str]]) -> set[str]:
    out, todo = set(start), list(start)
    while todo:
        for n in step[todo.pop()]:
            if n not in out:
                out.add(n)
                todo.append(n)
    return out


def connectivity_removals(net_file: Path) -> set[str]:
    """Edges that cannot be part of a trip through the network's main core.

    The core is the largest strongly connected set of edges (following lane connections for
    passenger cars). Feeders can reach the core (e.g. entry roads), drains can be reached from
    it (e.g. exit roads). An edge is kept if it lies on a path from a feeder to a drain. Then
    every kept entry road is a feeder and every kept exit road a drain, so every entry reaches
    every exit (through the core), and every entry reaches the hospital if its street is kept.
    Clipping at the bounding box leaves a few one-way fragments that fail this test.
    """
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    graph = {
        e.getID(): sorted(o.getID() for o in e.getOutgoing() if o.allows("passenger"))
        for e in net.getEdges()
        if e.allows("passenger")
    }
    core = _strong_core(graph)
    reverse: dict[str, list[str]] = {e: [] for e in graph}
    for e, outs in graph.items():
        for o in outs:
            reverse[o].append(e)
    feeders = _closure(core, reverse)  # can reach the core
    drains = _closure(core, graph)  # reachable from the core
    # Keep every edge on some path feeder -> ... -> drain (this includes through roads that
    # bypass the core, such as one carriageway of a dual road between two kept junctions).
    keep = _closure(feeders, graph) & _closure(drains, reverse)
    return {e.getID() for e in net.getEdges()} - keep


@dataclass
class BuildResult:
    net_file: Path
    command: list[str]  # final netconvert command, paths relative to the scenario folder
    removed_tls: dict[str, str]  # junction id -> cleanup reason
    removed_edges: list[str]  # edges removed by the connectivity cleanup
    osm_signal_nodes: int  # highway=traffic_signals nodes inside the box


def build_network(area: Area, raw_osm: Path, out_dir: Path, net_name: str) -> BuildResult:
    """Filter + clip ``raw_osm``, run netconvert, then clean up signals and connectivity.

    The cleanup repeats netconvert with ``--tls.unset`` and ``--remove-edges.explicit`` until
    no rejected traffic light (:func:`tls_cleanup_reasons`) or disconnected edge
    (:func:`connectivity_removals`) is left (at most 6 passes), so the result is reproducible
    from the raw file alone.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    root = filter_and_clip(read_osm(raw_osm), area.bbox)
    filtered = out_dir / f"{net_name}.filtered.osm.xml"
    write_osm(root, filtered)
    net_file = out_dir / f"{net_name}.net.xml"
    removed: dict[str, str] = {}
    removed_edges: set[str] = set()
    try:
        for _ in range(6):
            while True:
                unset = sorted(k for k, v in removed.items() if "junction removed" not in v)
                cmd = netconvert_command(area, filtered, net_file, unset_tls=unset,
                                         remove_edges=sorted(removed_edges))  # fmt: skip
                proc = subprocess.run(cmd, capture_output=True, text=True)
                gone = re.search(r"junction '([^']+)' to set as not-controlled is not known",
                                 proc.stderr)  # fmt: skip
                if proc.returncode == 0:
                    break
                if not gone:
                    raise RuntimeError(f"netconvert failed: {proc.stderr[-2000:]}")
                # The junction vanished with removed edges; nothing left to unset there.
                removed[gone.group(1)] += "; junction removed with its edges"
            new_tls = {k: v for k, v in tls_cleanup_reasons(net_file).items() if k not in removed}
            new_edges = connectivity_removals(net_file) - removed_edges
            if not new_tls and not new_edges:
                break
            removed.update(new_tls)
            removed_edges |= new_edges
        else:
            raise RuntimeError("network cleanup did not converge")
    finally:
        filtered.unlink(missing_ok=True)

    def rel(arg: str) -> str:
        if arg == cmd[0]:
            return "netconvert"
        p = Path(arg)
        return p.name if p.is_absolute() else arg

    return BuildResult(net_file, [rel(a) for a in cmd], dict(sorted(removed.items())),
                       sorted(removed_edges), len(signal_nodes(root)))  # fmt: skip


# --------------------------------------------------------------------------- hospital


def bridge_way_ids(root: ET.Element) -> set[str]:
    return {w.get("id") for w in root.findall("way") if _tags(w).get("bridge") not in (None, "no")}


def _way_of(edge_id: str) -> str:
    return edge_id.lstrip("-").split("#")[0]


def hospital_edge(net, area: Area, bridges: set[str], radius_m: float = 200.0) -> str:
    """The drivable street edge nearest to the hospital point, excluding bridges/flyovers.

    The ambulance ends its trip at the end of this edge. Flyovers are excluded because the
    hospital gate is at street level.
    """
    x, y = lonlat_to_net_xy(net, area.hospital.lat, area.hospital.lon)
    near = sorted(net.getNeighboringEdges(x, y, radius_m), key=lambda t: (t[1], t[0].getID()))
    for edge, _ in near:
        if _way_of(edge.getID()) not in bridges and edge.allows("emergency"):
            return edge.getID()
    raise ValueError(f"no street edge within {radius_m} m of {area.hospital.name}")


# --------------------------------------------------------------------------- demand

# Seeded demand for the Lahore network. Same file layout and manifest as
# manzil.scenarios.demand (routes, sumocfg, json), so experiment code can use either. Rates are
# per *lane* of the entry road (a 3-lane primary gets three times the rate of a 1-lane tertiary);
# "major" entries are those heading mainly north-south (the Ferozpur Road axis). Calibrated on
# dev seeds 100-101 with netconvert's default signals (results/fyp2/lahore_network/
# demand_calibration.csv): queues start to grow at about 125 veh/h per lane. Synthetic demand,
# not calibrated to real Lahore counts (W6 compares with the video counts).
LAHORE_PROFILES: dict[str, tuple[float, float, str]] = {
    "light": (50, 50, "Free-flowing traffic."),
    "medium": (100, 100, "Busy but stable traffic."),
    "heavy": (125, 125, "At the onset of saturation; queues grow."),
    "uneven": (150, 30, "Busy on the Ferozpur Road axis, light on cross streets."),
}  # fmt: skip


def lahore_trips(net, profile: str, seed: int, duration_s: float):
    """Poisson arrivals per entry road (rate x lanes); exits weighted by their lane count."""
    import numpy as np

    from manzil.scenarios.demand import Trip, fringe_edges

    major, minor, _ = LAHORE_PROFILES[profile]
    rng = np.random.default_rng(seed)
    entries, exits = fringe_edges(net)
    raw = []
    for entry in entries:
        lanes = net.getEdge(entry.edge_id).getLaneNumber()
        rate = (major if entry.north_south else minor) * lanes
        targets = [x for x in exits if x.node_id != entry.node_id]
        weights = np.array([net.getEdge(x.edge_id).getLaneNumber() for x in targets], float)
        weights /= weights.sum()
        mean_gap = 3600.0 / rate
        t = rng.exponential(mean_gap)
        while t < duration_s:
            dest = targets[rng.choice(len(targets), p=weights)]
            raw.append((round(t, 2), entry.edge_id, dest.edge_id))
            t += rng.exponential(mean_gap)
    raw.sort()
    return [Trip(f"{profile}_{i}", d, f, to) for i, (d, f, to) in enumerate(raw)]


def build_lahore_demand(
    profile_name: str,
    seed: int,
    duration_s: float = 3600.0,
    net_file: Path | None = None,
    out_dir: Path | None = None,
):
    """Drop-in for ``manzil.scenarios.demand.build_demand`` on the Lahore network."""
    import sumolib

    from manzil.scenarios.demand import DemandFiles, route_trips, write_sumocfg, write_trips

    if profile_name not in LAHORE_PROFILES:
        raise KeyError(f"unknown Lahore profile {profile_name!r}")
    net_file = Path(net_file) if net_file else LAHORE_DIR / "lahore.net.xml"
    out_dir = Path(out_dir) if out_dir else net_file.parent / "demand"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{profile_name}_seed{seed}"
    net = sumolib.net.readNet(str(net_file))
    trips = lahore_trips(net, profile_name, seed, duration_s)
    trips_file, routes_file = out_dir / f"{stem}.trips.xml", out_dir / f"{stem}.rou.xml"
    write_trips(trips, trips_file)
    route_trips(net_file, trips_file, routes_file)
    cfg_file = out_dir / f"{stem}.sumocfg"
    write_sumocfg(net_file, routes_file, cfg_file, seed, end_s=duration_s)
    major, minor, desc = LAHORE_PROFILES[profile_name]
    manifest = out_dir / f"{stem}.json"
    manifest.write_text(
        json.dumps(
            {
                "profile": {"name": profile_name, "major_rate_vph_per_lane": major,
                            "minor_rate_vph_per_lane": minor, "description": desc},
                "seed": seed,
                "duration_s": duration_s,
                "vehicles": len(trips),
                "network": net_file.name,
                "generator": "manzil.scenarios.osm.build_lahore_demand "
                "(Poisson per entry lane, numpy PCG64)",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )  # fmt: skip
    return DemandFiles(profile_name, seed, duration_s, len(trips), routes_file, cfg_file, manifest)


# --------------------------------------------------------------------------- signal timing

SIGNALS_VERSION = 1


def signal_timing(net_file: Path) -> dict:
    """``signals.json`` for the Lahore network (same schema as ``scenarios/grid3x3``).

    Safety timing is the same as on the grid. The fixed-time plan uses the green durations of
    netconvert's own program, raised to the minimum green; it is *not* tuned for Lahore (tuning
    belongs to the evaluation protocol). The adaptive parameters and the DQN checkpoint are the
    grid ones, used here without retuning or retraining (a transfer test).
    """
    from manzil.sim.network import NetworkModel

    network = NetworkModel.from_file(net_file)
    safety = {"min_green_s": 10, "yellow_s": 3, "all_red_s": 2, "max_red_s": 90,
              "corridor_min_green_s": 5}  # fmt: skip
    junctions = {
        tls: {
            "green_s": [max(safety["min_green_s"], round(g.default_duration_s))
                        for g in x.green_phases],
            "offset_s": 0,
        }
        for tls, x in sorted(network.intersections.items())
    }  # fmt: skip
    return {
        "version": SIGNALS_VERSION,
        "notes": "Lahore (Ichhra) OSM network, generated by manzil.scenarios.osm. Signals are "
        "guessed by netconvert (OSM has no signal tags here). Fixed-time greens come from "
        "netconvert's program (raised to min green), not tuned. Adaptive parameters and the DQN "
        "checkpoint are the grid ones, not retuned or retrained (transfer).",
        "safety": safety,
        "fixed_time_plans": {
            "netconvert": {
                "description": "Green durations of netconvert's generated program, at least "
                "min_green_s; no offsets. Not tuned for Lahore.",
                "junctions": junctions,
            }
        },
        "profile_plans": {p: "netconvert" for p in LAHORE_PROFILES},
        "adaptive": {
            "description": "Grid parameters (scenarios/grid3x3/signals.json), not retuned.",
            "alpha": 0.5, "beta": 0.02, "max_green_s": 40, "max_red_s": 90,
            "switch_margin": 3, "min_hold_s": 15,
        },
        "dqn": {
            "description": "Grid-trained checkpoint, not retrained on Lahore (transfer test).",
            "checkpoint": "models/dqn/grid3x3/best.pt",
            "decision_s": 5,
        },
    }  # fmt: skip


# --------------------------------------------------------------------------- validation

RESULTS_DIR = REPO_ROOT / "results" / "fyp2" / "lahore_network"
RUN_KEYS = (
    "throughput_veh", "completed_trips", "unfinished_veh", "vehicles_loaded",
    "vehicles_inserted", "travel_time_mean_s", "waiting_time_mean_s", "time_loss_mean_s",
    "queue_mean_veh", "queue_max_veh", "phase_changes", "max_red_s", "teleports",
    "teleports_jam", "collisions", "emergency_braking", "safety_violations",
)  # fmt: skip
MISSION_KEYS = (
    "mission_status", "amb_travel_time_s", "amb_free_flow_time_s", "amb_excess_delay_s",
    "amb_stops", "amb_waiting_s", "amb_signal_crossings", "amb_red_crossings",
)  # fmt: skip


def _hospital_edge_for(net_file: Path) -> str:
    import sumolib

    record = json.loads((net_file.parent / "network.json").read_text(encoding="utf-8"))
    area = AREAS[record["area"]["name"]]
    raw = net_file.parent / record["extract"]["raw_file"]
    return hospital_edge(sumolib.net.readNet(str(net_file)), area, bridge_way_ids(read_osm(raw)))


def network_checks(net_file: Path) -> dict:
    """Reader, conflict rule on every green phase, headless SUMO load."""
    from manzil.sim.network import NetworkModel

    network = NetworkModel.from_file(net_file)
    conflicts = {
        tls: {g.index: x.conflicts_in(g.state) for g in x.green_phases if x.conflicts_in(g.state)}
        for tls, x in network.intersections.items()
    }
    proc = subprocess.run(
        [sumo_binary("sumo"), "--net-file", str(net_file), "--end", "10", "--no-step-log", "true"],
        capture_output=True, text=True,
    )  # fmt: skip
    return {
        "network_id": network.network_id,
        "traffic_lights": len(network.intersections),
        "joined_traffic_lights": sum(x.joined for x in network.intersections.values()),
        "green_phases_per_tls": {t: len(x.green_phases) for t, x in network.intersections.items()},
        "approaches_per_tls": {t: len(x.approaches) for t, x in network.intersections.items()},
        "phases_with_conflicts": {t: c for t, c in conflicts.items() if c},
        "sumo_headless_load_ok": proc.returncode == 0,
    }


def hospital_routes(net_file: Path) -> list[dict]:
    """Shortest path (sumolib, passenger connections) from every entry road to the hospital."""
    import sumolib

    from manzil.scenarios.demand import fringe_edges

    net = sumolib.net.readNet(str(net_file))
    target = net.getEdge(_hospital_edge_for(net_file))
    rows = []
    for entry in fringe_edges(net)[0]:
        path, _ = net.getShortestPath(net.getEdge(entry.edge_id), target, vClass="emergency")
        rows.append({
            "entry_edge": entry.edge_id,
            "hospital_edge": target.getID(),
            "reachable": path is not None,
            "edges": len(path) if path else 0,
            "length_m": round(sum(e.getLength() for e in path), 1) if path else None,
            "free_flow_s": round(sum(e.getLength() / e.getSpeed() for e in path), 1)
            if path else None,
            "signals_on_route": sum(e.getToNode().getType() == "traffic_light" for e in path)
            if path else 0,
        })  # fmt: skip
    return rows


def demand_calibration(net_file: Path, rates=(50, 75, 100, 125, 150), seeds=(100, 101)):
    """Default-signal SUMO runs for a sweep of per-lane rates (dev seeds), like the grid."""
    import re as _re

    rows = []
    for rate in rates:
        for seed in seeds:
            LAHORE_PROFILES["_sweep"] = (rate, rate, "calibration sweep")
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    d = build_lahore_demand("_sweep", seed, 4500.0, net_file, Path(tmp))
                    proc = subprocess.run(
                        [sumo_binary("sumo"), "-c", str(d.sumocfg), "--end", "6300",
                         "--time-to-teleport", "300", "--no-step-log", "true",
                         "--duration-log.statistics", "true"],
                        capture_output=True, text=True, check=True,
                    )  # fmt: skip
            finally:
                del LAHORE_PROFILES["_sweep"]

            def num(pattern, text=proc.stdout):
                m = _re.search(pattern, text)
                return float(m.group(1)) if m else None

            teleports = [ln for ln in proc.stderr.splitlines() if "Teleporting" in ln]
            rows.append({
                "rate_vph_per_lane": rate, "seed": seed, "loaded": d.vehicles,
                "inserted": num(r"Inserted: (\d+)"), "teleports": len(teleports),
                "teleports_jam": sum("jam" in ln for ln in teleports),
                "waiting_time_mean_s": num(r"WaitingTime: ([\d.]+)"),
                "time_loss_mean_s": num(r"TimeLoss: ([\d.]+)"),
            })  # fmt: skip
    return rows


def mission_origin(routes: list[dict]) -> str:
    """Entry road whose route to the hospital crosses the most signals (ties: longest)."""
    reachable = [r for r in routes if r["reachable"]]
    key = lambda r: (r["signals_on_route"], r["length_m"], r["entry_edge"])  # noqa: E731
    return max(reachable, key=key)["entry_edge"]


def controller_runs(profiles, seeds, controllers, missions: bool, work_dir: Path) -> list[dict]:
    """All controllers through the normal experiment runner, with Lahore demand.

    The runner builds demand with ``manzil.scenarios.demand.build_demand`` (grid profiles);
    for this check it is swapped for :func:`build_lahore_demand` (same signature and files).
    """
    from manzil.experiments import runner
    from manzil.experiments.emergency import MissionConfig

    net_file = LAHORE_DIR / "lahore.net.xml"
    routes = hospital_routes(net_file)
    origin, hospital = mission_origin(routes), routes[0]["hospital_edge"]
    original = runner.build_demand
    runner.build_demand = build_lahore_demand
    rows = []
    try:
        jobs = [(c, p, s, None) for c in controllers for p in profiles for s in seeds]
        if missions:
            jobs += [(c, "medium", seeds[0], corridor) for c in controllers
                     for corridor in (False, True)]  # fmt: skip
        for controller, profile, seed, corridor in jobs:
            mission = None
            label = "normal"
            if corridor is not None:
                mission = MissionConfig(origin=origin, destination=hospital, corridor=corridor)
                label = "mission_corridor_on" if corridor else "mission_corridor_off"
            cfg = runner.RunConfig(scenario="lahore", profile=profile, seed=seed,
                                   controller=controller, mission=mission, label=label)  # fmt: skip
            run_dir = work_dir / f"{controller}_{profile}_s{seed}_{label}"
            result = runner.run(cfg, run_dir)
            row = {"controller": controller, "profile": profile, "seed": seed, "arm": label}
            row.update({k: result.metrics.get(k) for k in RUN_KEYS})
            if mission:
                row.update({k: result.metrics.get(k) for k in MISSION_KEYS})
            row["monitor_violations"] = len(result.violations)
            rows.append(row)
            print(f"{controller:10s} {profile:7s} s{seed} {label:22s} "
                  f"inserted {row['vehicles_inserted']}/{row['vehicles_loaded']} "
                  f"jam-teleports {row['teleports_jam']} violations {row['safety_violations']}",
                  flush=True)  # fmt: skip
    finally:
        runner.build_demand = original
    return rows


def write_rows(rows: list[dict], path: Path) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def validate(out_dir: Path = RESULTS_DIR, seeds=(0,), missions: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    net_file = LAHORE_DIR / "lahore.net.xml"
    checks = network_checks(net_file)
    routes = hospital_routes(net_file)
    write_rows(routes, out_dir / "routes_to_hospital.csv")
    calib = demand_calibration(net_file)
    write_rows(calib, out_dir / "demand_calibration.csv")
    with tempfile.TemporaryDirectory() as tmp:
        runs = controller_runs(tuple(LAHORE_PROFILES), seeds, ("fixed_time", "adaptive", "dqn"),
                               missions, Path(tmp))  # fmt: skip
    write_rows(runs, out_dir / "controller_runs.csv")
    summary = {
        "network": checks,
        "hospital_edge": routes[0]["hospital_edge"],
        "entries": len(routes),
        "entries_reaching_hospital": sum(r["reachable"] for r in routes),
        "mission_origin": mission_origin(routes),
        "runs": len(runs),
        "runs_with_safety_violations": sum(
            bool(r["safety_violations"]) or bool(r["monitor_violations"]) for r in runs
        ),
        "total_safety_violations": sum(r["safety_violations"] for r in runs),
        "total_collisions": sum(r["collisions"] or 0 for r in runs),
    }
    (out_dir / "validation.json").write_text(json.dumps(summary, indent=2) + "\n", "utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--area", choices=sorted(AREAS), default=SELECTED_AREA)
    parser.add_argument("--fetch", action="store_true", help="download raw OSM from the OSM API")
    parser.add_argument("--out-dir", type=Path, default=LAHORE_DIR)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="run the W1 checks and write results/fyp2/lahore_network/",
    )
    args = parser.parse_args(argv)
    if args.validate:
        print(json.dumps(validate(), indent=2))
        return
    area = AREAS[args.area]
    out_dir: Path = args.out_dir
    osm_dir = out_dir / "osm"
    osm_dir.mkdir(parents=True, exist_ok=True)
    raw = osm_dir / f"{area.name}.raw.osm.xml.gz"
    extract_file = osm_dir / f"{area.name}.extract.json"
    if args.fetch:
        tiles = fetch_tiles(area.bbox, osm_dir / "_tiles")
        write_osm(merge_osm(tiles), raw)
        for t in tiles:
            t.unlink()
        (osm_dir / "_tiles").rmdir()
        extract = {
            "source": OSM_API,
            "bbox": asdict(area.bbox),
            "extracted_utc": f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}",
            "raw_file": f"osm/{raw.name}",
            "raw_sha256": file_sha256(raw),
            "licence": "ODbL; (c) OpenStreetMap contributors",
        }
        extract_file.write_text(json.dumps(extract, indent=2) + "\n", encoding="utf-8")
    extract = json.loads(extract_file.read_text(encoding="utf-8"))
    if file_sha256(raw) != extract["raw_sha256"]:
        raise RuntimeError(f"{raw} does not match the checksum in {extract_file}")

    result = build_network(area, raw, out_dir, out_dir.name)
    import sumolib

    net = sumolib.net.readNet(str(result.net_file), withPrograms=True)
    record = {
        "network": result.net_file.name,
        "synthetic": False,
        "source": "OpenStreetMap",
        "licence": "Map data (c) OpenStreetMap contributors, ODbL",
        "area": {**asdict(area), "bbox": asdict(area.bbox), "hospital": asdict(area.hospital)},
        "extract": extract,
        "generator": "manzil.scenarios.osm (filter + clip, netconvert, signal cleanup)",
        "typemap": TYPEMAP.name,
        "sumo_version": sumo_version(),
        "command": result.command,
        "traffic_lights": len(net.getTrafficLights()),
        "osm_signal_nodes_in_box": result.osm_signal_nodes,
        "signals_origin": "guessed by netconvert (--tls.guess); OSM has no signal tags here"
        if result.osm_signal_nodes == 0
        else "OSM traffic_signals tags plus netconvert guesses",
        "signals_removed_by_cleanup": result.removed_tls,
        "edges_removed_by_cleanup": result.removed_edges,
        "edges": len(net.getEdges()),
        "content_sha256": content_sha256(result.net_file),
    }
    (out_dir / "network.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    signals = signal_timing(result.net_file)
    (out_dir / "signals.json").write_text(json.dumps(signals, indent=2) + "\n", encoding="utf-8")
    n_tls, n_removed = record["traffic_lights"], len(result.removed_tls)
    print(f"wrote {result.net_file}: {n_tls} traffic lights, {n_removed} removed by cleanup")


if __name__ == "__main__":
    main()
