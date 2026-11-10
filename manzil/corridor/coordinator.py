"""Moving green corridor: D2 Algorithm 2 / Fig 6.6 (PLAN task 3.5).

Only a bounded look-ahead set of signalised junctions ahead of the ambulance takes part (FR-12).
Per junction the state runs::

    IDLE -> REQUESTED -> SAFE_TRANSITION -> ACTIVE_PRIORITY -> PASSAGE -> RECOVERY -> IDLE
                 \\______________ CANCELLED (route change, NO_ROUTE, timeout) ______/

- REQUESTED: the junction is among the next ``lookahead`` signalised junctions on the route.
- Activation when the ambulance's free-flow ETA to the stop line is within ``activate_eta_s``
  plus the time to clear the queue on its approach. The coordinator then owns the junction and
  requests the green phase that serves the ambulance's movement. The safety filter still
  finishes minimum green and applies yellow + all-red (SAFE_TRANSITION).
- ACTIVE_PRIORITY: the ambulance's phase is shown; it is held for at most ``max_priority_s``.
- PASSAGE: the ambulance has left the approach edge. Ownership returns to normal control at once
  (the safety filter guarantees a legal phase boundary) and the junction enters RECOVERY.
- RECOVERY ends when the junction's approach queue is back to its typical level: the larger of
  its value at activation and its mean over the ``baseline_s`` before activation (or after
  ``recovery_cap_s``). That duration is the recovery time; recoveries still open when the run
  ends are reported separately, not dropped.
- A route revision cancels requests for junctions no longer on the route before new ones are
  made (FR-14); NO_ROUTE or a timeout cancels and releases safely (FR-13).

The coordinator never actuates SUMO: it only sets ownership and submits requests to the filter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from manzil.control.safety import CORRIDOR_ID, SafetyFilter
from manzil.routing.graph import RoutePlan, RoutingGraph
from manzil.sim.contracts import ControlRequest, Owner, TrafficSnapshot, VehicleState
from manzil.sim.network import NetworkModel


@dataclass(frozen=True)
class CorridorParams:
    lookahead: int = 2  # signalised junctions ahead that may hold a request
    activate_eta_s: float = 15.0  # activate when ETA <= this + queue clearance time
    headway_s: float = 2.0  # queue discharge per halting vehicle per lane
    max_priority_s: float = 60.0  # longest a junction may be held for the ambulance
    recovery_cap_s: float = 300.0
    baseline_s: int = 120  # window for a junction's typical queue before activation


@dataclass
class _Request:
    tls: str
    approach: str  # edge the ambulance arrives on
    exit: str  # edge it leaves on
    phase: int  # green phase serving that movement
    route_version: int
    state: str = "REQUESTED"
    created_s: float = 0.0
    activated_s: float | None = None
    served_s: float | None = None
    passed_s: float | None = None
    queue_at_activation: float = 0.0


@dataclass
class CorridorCoordinator:
    network: NetworkModel
    graph: RoutingGraph
    safety: SafetyFilter
    params: CorridorParams = field(default_factory=CorridorParams)
    mission_id: str = "m1"
    events: list[dict] = field(default_factory=list)
    recovery_times_s: list[float] = field(default_factory=list)
    _active: dict[str, _Request] = field(default_factory=dict)  # tls -> request
    _recovering: dict[str, tuple[float, float]] = field(default_factory=dict)
    _history: dict[str, list[int]] = field(default_factory=dict)  # recent queue per junction

    # ----- per step --------------------------------------------------------------------------
    def step(self, snap: TrafficSnapshot, amb: VehicleState | None, plan: RoutePlan | None):
        now, step = snap.sim_time_s, snap.effective_step
        for tls in self.network.intersections:
            h = self._history.setdefault(tls, [])
            h.append(_queue(snap, tls))
            if len(h) > self.params.baseline_s:
                del h[0]
        self._track_recovery(snap)
        if plan is None or amb is None:
            return
        upcoming = self._upcoming(plan, amb)
        wanted = {tls for tls, *_ in upcoming[: self.params.lookahead]}

        # Passage: the ambulance is no longer on (or before) the approach edge.
        for tls, req in list(self._active.items()):
            if self._passed(req, plan, amb):
                req.passed_s = now
                self._release(req, now, step, "PASSAGE", snap)
            elif tls not in wanted and req.state == "REQUESTED":
                self._cancel(req, now, step, "out_of_lookahead")

        for tls, approach, exit_, phase, eta in upcoming[: self.params.lookahead]:
            req = self._active.get(tls)
            if req is None:
                req = _Request(tls, approach, exit_, phase, plan.route_version, created_s=now)
                self._active[tls] = req
                self._event(now, step, req, "REQUESTED", eta=eta)
            if req.state == "REQUESTED" and eta <= self._activation_eta(snap, tls, approach):
                req.state, req.activated_s = "SAFE_TRANSITION", now
                h = self._history.get(tls) or [0]
                req.queue_at_activation = max(_queue(snap, tls), sum(h) / len(h))
                self.safety.set_owner(tls, Owner.CORRIDOR, now, step)
                self._event(now, step, req, "SAFE_TRANSITION", eta=eta)
            if req.state in ("SAFE_TRANSITION", "ACTIVE_PRIORITY"):
                held_for = now - req.activated_s
                if held_for > self.params.max_priority_s:
                    self._cancel(req, now, step, "timeout")
                    continue
                why = f"corridor {self.mission_id} v{req.route_version} eta={eta:.0f}s"
                self.safety.submit(
                    ControlRequest(CORRIDOR_ID, tls, req.phase, step, why), now, step
                )
                if req.state == "SAFE_TRANSITION" and self.safety.showing(tls) == req.phase:
                    req.state, req.served_s = "ACTIVE_PRIORITY", now
                    self._event(now, step, req, "ACTIVE_PRIORITY", eta=eta)

    def on_route_change(self, plan: RoutePlan, now: float, step: int) -> None:
        """FR-14: cancel requests that the new route version no longer justifies."""
        for req in list(self._active.values()):
            on_route = any(
                a == req.approach and b == req.exit
                for a, b in zip(plan.edge_ids, plan.edge_ids[1:], strict=False)
            )
            if not on_route:
                self._cancel(req, now, step, f"route_v{plan.route_version}")
            else:
                req.route_version = plan.route_version

    def cancel_all(self, now: float, step: int, reason: str) -> None:
        for req in list(self._active.values()):
            self._cancel(req, now, step, reason)

    # ----- internals -------------------------------------------------------------------------
    def _upcoming(self, plan: RoutePlan, amb: VehicleState):
        """Signalised junctions still ahead: (tls, approach, exit, phase, free-flow ETA).

        SUMO's route index points at the current edge of the route it was given, which is always
        ``plan.edge_ids``. Inside a junction (edge id starting with ':') the index still points at
        the edge just left, whose junction has therefore been passed.
        """
        edges = plan.edge_ids
        inside = amb.edge_id.startswith(":")
        start = amb.route_index + 1 if inside else amb.route_index
        if inside:
            eta = 0.0
        else:
            e = self.network.net.getEdge(amb.edge_id)
            eta = max(e.getLength() - amb.position_m, 0.0) / e.getSpeed()
        out = []
        for i in range(start, len(edges) - 1):
            a, b = edges[i], edges[i + 1]
            if i > start or inside:
                eta += self.graph.free_flow_s[a]
            x = self.network.intersections.get(self.network.net.getEdge(a).getToNode().getID())
            if x is None:
                continue
            phase = _phase_for(x, a, b)
            if phase is not None:
                out.append((x.tls_id, a, b, phase, eta))
        return out

    def _activation_eta(self, snap: TrafficSnapshot, tls: str, approach: str) -> float:
        e = snap.edges.get(approach)
        lanes = self.graph.lanes.get(approach, 1)
        queue_clear = (e.halting * self.params.headway_s / lanes) if e else 0.0
        return self.params.activate_eta_s + queue_clear

    def _passed(self, req: _Request, plan: RoutePlan, amb: VehicleState) -> bool:
        """The ambulance crossed the stop line: it is past the approach edge on its route."""
        edges = plan.edge_ids
        if req.approach not in edges:
            return False
        ai = edges.index(req.approach)
        return amb.route_index > ai or (amb.route_index == ai and amb.edge_id.startswith(":"))

    def _release(self, req: _Request, now, step, state, snap) -> None:
        self._event(now, step, req, state)
        self._active.pop(req.tls, None)
        if self.safety.owner(req.tls) is Owner.CORRIDOR:
            self.safety.set_owner(req.tls, Owner.NORMAL, now, step)
            self._recovering[req.tls] = (now, req.queue_at_activation)
            self._event(now, step, req, "RECOVERY")

    def _cancel(self, req: _Request, now, step, reason) -> None:
        self._event(now, step, req, "CANCELLED", reason=reason)
        self._active.pop(req.tls, None)
        if self.safety.owner(req.tls) is Owner.CORRIDOR:
            self.safety.set_owner(req.tls, Owner.NORMAL, now, step)
            self._recovering[req.tls] = (now, req.queue_at_activation)

    @property
    def open_recoveries(self) -> int:
        return len(self._recovering)

    def _track_recovery(self, snap: TrafficSnapshot) -> None:
        for tls, (start, q0) in list(self._recovering.items()):
            done = _queue(snap, tls) <= q0 or snap.sim_time_s - start >= self.params.recovery_cap_s
            if done:
                self.recovery_times_s.append(snap.sim_time_s - start)
                self.events.append({"time_s": snap.sim_time_s, "tls": tls, "state": "IDLE",
                                    "recovery_s": snap.sim_time_s - start})  # fmt: skip
                del self._recovering[tls]

    def _event(self, now, step, req: _Request, state, **extra) -> None:
        if state not in ("RECOVERY",):
            req.state = state if state != "PASSAGE" else req.state
        self.events.append({"time_s": now, "step": step, "tls": req.tls, "state": state,
                            "route_version": req.route_version, "phase": req.phase,
                            **{k: (round(v, 1) if isinstance(v, float) else v)
                               for k, v in extra.items()}})  # fmt: skip


def _phase_for(x, approach: str, exit_: str) -> int | None:
    """Green phase giving the movement approach -> exit a priority green ('G') if possible."""
    links = [lk.index for lk in x.links if lk.from_edge == approach and lk.to_edge == exit_]
    if not links:
        return None
    best = None
    for g in x.green_phases:
        chars = [g.state[i] for i in links]
        if all(c == "G" for c in chars):
            return g.index
        if best is None and any(c in "Gg" for c in chars):
            best = g.index
    return best


def _queue(snap: TrafficSnapshot, tls: str) -> int:
    return sum(a.queue for a in snap.approaches.get(tls, ()))
