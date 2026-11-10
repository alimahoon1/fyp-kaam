"""Emergency mission routing with stable rerouting: D2 Algorithm 1 (PLAN tasks 3.3 and 3.4).

One active ambulance. The mission owns immutable ``RoutePlan`` versions. ``update`` runs every
``refresh_s`` from the ambulance's current edge:

1. Validate the cost snapshot (not stale, no negative cost); closures cost infinity.
2. Search a candidate route (A* with the admissible heuristic, or Dijkstra).
3. No candidate -> ``NO_ROUTE`` (the caller cancels future corridor requests).
4. Compare remaining costs of current and candidate routes under the same snapshot.
5. If the current route is infeasible (it crosses a closure) accept the candidate at once.
   Otherwise accept only if it saves more than ``delta_s`` continuously for ``persistence_s``
   and ``cooldown_s`` has passed since the last change.
6. Accepting increments the route version; the caller cancels obsolete corridor requests.

Static routing (the D2 comparison baseline) plans once at dispatch on free-flow costs and never
revises. Routing never actuates SUMO; the runner applies a new plan through the adapter.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from manzil.routing.graph import CostSnapshot, RoutePlan, RoutingGraph, timed_path
from manzil.sim.contracts import VehicleState


@dataclass(frozen=True)
class RerouteParams:
    dynamic: bool = True
    refresh_s: float = 5.0
    delta_s: float = 10.0  # minimum saving (s) for an improvement reroute
    persistence_s: float = 10.0  # the saving must last this long
    cooldown_s: float = 30.0  # minimum time between improvement reroutes
    use_astar: bool = True


@dataclass
class EmergencyMission:
    mission_id: str
    origin: str
    destination: str
    graph: RoutingGraph
    params: RerouteParams = field(default_factory=RerouteParams)
    status: str = "PENDING"  # PENDING, ACTIVE, ARRIVED, NO_ROUTE
    plans: list[RoutePlan] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)  # revisions and rejected candidates
    dispatch_s: float | None = None
    arrival_s: float | None = None
    _last_refresh: float = -math.inf
    _last_change: float = -math.inf
    _better_since: float | None = None

    @property
    def plan(self) -> RoutePlan | None:
        return self.plans[-1] if self.plans else None

    @property
    def version(self) -> int:
        return self.plan.route_version if self.plan else 0

    def dispatch(self, costs: CostSnapshot, now: float) -> RoutePlan | None:
        """First route version (v1). Validates origin and destination (FR-09)."""
        if self.origin not in self.graph.succ or self.destination not in self.graph.succ:
            raise ValueError(f"invalid origin/destination {self.origin!r} -> {self.destination!r}")
        path, cost, expanded, ms = timed_path(
            self.graph, self.origin, self.destination, costs, self.params.use_astar
        )
        self.dispatch_s = now
        self._last_refresh = now
        if path is None:
            self.status = "NO_ROUTE"
            self._log(now, "no_route", None, None, expanded, ms)
            return None
        self.status = "ACTIVE"
        return self._accept(path, cost, costs, now, "dispatch", expanded, ms)

    def update(self, vehicle: VehicleState | None, costs: CostSnapshot, now: float, step: int):
        """Algorithm 1. Returns a new RoutePlan when the route changes, else None."""
        if self.status != "ACTIVE" or vehicle is None or not self.params.dynamic:
            return None
        if vehicle.edge_id.startswith(":"):  # inside a junction: wait for the next edge
            return None
        if now - self._last_refresh < self.params.refresh_s and not self._crosses_closure(costs):
            return None
        self._last_refresh = now
        self.graph.validate(costs, step)
        current = self.plan.edge_ids
        if vehicle.edge_id not in current:
            raise RuntimeError(f"ambulance on {vehicle.edge_id}, not on its route {current}")
        remaining = current[current.index(vehicle.edge_id) :]
        cand, cand_cost, expanded, ms = timed_path(
            self.graph, vehicle.edge_id, self.destination, costs, self.params.use_astar
        )
        if cand is None:
            self.status = "NO_ROUTE"
            self._log(now, "no_route", None, None, expanded, ms)
            return None
        cur_cost = costs.route_cost(remaining[1:])
        if tuple(cand) == remaining:
            self._better_since = None
            return None
        if math.isinf(cur_cost):
            return self._accept(cand, cand_cost, costs, now, "closure", expanded, ms)
        saving = cur_cost - cand_cost
        if saving <= self.params.delta_s:
            self._better_since = None
            return None
        if self._better_since is None:
            self._better_since = now
        persisted = now - self._better_since >= self.params.persistence_s
        cooled = now - self._last_change >= self.params.cooldown_s
        if persisted and cooled:
            return self._accept(cand, cand_cost, costs, now, "improvement", expanded, ms)
        self._log(now, "candidate_rejected", saving, "persistence" if not persisted else
                  "cooldown", expanded, ms)  # fmt: skip
        return None

    def arrived(self, now: float) -> None:
        self.status = "ARRIVED"
        self.arrival_s = now

    # ----- internals -------------------------------------------------------------------------
    def _crosses_closure(self, costs: CostSnapshot) -> bool:
        return self.plan is not None and any(
            math.isinf(costs.costs.get(e, 0.0)) for e in self.plan.edge_ids
        )

    def _accept(self, path, cost, costs, now, trigger, expanded, ms) -> RoutePlan:
        plan = RoutePlan(
            mission_id=self.mission_id,
            route_version=self.version + 1,
            edge_ids=tuple(path),
            cost_s=round(cost, 3),
            snapshot_step=costs.step,
            trigger=trigger,
            compute_ms=round(ms, 3),
        )
        self.plans.append(plan)
        self._last_change = now
        self._better_since = None
        self._log(now, f"route_v{plan.route_version}", None, trigger, expanded, ms)
        return plan

    def _log(self, now, event, saving, reason, expanded, ms):
        self.log.append(
            {
                "time_s": now,
                "event": event,
                "route_version": self.version,
                "saving_s": None if saving is None else round(saving, 2),
                "reason": reason,
                "nodes_expanded": expanded,
                "compute_ms": round(ms, 3),
            }
        )
