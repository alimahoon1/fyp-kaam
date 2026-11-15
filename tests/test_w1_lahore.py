"""W1: Lahore (Ichhra) OSM network, joined traffic lights, demand and controller smoke runs."""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import sumolib

from manzil.control.fixed_time import SignalTiming
from manzil.scenarios import osm
from manzil.scenarios.demand import fringe_edges
from manzil.scenarios.grid import content_sha256
from manzil.sim.network import NetworkModel
from manzil.sumo_env import sumo_binary

LAHORE = osm.LAHORE_DIR
NET = LAHORE / "lahore.net.xml"


@pytest.fixture(scope="module")
def model():
    return NetworkModel.from_file(NET)


@pytest.fixture(scope="module")
def record():
    return json.loads((LAHORE / "network.json").read_text(encoding="utf-8"))


# ----------------------------------------------------------------- projection and OSM handling


@pytest.mark.parametrize(
    "lat, lon, zone, east, north",
    [  # reference values from pyproj 3 (+proj=utm, WGS84)
        (31.5238238, 74.3228094, 43, 435706.6828, 3487855.7948),
        (31.514, 74.313, 43, 434768.5203, 3486772.7446),
        (24.86, 67.0, 42, 297925.7758, 2750928.9967),
    ],
)
def test_utm_forward_matches_pyproj(lat, lon, zone, east, north):
    e, n = osm.utm_forward(lat, lon, zone)
    assert e == pytest.approx(east, abs=1e-3)
    assert n == pytest.approx(north, abs=1e-3)


def _osm(*elements: str) -> ET.Element:
    return ET.fromstring("<osm version='0.6'>" + "".join(elements) + "</osm>")


def _node(i, lat, lon, tags=""):
    return f"<node id='{i}' lat='{lat}' lon='{lon}'>{tags}</node>"


def _way(i, refs, highway):
    nds = "".join(f"<nd ref='{r}'/>" for r in refs)
    return f"<way id='{i}'>{nds}<tag k='highway' v='{highway}'/></way>"


def test_filter_and_clip_splits_ways_and_drops_minor_roads():
    box = osm.BBox(0.0, 0.0, 1.0, 1.0)
    root = _osm(
        _node(1, 0.1, 0.1), _node(2, 0.2, 0.2), _node(3, 2.0, 0.3),  # 3 is outside
        _node(4, 0.4, 0.4), _node(5, 0.5, 0.5),
        _node(6, 0.6, 0.6, "<tag k='highway' v='traffic_signals'/>"), _node(7, 0.7, 0.7),
        _way(10, [1, 2, 3, 4, 5], "primary"),
        _way(11, [6, 7], "residential"),
        _way(12, [5, 6], "tertiary"),
        "<relation id='20'><member type='way' ref='11' role='from'/>"
        "<member type='node' ref='6' role='via'/><member type='way' ref='12' role='to'/>"
        "<tag k='type' v='restriction'/></relation>",
    )  # fmt: skip
    out = osm.filter_and_clip(root, box)
    ways = {w.get("id"): [nd.get("ref") for nd in w.findall("nd")] for w in out.findall("way")}
    assert ways["10"] == ["1", "2"]
    split = [k for k in ways if int(k) > 10**15]
    assert len(split) == 1 and ways[split[0]] == ["4", "5"]
    assert ways["12"] == ["5", "6"]
    assert "11" not in ways  # residential dropped
    assert {n.get("id") for n in out.findall("node")} == {"1", "2", "4", "5", "6"}
    assert out.findall("relation") == []  # its member way 11 was dropped
    assert osm.signal_nodes(out) == ["6"]


def test_strong_core_and_connectivity_rule():
    graph = {"a": ["b"], "b": ["c"], "c": ["a", "x"], "x": [], "in": ["a"], "lost": ["in"]}
    assert osm._strong_core(graph) == {"a", "b", "c"}
    reverse = {k: [] for k in graph}
    for k, outs in graph.items():
        for o in outs:
            reverse[o].append(k)
    assert osm._closure({"a"}, graph) == {"a", "b", "c", "x"}
    assert osm._closure({"a"}, reverse) == {"a", "b", "c", "in", "lost"}


# ----------------------------------------------------------------- joined traffic lights


def _joined_net(tmp_path: Path) -> Path:
    """Two signalised crossings 20 m apart on one road, joined into one traffic light."""
    nodes = tmp_path / "j.nod.xml"
    edges = tmp_path / "j.edg.xml"
    nodes.write_text(
        "<nodes>"
        "<node id='W' x='-200' y='0'/><node id='A' x='0' y='0' type='traffic_light'/>"
        "<node id='B' x='20' y='0' type='traffic_light'/><node id='E' x='220' y='0'/>"
        "<node id='AN' x='0' y='200'/><node id='AS' x='0' y='-200'/>"
        "<node id='BN' x='20' y='200'/><node id='BS' x='20' y='-200'/>"
        "</nodes>"
    )
    pairs = [("W", "A"), ("A", "B"), ("B", "E"), ("AN", "A"), ("A", "AS"), ("BS", "B"), ("B", "BN")]
    e = "".join(
        f"<edge id='{a}{b}' from='{a}' to='{b}' numLanes='1' speed='13.9'/>"
        f"<edge id='{b}{a}' from='{b}' to='{a}' numLanes='1' speed='13.9'/>"
        for a, b in pairs
    )
    edges.write_text(f"<edges>{e}</edges>")
    net = tmp_path / "joined.net.xml"
    subprocess.run(
        [sumo_binary("netconvert"), "--node-files", str(nodes), "--edge-files", str(edges),
         "--tls.join", "true", "--tls.join-dist", "30", "--no-turnarounds", "true",
         "--output-file", str(net)],
        check=True, capture_output=True,
    )  # fmt: skip
    return net


def test_joined_traffic_light_is_read(tmp_path):
    model = NetworkModel.from_file(_joined_net(tmp_path))
    assert len(model.intersections) == 1
    (x,) = model.intersections.values()
    assert x.joined and set(x.junction_ids) == {"A", "B"}
    assert {lk.junction_id for lk in x.links} == {"A", "B"}
    for g in x.green_phases:  # netconvert's joined program is conflict-free
        assert x.conflicts_in(g.state) == []
    assert x.conflicts_in("G" * x.num_links)  # all green is not
    for a in range(x.num_links):
        for b in range(x.num_links):
            assert x.are_foes(a, b) == x.are_foes(b, a)
            if x.links[a].junction_id != x.links[b].junction_id:
                assert not x.are_foes(a, b)  # different junctions never conflict


def test_single_junction_links_carry_their_junction(model):
    for x in model.intersections.values():
        assert not x.joined
        assert {lk.junction_id for lk in x.links} == set(x.junction_ids)


# ----------------------------------------------------------------- the committed Lahore network


def test_raw_extract_matches_its_checksum(record):
    raw = LAHORE / record["extract"]["raw_file"]
    assert osm.file_sha256(raw) == record["extract"]["raw_sha256"]
    assert record["area"]["name"] == osm.SELECTED_AREA == "ichhra"


def test_rebuild_reproduces_committed_network(tmp_path, record):
    area = osm.AREAS[record["area"]["name"]]
    result = osm.build_network(area, LAHORE / record["extract"]["raw_file"], tmp_path, "lahore")
    assert content_sha256(result.net_file) == record["content_sha256"] == content_sha256(NET)
    assert result.removed_tls == record["signals_removed_by_cleanup"]
    assert result.removed_edges == record["edges_removed_by_cleanup"]


def test_network_size_and_driving_side(model, record):
    assert 10 <= len(model.intersections) <= 20  # D2 planning range
    assert len(model.intersections) == record["traffic_lights"]
    net = ET.parse(NET).getroot()
    assert net.get("lefthand") == "true"  # Pakistan drives on the left


def test_green_phases_are_conflict_free(model):
    for x in model.intersections.values():
        for g in x.green_phases:
            assert x.conflicts_in(g.state) == []
        served = set().union(*(g.green_links() for g in x.green_phases))
        assert served == set(range(x.num_links))


def test_rl_layout_limits_hold(model):
    # rl_env allows at most 4 approaches and 4 green phases per traffic light
    for x in model.intersections.values():
        assert len(x.approaches) <= 4 and len(x.green_phases) <= 4


def test_every_entry_reaches_the_hospital():
    rows = osm.hospital_routes(NET)
    assert len(rows) >= 10
    assert all(r["reachable"] for r in rows)
    assert rows[0]["hospital_edge"] == "25036926"  # Fazal Elahi Road at WAPDA Hospital


def test_every_entry_reaches_every_exit():
    net = sumolib.net.readNet(str(NET))
    entries, exits = fringe_edges(net)
    for entry in entries:
        for ex in exits:
            if ex.node_id != entry.node_id:
                path, _ = net.getShortestPath(net.getEdge(entry.edge_id), net.getEdge(ex.edge_id))
                assert path is not None, (entry.edge_id, ex.edge_id)


def test_signal_file_loads_and_matches_network(model):
    timing = SignalTiming.load(LAHORE / "signals.json")
    for profile in osm.LAHORE_PROFILES:
        plan = timing.resolve_plan("auto", profile)
        ctrl = timing.fixed_time_controller(model, plan)
        ctrl.reset(model, timing.safety)  # checks phase counts and min green
    assert timing == SignalTiming.load(LAHORE / "signals.json")
    assert json.loads((LAHORE / "signals.json").read_text()) == osm.signal_timing(NET)


def test_lahore_demand_is_seeded_and_routable(tmp_path):
    a = osm.build_lahore_demand("light", 7, 600.0, NET, tmp_path / "a")
    b = osm.build_lahore_demand("light", 7, 600.0, NET, tmp_path / "b")
    assert a.vehicles == b.vehicles > 0

    def vehicles(path):
        root = ET.parse(path).getroot()
        return [(v.get("id"), v.get("depart"), v.find("route").get("edges"))
                for v in root.findall("vehicle")]  # fmt: skip

    assert vehicles(a.routes) == vehicles(b.routes)
    assert len(vehicles(a.routes)) == a.vehicles  # duarouter found a route for every trip


def test_sumo_loads_headless():
    proc = subprocess.run(
        [sumo_binary("sumo"), "--net-file", str(NET), "--end", "5"], capture_output=True
    )
    assert proc.returncode == 0


# ----------------------------------------------------------------- controllers on Lahore


@pytest.mark.parametrize("controller", ["fixed_time", "adaptive", "dqn"])
def test_controller_runs_without_safety_violations(controller, tmp_path):
    if controller == "dqn":
        pytest.importorskip("torch")
    rows = osm.controller_runs(("medium",), (0,), (controller,), False, tmp_path, 120.0, 480.0)
    (row,) = rows
    assert row["safety_violations"] == 0 and row["monitor_violations"] == 0
    assert row["collisions"] == 0
    assert row["teleports_jam"] == 0
    assert row["vehicles_inserted"] >= 0.99 * row["vehicles_loaded"]  # no gridlock
