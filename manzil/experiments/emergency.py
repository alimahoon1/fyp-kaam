"""Emergency mission inside a run: incident, dispatch, rerouting, corridor, metrics (PLAN 3.3-3.6).

Called by the runner once per step, after the snapshot and before the normal controller, in
the D2 Algorithm 3 order: snapshot -> routing -> corridor -> controller -> safety filter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from manzil.control.safety import SafetyFilter
from manzil.corridor.coordinator import CorridorCoordinator, CorridorParams
from manzil.routing.graph import RoutingGraph
from manzil.routing.mission import EmergencyMission, RerouteParams
from manzil.sim.adapter import SimulationAdapter
from manzil.sim.contracts import TrafficSnapshot
from manzil.sim.network import NetworkModel

AMBULANCE_ID = "ambulance_1"
RECOVERY_WINDOW_S = 300.0  # ordinary traffic is measured until this long after arrival


@dataclass(frozen=True)
class MissionConfig:
    origin: str = "left0A0"  # south-west corner, heading east
    destination: str = "C2top2"  # north-east corner exit
    dispatch_s: float = 1200.0
    routing: str = "dynamic"  # "static": plan once on free-flow costs; "dynamic": Algorithm 1
    corridor: bool = False
    incident: str = "none"  # "none", "closure" (hard), "slowdown" (obstruction)
    incident_edge: str = ""
    incident_s: float = 0.0
    incident_speed_mps: float = 2.0
    lookahead: int = 2
    activate_eta_s: float = 15.0
    max_priority_s: float = 60.0
    delta_s: float = 10.0
    persistence_s: float = 10.0
    cooldown_s: float = 30.0

    def validate(self) -> list[str]:
        problems = []
        if self.routing not in ("static", "dynamic"):
            problems.append(f"unknown routing {self.routing!r}")
        if self.incident not in ("none", "closure", "slowdown"):
            problems.append(f"unknown incident {self.incident!r}")
        if self.incident != "none" and not self.incident_edge:
            problems.append("incident needs an edge")
        return problems


@dataclass
class MissionDriver:
    config: MissionConfig
    network: NetworkModel
    safety: SafetyFilter
    sim: SimulationAdapter

    def __post_init__(self):
        c = self.config
        self.graph = RoutingGraph(self.network)
        for e in (c.origin, c.destination, c.incident_edge):
            if e and e not in self.graph.succ:
                raise ValueError(f"edge {e!r} is not in the routing graph")
        self.mission = EmergencyMission(
            "m1", c.origin, c.destination, self.graph,
            RerouteParams(dynamic=c.routing == "dynamic", delta_s=c.delta_s,
                          persistence_s=c.persistence_s, cooldown_s=c.cooldown_s),
        )  # fmt: skip
        self.corridor = (
            CorridorCoordinator(
                self.network,
                self.graph,
                self.safety,
                CorridorParams(
                    lookahead=c.lookahead,
                    activate_eta_s=c.activate_eta_s,
                    max_priority_s=c.max_priority_s,
                ),
            )  # fmt: skip
            if c.corridor
            else None
        )
        self.depart_s: float | None = None
        self.stops = 0
        self._moving = True
        self.waiting_s = 0.0
        self.driven: list[str] = []
        self.window_queue: list[int] = []  # network halting vehicles while the mission runs

    def step(self, snap: TrafficSnapshot) -> None:
        c, now, step = self.config, snap.sim_time_s, snap.effective_step
        if c.incident != "none" and now == c.incident_s:
            if c.incident == "closure":
                self.sim.close_edge(c.incident_edge)
            else:
                self.sim.slow_edge(c.incident_edge, c.incident_speed_mps)
        closed = self.sim.closed_edges
        m = self.mission
        if (
            m.dispatch_s is not None
            and now > m.dispatch_s
            and (
                m.status == "ACTIVE"
                or (m.arrival_s is not None and now <= m.arrival_s + RECOVERY_WINDOW_S)
            )
        ):
            self.window_queue.append(sum(e.halting for e in snap.edges.values()))

        if now == c.dispatch_s and self.mission.status == "PENDING":
            costs = (
                self.graph.free_flow_snapshot(closed)
                if c.routing == "static"
                else self.graph.live_snapshot(snap, closed, self.sim.speed_limits)
            )
            plan = self.mission.dispatch(costs, now)
            if plan is not None:
                self.sim.add_ambulance_type()
                self.sim.add_vehicle(AMBULANCE_ID, plan.edge_ids, "ambulance")
            return

        if self.mission.status != "ACTIVE":
            return
        if AMBULANCE_ID in snap.arrived_ids:
            self.mission.arrived(now)
            if self.corridor:
                self.corridor.cancel_all(now, step, "arrived")
            return
        amb = snap.tracked.get(AMBULANCE_ID)
        if amb is None or amb.edge_id == "":  # still waiting to enter the network
            return
        if self.depart_s is None:
            self.depart_s = now - 1.0  # inserted during the previous step
        self._record_motion(amb, snap)

        plan = self.mission.update(
            amb, self.graph.live_snapshot(snap, closed, self.sim.speed_limits), now, step
        )
        if plan is not None:
            self.sim.set_route(AMBULANCE_ID, plan.edge_ids)
            if self.corridor:
                self.corridor.on_route_change(plan, now, step)
        if self.mission.status == "NO_ROUTE" and self.corridor:
            self.corridor.cancel_all(now, step, "no_route")
            return
        if self.corridor:
            self.corridor.step(snap, amb, self.mission.plan)

    def _record_motion(self, amb, snap) -> None:
        if not amb.edge_id.startswith(":") and (not self.driven or self.driven[-1] != amb.edge_id):
            self.driven.append(amb.edge_id)
        moving = amb.speed_mps >= 0.1
        if self._moving and not moving:
            self.stops += 1
        if not moving:
            self.waiting_s += 1.0
        self._moving = moving

    def metrics(self) -> dict:
        m = self.mission
        arrived = m.status == "ARRIVED"
        # Response time counts from dispatch, so waiting to enter a full road is included.
        travel = (m.arrival_s - m.dispatch_s) if arrived else None
        insertion = (self.depart_s - m.dispatch_s) if self.depart_s is not None else None
        ff = sum(self.graph.free_flow_s[e] for e in self.driven[1:]) if self.driven else None
        if self.driven:  # the first edge is driven in full from the insertion point
            ff += self.graph.free_flow_s[self.driven[0]]
        revisions = [p for p in m.plans if p.route_version > 1]
        ms = [p.compute_ms for p in m.plans]
        out = {
            "mission_status": m.status,
            "amb_travel_time_s": travel,
            "amb_insertion_delay_s": insertion,
            "amb_free_flow_time_s": round(ff, 2) if ff is not None else None,
            "amb_excess_delay_s": round(travel - ff, 2) if travel is not None else None,
            "amb_stops": self.stops,
            "amb_waiting_s": self.waiting_s,
            "route_revisions": len(revisions),
            "revision_triggers": [p.trigger for p in revisions],
            "route_compute_ms_max": max(ms) if ms else None,
            "driven_route": self.driven,
            # Network halting vehicles from dispatch to 300 s after arrival (ordinary traffic).
            "mission_window_queue_mean_veh": (
                round(sum(self.window_queue) / len(self.window_queue), 3)
                if self.window_queue else None
            ),
        }  # fmt: skip
        if self.corridor:
            states = [e["state"] for e in self.corridor.events]
            rec = self.corridor.recovery_times_s
            out.update(
                corridor_activations=states.count("SAFE_TRANSITION"),
                corridor_served=states.count("ACTIVE_PRIORITY"),
                corridor_cancelled=states.count("CANCELLED"),
                corridor_timeouts=sum(
                    1 for e in self.corridor.events if e.get("reason") == "timeout"
                ),
                recovery_time_mean_s=round(sum(rec) / len(rec), 1) if rec else None,
                recovery_time_max_s=max(rec) if rec else None,
            )
        return out

    def records(self) -> dict:
        return {
            "config": asdict(self.config),
            "route_versions": [asdict(p) for p in self.mission.plans],
            "routing_log": self.mission.log,
            "corridor_events": self.corridor.events if self.corridor else [],
        }
