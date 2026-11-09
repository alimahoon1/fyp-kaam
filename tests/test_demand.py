"""Task 1.2: seeded demand profiles are deterministic, network-derived, and run without gridlock."""

import pytest
import sumolib

from manzil.scenarios.check import run_check
from manzil.scenarios.demand import (
    DEFAULT_NET,
    PROFILES,
    build_demand,
    fringe_edges,
    generate_trips,
)

GRID_NET = DEFAULT_NET


@pytest.fixture(scope="module")
def net():
    return sumolib.net.readNet(str(GRID_NET))


def test_fringe_edges_found_from_network(net):
    entries, exits = fringe_edges(net)
    assert len(entries) == 12 and len(exits) == 12
    # On the grid, half the entry roads run north-south.
    assert sum(e.north_south for e in entries) == 6


def test_same_seed_same_trips(net):
    a = generate_trips(net, PROFILES["medium"], seed=7, duration_s=600)
    b = generate_trips(net, PROFILES["medium"], seed=7, duration_s=600)
    assert a == b


def test_different_seed_different_trips(net):
    a = generate_trips(net, PROFILES["medium"], seed=1, duration_s=600)
    b = generate_trips(net, PROFILES["medium"], seed=2, duration_s=600)
    assert a != b


def test_no_u_turn_trips(net):
    entries, exits = fringe_edges(net)
    node_of = {f.edge_id: f.node_id for f in entries + exits}
    for t in generate_trips(net, PROFILES["heavy"], seed=0, duration_s=600):
        assert node_of[t.from_edge] != node_of[t.to_edge]


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_vehicle_count_matches_rate(net, name):
    profile = PROFILES[name]
    duration = 3600.0
    expected = 6 * (profile.major_rate_vph + profile.minor_rate_vph) * duration / 3600
    n = len(generate_trips(net, profile, seed=0, duration_s=duration))
    assert abs(n - expected) < 0.1 * expected  # Poisson noise is about 1-2 % here


def test_profiles_ordered_by_load(net):
    totals = {
        name: len(generate_trips(net, p, seed=0, duration_s=3600)) for name, p in PROFILES.items()
    }
    assert totals["light"] < totals["medium"] < totals["heavy"]


def test_uneven_is_unbalanced(net):
    entries, _ = fringe_edges(net)
    ns = {e.edge_id for e in entries if e.north_south}
    trips = generate_trips(net, PROFILES["uneven"], seed=0, duration_s=3600)
    n_ns = sum(t.from_edge in ns for t in trips)
    assert n_ns > 5 * (len(trips) - n_ns)


def test_build_demand_writes_routes(tmp_path):
    files = build_demand("light", seed=0, duration_s=300, net_file=GRID_NET, out_dir=tmp_path)
    text = files.routes.read_text()
    assert files.vehicles > 0
    assert text.count("<vehicle ") == files.vehicles
    assert files.sumocfg.is_file() and files.manifest.is_file()


def test_light_short_run_is_gridlock_free(tmp_path):
    r = run_check("light", seed=0, duration_s=600, drain_s=600, work_dir=tmp_path)
    assert r.gridlock_free
    assert r.vehicles_arrived == r.vehicles_loaded > 0
    assert r.collisions == 0
