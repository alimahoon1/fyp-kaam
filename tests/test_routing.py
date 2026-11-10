"""Tasks 3.1-3.4: routing graph, Eq 5.4 costs, Dijkstra = A*, Algorithm 1 rerouting."""

import math
import random
from dataclasses import replace

import pytest

from manzil.routing.graph import INF, CostSnapshot, RoutingGraph
from manzil.routing.mission import EmergencyMission, RerouteParams
from manzil.sim.contracts import EdgeState, VehicleState


@pytest.fixture(scope="module")
def graph(grid_model):
    return RoutingGraph(grid_model)


def snap_costs(graph, costs, step=0):
    return CostSnapshot(step, float(step), costs, "test", "test")


def test_graph_follows_sumo_connections(graph, grid_model):
    assert len(graph.succ) == 48
    for e, succ in graph.succ.items():
        edge = grid_model.net.getEdge(e)
        legal = {c.getTo().getID() for c in edge.getOutgoing() for c in edge.getOutgoing()[c]}
        assert set(succ) <= legal
        # no U-turns on the grid (netgenerate --no-turnarounds)
        assert all(grid_model.net.getEdge(f).getToNode() != edge.getFromNode() for f in succ)


def test_free_flow_route_cost(graph):
    ff = graph.free_flow_snapshot()
    path, cost, _ = graph.shortest_path("left0A0", "C2top2", ff)
    assert graph.is_valid_path(path)
    assert cost == pytest.approx(sum(graph.free_flow_s[e] for e in path[1:]))
    assert len(path) == 6  # 4 blocks + entry + exit: a shortest grid path


def test_astar_matches_dijkstra_on_random_costs(graph):
    rng = random.Random(0)
    edges = sorted(graph.succ)
    for _ in range(200):
        costs = {e: graph.free_flow_s[e] + rng.uniform(0, 60) for e in edges}
        snap = snap_costs(graph, costs)
        a, b = rng.choice(edges), rng.choice(edges)
        p1, c1, n1 = graph.shortest_path(a, b, snap, use_astar=False)
        p2, c2, n2 = graph.shortest_path(a, b, snap, use_astar=True)
        assert (p1 is None) == (p2 is None)
        if p1:
            assert c2 == pytest.approx(c1)
            assert n2 <= n1


def test_heuristic_is_admissible(graph):
    ff = graph.free_flow_snapshot()
    for a in graph.succ:
        for b in graph.succ:
            path, cost, _ = graph.shortest_path(a, b, ff)
            if path:
                assert graph.heuristic(a, b) <= cost + 1e-9


def test_closure_is_avoided_and_can_disconnect(graph):
    path, _, _ = graph.shortest_path("left0A0", "C2top2", graph.free_flow_snapshot())
    closed = {path[2]}
    p2, c2, _ = graph.shortest_path("left0A0", "C2top2", graph.free_flow_snapshot(closed))
    assert p2 and not closed & set(p2) and math.isfinite(c2)
    # Closing every road into the destination's junction leaves no route.
    into = {e for e, s in graph.succ.items() if "C2top2" in s}
    p3, c3, _ = graph.shortest_path("left0A0", "C2top2", graph.free_flow_snapshot(into))
    assert p3 is None and c3 == INF


def test_live_costs_follow_equation_5_4(graph, grid_model):
    edges = {e: EdgeState(e, 0, 0, 0.0) for e in graph.succ}
    edges["A0B0"] = EdgeState("A0B0", 10, 6, 0.5)
    from tests.test_adaptive import snapshot  # a hand-made traffic snapshot

    snap = replace(snapshot(grid_model, 50), edges=edges)
    c = graph.live_snapshot(snap, closed={"B0C0"}, speed_limits={"A1A2": 2.0})
    p = graph.params
    assert c.costs["A0B0"] == pytest.approx(
        graph.free_flow_s["A0B0"] + 6 * p.headway_s / 2 + p.signal_delay_s
    )
    assert c.costs["B0C0"] == INF
    assert c.costs["A1A2"] == pytest.approx(graph.length_m["A1A2"] / 2.0 + p.signal_delay_s)
    assert c.costs["A0bottom0"] == pytest.approx(graph.free_flow_s["A0bottom0"])  # no signal


def test_stale_and_negative_costs_rejected(graph):
    costs = dict(graph.free_flow_snapshot().costs)
    with pytest.raises(ValueError, match="stale"):
        graph.validate(snap_costs(graph, costs, step=10), now_step=100)
    costs["A0B0"] = -1.0
    with pytest.raises(ValueError, match="negative"):
        graph.validate(snap_costs(graph, costs, step=100), now_step=100)


# ----- Algorithm 1 ---------------------------------------------------------------------------
def amb(edge, idx=0):
    return VehicleState("amb", edge, f"{edge}_0", 10.0, 10.0, 0.0, idx)


def mission(graph, **kw):
    return EmergencyMission("m", "left0A0", "C2top2", graph, RerouteParams(**kw))


def test_dispatch_rejects_bad_endpoints(graph):
    with pytest.raises(ValueError):
        EmergencyMission("m", "nope", "C2top2", graph).dispatch(graph.free_flow_snapshot(), 0)


def test_closure_forces_new_version_at_once(graph):
    m = mission(graph)
    v1 = m.dispatch(graph.free_flow_snapshot(), 0.0)
    closed = graph.free_flow_snapshot({v1.edge_ids[2]})
    v2 = m.update(amb("left0A0"), closed, 1.0, 0)
    assert v2.route_version == 2 and v2.trigger == "closure"
    assert v1.edge_ids[2] not in v2.edge_ids and graph.is_valid_path(v2.edge_ids)


def test_improvement_needs_threshold_persistence_and_cooldown(graph):
    m = mission(graph, delta_s=10, persistence_s=10, cooldown_s=0, refresh_s=1)
    v1 = m.dispatch(graph.free_flow_snapshot(), 0.0)
    costs = dict(graph.free_flow_snapshot().costs)
    costs[v1.edge_ids[2]] += 5  # saving below delta: never reroute
    for t in range(1, 30):
        assert m.update(amb("left0A0"), snap_costs(graph, costs, t), float(t), t) is None
    costs[v1.edge_ids[2]] += 100  # big saving: accepted only after persisting 10 s
    accepted = [
        t
        for t in range(30, 60)
        if m.update(amb("left0A0"), snap_costs(graph, costs, t), float(t), t) is not None
    ]
    assert accepted and accepted[0] >= 40 and m.version == 2
    assert m.plan.trigger == "improvement"
    assert any(e["event"] == "candidate_rejected" for e in m.log)


def test_no_route_reported(graph):
    m = mission(graph)
    m.dispatch(graph.free_flow_snapshot(), 0.0)
    into = {e for e, s in graph.succ.items() if "C2top2" in s}
    assert m.update(amb("left0A0"), graph.free_flow_snapshot(into), 1.0, 0) is None
    assert m.status == "NO_ROUTE"


def test_static_routing_never_revises(graph):
    m = mission(graph, dynamic=False)
    v1 = m.dispatch(graph.free_flow_snapshot(), 0.0)
    assert m.update(amb("left0A0"), graph.free_flow_snapshot({v1.edge_ids[2]}), 1.0, 0) is None
    assert m.version == 1
