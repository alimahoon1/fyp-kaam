"""Emergency mission inside a run: incident, dispatch, rerouting, corridor, metrics (PLAN 3.3-3.6).

Called by the runner once per step, after the snapshot and before the normal controller, in
the D2 Algorithm 3 order: snapshot -> routing -> corridor -> controller -> safety filter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from manzil.control.safety import SafetyFilter
from manzil.corridor.coordinator import CorridorCoordinator, CorridorParams, phase_for
from manzil.routing.graph import RoutingGraph
from manzil.routing.mission import EmergencyMission, RerouteParams
from manzil.sim.adapter import SimulationAdapter
from manzil.sim.contracts import TrafficSnapshot
from manzil.sim.network import NetworkModel

AMBULANCE_ID = "ambulance_1"
RECOVERY_WINDOW_S = 300.0  # ordinary traffic is measured until this long after arrival
FIXED_WINDOW_S = 600.0  # same-length window from dispatch for every arm (cross-street waiting)
RED_CHARS = "ryu"  # SUMO link states that forbid entering the junction (red, yellow, red-yellow)
# Stop reasons (task 3.7), rolled up into the four groups reported.
STOP_GROUPS = {
    "red_corridor_not_active": "red_corridor",  # request exists, activation not reached yet
    "red_corridor_min_green": "red_corridor",  # activated, filter still finishing min green
    "red_corridor_clearance": "red_corridor",  # activated, yellow / all-red running
    "red_corridor_other": "red_corridor",
    "red_outside_lookahead": "red_outside_lookahead",  # no corridor request for the junction
    "red_no_corridor": "red_no_corridor",  # corridor off
    "queue_at_red": "queue",  # vehicles between the ambulance and a red stop line
    "queue_at_green": "queue",  # vehicles ahead still discharging / blocked at a green
    "green_blocked": "other",  # first in line at a green: yielding or exit road full
    "inside_junction": "other",
    "no_signal_ahead": "other",
}


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
    # Emergency truncation of minimum green for corridor requests (task 3.7); None = use the
    # scenario's signals.json value. Yellow and all-red are never shortened.
    corridor_min_green_s: float | None = None
    # Ordinary vehicles give way (SUMO bluelight device); the ambulance still obeys red lights.
    give_way: bool = False

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
    vehicle_id: str = AMBULANCE_ID  # unique per mission when one run dispatches several

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
        self.stop_reasons: dict[str, int] = {}  # seconds stopped per reason (task 3.7)
        self.speed_mode_at_departure: int | None = None
        # Halting vehicles summed per (tls, approach) over [dispatch, dispatch + 600 s].
        self.approach_queue_sum: dict[tuple[str, str], int] = {}
        self.fixed_window_queue: list[int] = []
        self.stop_log: list[dict] = []  # one row per stopped second
        # Decision 11 check: the signal shown when the ambulance crossed each stop line.
        self.crossings: list[dict] = []
        self._ahead: tuple[str, str, int] | None = None  # (approach edge, tls, link index)

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
        if m.dispatch_s is not None and m.dispatch_s < now <= m.dispatch_s + FIXED_WINDOW_S:
            self.fixed_window_queue.append(sum(e.halting for e in snap.edges.values()))
            for tls, apps in snap.approaches.items():
                for a in apps:
                    k = (tls, a.approach_id)
                    self.approach_queue_sum[k] = self.approach_queue_sum.get(k, 0) + a.queue

        if now == c.dispatch_s and self.mission.status == "PENDING":
            costs = (
                self.graph.free_flow_snapshot(closed)
                if c.routing == "static"
                else self.graph.live_snapshot(snap, closed, self.sim.speed_limits)
            )
            plan = self.mission.dispatch(costs, now)
            if plan is not None:
                t = self.sim.add_ambulance_type(give_way=c.give_way)
                self.sim.add_vehicle(self.vehicle_id, plan.edge_ids, t)
            return

        if self.mission.status != "ACTIVE":
            return
        if self.vehicle_id in snap.arrived_ids:
            self.mission.arrived(now)
            if self.corridor:
                self.corridor.cancel_all(now, step, "arrived")
            return
        amb = snap.tracked.get(self.vehicle_id)
        if amb is None or amb.edge_id == "":  # still waiting to enter the network
            return
        if self.depart_s is None:
            self.depart_s = now - 1.0  # inserted during the previous step
            self.sim.obey_signals(self.vehicle_id)  # again after insertion (devices are built)
            self.speed_mode_at_departure = self.sim.speed_mode(self.vehicle_id)
        self._record_motion(amb, snap)

        plan = self.mission.update(
            amb, self.graph.live_snapshot(snap, closed, self.sim.speed_limits), now, step
        )
        if plan is not None:
            self.sim.set_route(self.vehicle_id, plan.edge_ids)
            if self.corridor:
                self.corridor.on_route_change(plan, now, step)
        if self.mission.status == "NO_ROUTE" and self.corridor:
            self.corridor.cancel_all(now, step, "no_route")
            return
        if self.corridor:
            self.corridor.step(snap, amb, self.mission.plan)

    def _record_motion(self, amb, snap) -> None:
        self._check_crossing(amb, snap)
        if not amb.edge_id.startswith(":") and (not self.driven or self.driven[-1] != amb.edge_id):
            self.driven.append(amb.edge_id)
        moving = amb.speed_mps >= 0.1
        if self._moving and not moving:
            self.stops += 1
        if not moving:
            self.waiting_s += 1.0
            self._classify_stop(amb, snap)
        self._moving = moving

    def _check_crossing(self, amb, snap) -> None:
        """Record the link state in force while the ambulance crossed a signalised stop line.

        States are applied after each step, so the state in force during the step that has
        just run is the one read back in this snapshot (``snap.signal_states``).
        """
        if self._ahead and amb.edge_id != self._ahead[0]:
            edge, tls, link = self._ahead
            state = snap.signal_states.get(tls, "")
            ch = state[link] if link < len(state) else "?"
            self.crossings.append({"time_s": snap.sim_time_s, "tls": tls, "approach": edge,
                                   "link": link, "state": ch})  # fmt: skip
            self._ahead = None
        if not amb.edge_id.startswith(":"):
            ctx = self.sim.stop_context(self.vehicle_id)
            near = ctx["tls"] is not None and ctx["tls_dist_m"] is not None
            # The next light is at the end of this edge (not further along the route).
            e_len = self.network.net.getEdge(amb.edge_id).getLength()
            if near and ctx["tls_dist_m"] <= e_len - amb.position_m + 1.0:
                self._ahead = (amb.edge_id, ctx["tls"], ctx["link"])
            else:
                self._ahead = None

    def _classify_stop(self, amb, snap) -> None:
        """Why the ambulance is standing still this second (diagnostics only, task 3.7)."""
        ctx = {"tls": None, "tls_dist_m": None, "tls_state": None, "leader_gap_m": None}
        if amb.edge_id.startswith(":"):
            reason = "inside_junction"
        else:
            ctx = self.sim.stop_context(self.vehicle_id)
            tls, state = ctx["tls"], ctx["tls_state"]
            dist, gap = ctx["tls_dist_m"], ctx["leader_gap_m"]
            red = state is not None and state in RED_CHARS
            if tls is None:
                reason = "no_signal_ahead"
            elif gap is not None and gap < dist:
                reason = "queue_at_red" if red else "queue_at_green"
            elif not red:
                reason = "green_blocked"
            elif self.corridor is None:
                reason = "red_no_corridor"
            else:
                rs = self.corridor.request_state(tls)
                if rs is None:
                    reason = "red_outside_lookahead"
                elif rs == "REQUESTED":
                    reason = "red_corridor_not_active"
                elif rs == "SAFE_TRANSITION":
                    green = self.safety.mode(tls) == "green"
                    reason = "red_corridor_min_green" if green else "red_corridor_clearance"
                else:
                    reason = "red_corridor_other"
        self.stop_reasons[reason] = self.stop_reasons.get(reason, 0) + 1
        tls = ctx.get("tls")
        self.stop_log.append({
            "time_s": snap.sim_time_s, "edge": amb.edge_id, "reason": reason, "tls": tls,
            "tls_state": ctx.get("tls_state"), "tls_dist_m": _r(ctx.get("tls_dist_m")),
            "leader_gap_m": _r(ctx.get("leader_gap_m")),
            "corridor_state": self.corridor.request_state(tls) if self.corridor and tls else None,
            "filter_mode": self.safety.mode(tls) if tls else None,
        })  # fmt: skip

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
            # Decision 11: stop lines crossed on red (must be 0) and on yellow.
            "amb_signal_crossings": len(self.crossings),
            "amb_red_crossings": sum(c["state"] in "rR" for c in self.crossings),
            "amb_yellow_crossings": sum(c["state"] in "yY" for c in self.crossings),
            # Seconds stopped (after insertion) by reason, and rolled up (task 3.7).
            "amb_stop_reasons": dict(sorted(self.stop_reasons.items())),
            **{f"amb_stopped_{g}_s": sum(v for k, v in self.stop_reasons.items()
                                         if STOP_GROUPS[k] == g)
               for g in sorted(set(STOP_GROUPS.values()))},
            # Network halting vehicles from dispatch to 300 s after arrival (ordinary traffic).
            "mission_window_queue_mean_veh": (
                round(sum(self.window_queue) / len(self.window_queue), 3)
                if self.window_queue else None
            ),
        }  # fmt: skip
        out.update(self._cross_street())
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
                recovery_unfinished=self.corridor.open_recoveries,
            )
        return out

    def _cross_street(self) -> dict:
        """Ordinary-traffic cost on the streets crossing the ambulance's path (task 3.7).

        For every signalised junction the ambulance drove through, the cross-street approaches
        are those with no green link in the phase that serves the ambulance's movement. Their
        halting vehicles are summed over the same 600 s from dispatch in every arm (veh x s, the
        queueing time of cross-street vehicles in that window).
        """
        cross = set()
        for a, b in zip(self.driven, self.driven[1:], strict=False):
            x = self.network.intersections.get(self.network.net.getEdge(a).getToNode().getID())
            if x is None:
                continue
            ph = phase_for(x, a, b)
            if ph is None:
                continue
            state = x.green_phases[ph].state
            for app in x.approaches:
                links = [lk.index for lk in x.links if lk.from_edge == app.edge_id]
                if links and not any(state[i] in "Gg" for i in links):
                    cross.add((x.tls_id, app.edge_id))
        q = self.fixed_window_queue
        return {
            "cross_street_wait_veh_s": sum(self.approach_queue_sum.get(k, 0) for k in cross),
            "cross_street_approaches": len(cross),
            "fixed_window_queue_mean_veh": round(sum(q) / len(q), 3) if q else None,
            "amb_speed_mode": self.speed_mode_at_departure,
        }

    def records(self) -> dict:
        return {
            "config": asdict(self.config),
            "route_versions": [asdict(p) for p in self.mission.plans],
            "routing_log": self.mission.log,
            "corridor_events": self.corridor.events if self.corridor else [],
            "stop_log": self.stop_log,
            "signal_crossings": self.crossings,
        }


def _r(x):
    return round(x, 1) if isinstance(x, float) else x
