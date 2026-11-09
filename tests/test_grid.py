"""Task 1.1: the synthetic 3x3 grid has 9 signalised four-arm junctions and opens in SUMO."""

import json
import subprocess

import pytest
import sumolib

from manzil.scenarios.demand import DEFAULT_NET
from manzil.scenarios.grid import GridSpec, build_grid, content_sha256
from manzil.sumo_env import sumo_binary

GRID_NET = DEFAULT_NET
GRID_DIR = DEFAULT_NET.parent


@pytest.fixture(scope="module")
def net():
    return sumolib.net.readNet(str(GRID_NET), withPrograms=True)


def test_nine_traffic_lights(net):
    assert len(net.getTrafficLights()) == 9


def test_every_signalised_junction_has_four_arms(net):
    for tls in net.getTrafficLights():
        (node,) = {c[0].getEdge().getToNode() for c in tls.getConnections()}
        assert len(node.getIncoming()) == 4
        assert len(node.getOutgoing()) == 4


def test_fringe_is_dead_ends_only(net):
    types = sorted({n.getType() for n in net.getNodes()})
    assert types == ["dead_end", "traffic_light"]
    assert sum(n.getType() == "dead_end" for n in net.getNodes()) == 12


def test_every_program_has_green_and_yellow(net):
    for tls in net.getTrafficLights():
        for program in tls.getPrograms().values():
            states = [p.state for p in program.getPhases()]
            assert any("G" in s for s in states)
            assert any("y" in s for s in states)


def test_committed_network_matches_record():
    record = json.loads((GRID_DIR / "network.json").read_text())
    assert record["content_sha256"] == content_sha256(GRID_NET)
    assert record["synthetic"] is True


def test_rebuild_reproduces_committed_network(tmp_path):
    rebuilt = build_grid(tmp_path, GridSpec())
    assert content_sha256(rebuilt) == content_sha256(GRID_NET)


def test_network_loads_in_headless_sumo():
    out = subprocess.run(
        [sumo_binary("sumo"), "--net-file", str(GRID_NET), "--end", "10", "--no-step-log"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr
