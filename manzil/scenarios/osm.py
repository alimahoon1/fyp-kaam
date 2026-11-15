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

    python -m manzil.scenarios.osm --area <name> --fetch   # download raw OSM (needs internet)
    python -m manzil.scenarios.osm --area <name>           # rebuild the network from the raw file
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import subprocess
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


def netconvert_command(area: Area, osm_file: Path, net_file: Path, typemap: Path = TYPEMAP):
    return [
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
        "--tls.guess-signals", "true",
        "--tls.guess", "true",
        "--tls.guess.joining", "true",
        "--tls.guess.threshold", str(area.tls_guess_threshold),
        "--tls.join", "true",
        "--tls.default-type", "static",
        "--lefthand", "true",  # Pakistan drives on the left
        "--no-turnarounds", "true",
        "--osm.layer-elevation", "5",
        "--output-file", str(net_file),
    ]  # fmt: skip


def build_network(area: Area, raw_osm: Path, out_dir: Path) -> Path:
    """Filter + clip ``raw_osm`` to ``area`` and run netconvert; writes net + record."""
    out_dir.mkdir(parents=True, exist_ok=True)
    root = filter_and_clip(read_osm(raw_osm), area.bbox)
    filtered = out_dir / f"{area.name}.filtered.osm.xml"
    write_osm(root, filtered)
    net_file = out_dir / f"{area.name}.net.xml"
    cmd = netconvert_command(area, filtered, net_file)
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    filtered.unlink()
    return net_file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--area", choices=sorted(AREAS), required=True)
    parser.add_argument("--fetch", action="store_true", help="download raw OSM from the OSM API")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    area = AREAS[args.area]
    out_dir = args.out_dir or LAHORE_DIR / area.name
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{area.name}.raw.osm.xml.gz"
    if args.fetch:
        tiles = fetch_tiles(area.bbox, out_dir / "_tiles")
        write_osm(merge_osm(tiles), raw)
        for t in tiles:
            t.unlink()
        (out_dir / "_tiles").rmdir()
        (out_dir / "extract.json").write_text(
            json.dumps(
                {
                    "source": OSM_API,
                    "bbox": asdict(area.bbox),
                    "extracted_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "raw_file": raw.name,
                    "raw_sha256": file_sha256(raw),
                    "licence": "ODbL; (c) OpenStreetMap contributors",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    net_file = build_network(area, raw, out_dir)
    print(f"wrote {net_file} ({content_sha256(net_file)[:12]}), {sumo_version()}")


if __name__ == "__main__":
    main()
