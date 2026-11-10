"""Routing graph from SUMO legal movements, time-based edge costs (Eq 5.4), Dijkstra and A*.

PLAN tasks 3.1 and 3.2. Each graph node is a SUMO edge, and there is an arc ``e -> f`` only if
the network has a connection from a lane of ``e`` to a lane of ``f`` that the vehicle class may
use. A path is therefore a sequence of edges SUMO can drive, turn restrictions included.

Cost of a route = sum of the costs of the edges still to be entered (the current edge is
already being driven and is not counted). The cost of an edge, in seconds (Eq 5.4)::

    c_e = T_run + D_signal + D_queue + M_e

- ``T_run``: free-flow time, length / speed limit (no queue or signal delay inside it);
- ``D_queue``: halting vehicles on the edge x discharge headway / lanes (queue to clear);
- ``D_signal``: a declared average signal delay when the edge ends at a traffic light;
- ``M_e``: 0 when open, infinity when closed.

No measured link travel time is added on top of these terms, so congestion is not counted
twice (D2 section 5.5). Every snapshot records its estimator, source and step.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field

from manzil.sim.contracts import TrafficSnapshot
from manzil.sim.network import NetworkModel

INF = math.inf


@dataclass(frozen=True)
class CostParams:
    headway_s: float = 2.0  # queue discharge time per halting vehicle per lane
    signal_delay_s: float = 10.0  # declared mean delay at a signalised junction (estimate)
    max_snapshot_age_steps: int = 5  # older snapshots are rejected as stale


@dataclass(frozen=True)
class CostSnapshot:
    step: int
    sim_time_s: float
    costs: dict[str, float]  # edge id -> seconds (inf if closed)
    estimator: str
    source: str

    def route_cost(self, edges) -> float:
        return sum(self.costs[e] for e in edges)


@dataclass
class RoutingGraph:
    network: NetworkModel
    vclass: str = "emergency"
    params: CostParams = field(default_factory=CostParams)
    succ: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False)
    free_flow_s: dict[str, float] = field(default_factory=dict, init=False)
    length_m: dict[str, float] = field(default_factory=dict, init=False)
    lanes: dict[str, int] = field(default_factory=dict, init=False)
    signalised: set[str] = field(default_factory=set, init=False)
    max_speed: float = field(default=0.0, init=False)
    length_ratio: float = field(default=1.0, init=False)  # min edge length / node distance
    _xy_from: dict[str, tuple[float, float]] = field(default_factory=dict, init=False)
    _xy_to: dict[str, tuple[float, float]] = field(default_factory=dict, init=False)

    def __post_init__(self):
        net = self.network.net
        for e in net.getEdges():
            if not e.allows(self.vclass):
                continue
            eid = e.getID()
            succ = set()
            for lane in e.getLanes():
                for c in lane.getOutgoing():
                    to = c.getToLane()
                    if to.allows(self.vclass) and lane.allows(self.vclass):
                        succ.add(to.getEdge().getID())
            self.succ[eid] = tuple(sorted(succ))
            self.free_flow_s[eid] = e.getLength() / e.getSpeed()
            self.length_m[eid] = e.getLength()
            self.lanes[eid] = e.getLaneNumber()
            self.max_speed = max(self.max_speed, e.getSpeed())
            self._xy_from[eid] = e.getFromNode().getCoord()
            self._xy_to[eid] = e.getToNode().getCoord()
            if e.getToNode().getType() == "traffic_light":
                self.signalised.add(eid)
        ratios = [
            self.free_flow_s[e] * net.getEdge(e).getSpeed() / d
            for e in self.succ
            if (d := math.dist(self._xy_from[e], self._xy_to[e])) > 0
        ]
        self.length_ratio = min([1.0, *ratios])

    # ----- costs -----------------------------------------------------------------------------
    def free_flow_snapshot(self, closed=frozenset()) -> CostSnapshot:
        costs = {e: (INF if e in closed else t) for e, t in self.free_flow_s.items()}
        return CostSnapshot(-1, 0.0, costs, "free_flow", "network file")

    def live_snapshot(
        self, snap: TrafficSnapshot, closed=frozenset(), speed_limits=None
    ) -> CostSnapshot:
        """Eq 5.4 from one traffic snapshot; edges without data fall back to free flow.

        ``speed_limits`` are reduced limits from reported incidents (an obstruction): the run
        time then uses the reduced limit, just as a closure uses infinity.
        """
        p = self.params
        speed_limits = speed_limits or {}
        costs = {}
        for e, t_run in self.free_flow_s.items():
            if e in closed:
                costs[e] = INF
                continue
            if e in speed_limits:
                t_run = max(t_run, self.length_m[e] / speed_limits[e])
            st = snap.edges.get(e)
            d_queue = st.halting * p.headway_s / self.lanes[e] if st else 0.0
            d_signal = p.signal_delay_s if e in self.signalised else 0.0
            costs[e] = t_run + d_queue + d_signal
        return CostSnapshot(snap.effective_step, snap.sim_time_s, costs, "eq5.4", "sumo")

    def validate(self, costs: CostSnapshot, now_step: int) -> None:
        if costs.step >= 0 and now_step - costs.step > self.params.max_snapshot_age_steps:
            raise ValueError(f"stale cost snapshot from step {costs.step} at step {now_step}")
        if any(c < 0 for c in costs.costs.values()):
            raise ValueError("negative edge cost")

    # ----- search ----------------------------------------------------------------------------
    def heuristic(self, edge: str, goal: str) -> float:
        """Admissible lower bound on the cost still to come.

        The edges between ``edge`` and ``goal`` connect the end node of ``edge`` to the start node
        of ``goal``, so their node-to-node distances sum to at least the straight line between
        those nodes (triangle inequality). SUMO edge lengths exclude junction interiors, so each
        edge is at least ``length_ratio`` times its node distance, and each costs at least
        length / max speed. Hence ``length_ratio * straight line / max speed`` never
        overestimates (D2: A* only with an admissible free-flow heuristic).
        """
        if edge == goal:
            return 0.0
        d = math.dist(self._xy_to[edge], self._xy_from[goal])
        return self.length_ratio * d / self.max_speed

    def shortest_path(
        self, start: str, goal: str, costs: CostSnapshot, use_astar: bool = False
    ) -> tuple[list[str] | None, float, int]:
        """(path from start to goal inclusive, cost of edges after start, nodes expanded)."""
        if start not in self.succ or goal not in self.succ:
            raise KeyError(f"unknown or forbidden edge {start!r} or {goal!r}")
        c = costs.costs
        dist = {start: 0.0}
        prev: dict[str, str] = {}
        h = (lambda e: self.heuristic(e, goal)) if use_astar else (lambda e: 0.0)
        heap = [(h(start), 0.0, start)]
        done = set()
        expanded = 0
        while heap:
            _, d, e = heapq.heappop(heap)
            if e in done:
                continue
            done.add(e)
            expanded += 1
            if e == goal:
                path = [e]
                while path[-1] != start:
                    path.append(prev[path[-1]])
                return path[::-1], d, expanded
            for f in self.succ[e]:
                w = c[f]
                if w == INF:
                    continue
                nd = d + w
                if nd < dist.get(f, INF):
                    dist[f] = nd
                    prev[f] = e
                    heapq.heappush(heap, (nd + h(f), nd, f))
        return None, INF, expanded

    def is_valid_path(self, path) -> bool:
        pairs = zip(path, path[1:], strict=False)
        return bool(path) and all(b in self.succ.get(a, ()) for a, b in pairs)


@dataclass(frozen=True)
class RoutePlan:
    """An immutable route version (D2 Table 6.3)."""

    mission_id: str
    route_version: int
    edge_ids: tuple[str, ...]
    cost_s: float
    snapshot_step: int
    trigger: str  # "dispatch", "closure", "improvement"
    compute_ms: float


def timed_path(graph: RoutingGraph, start, goal, costs, use_astar=False):
    t0 = time.perf_counter()
    path, cost, expanded = graph.shortest_path(start, goal, costs, use_astar)
    return path, cost, expanded, (time.perf_counter() - t0) * 1000
