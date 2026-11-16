"""Moving green corridor: D2 Algorithm 2 / Fig 6.6 (PLAN task 3.5).

Only a bounded look-ahead set of signalised junctions ahead of the ambulance takes part (FR-12).
Per junction the state runs::

    IDLE -> REQUESTED -> SAFE_TRANSITION -> ACTIVE_PRIORITY -> PASSAGE -> RECOVERY -> IDLE
                 \\______________ CANCELLED (route change, NO_ROUTE, timeout) ______/

- REQUESTED: the junction is among the next ``lookahead`` signalised junctions on the route.
- Activation when the ambulance's free-flow ETA to the stop line is within ``activate_eta_s``
  plus the time to clear the queue on its approach. The coordinator then owns the junction and
  requests the green phase that serves the ambulance's movement. The safety filter still
  finishes minimum green and applies yellow + all-red (SAFE_TRANSITION). Since task 3.7 the
  minimum green a corridor request must wait for is ``corridor_min_green_s`` (5 s on the grid,
  emergency truncation); yellow and all-red are never shortened.
- ACTIVE_PRIORITY: the ambulance's phase is shown; it is held for at most ``max_priority_s``.
- PASSAGE: the ambulance has left the approach edge. Ownership returns to normal control at once
  (the safety filter guarantees a legal phase boundary) and the junction enters RECOVERY.
- RECOVERY ends when the junction's approach queue is back to its typical level: the larger of
  its value at activation and its mean over the ``baseline_s`` before activation (or after
  ``recovery_cap_s``). That duration is the recovery time; recoveries still open when the run
  ends are reported separately, not dropped.
- A route revision cancels requests for junctions no longer on the route before new ones are
  made (FR-14); NO_ROUTE or a timeout cancels and releases safely (FR-13).

Additions from workstream W4 (all off by default; see ``results/fyp2/corridor/``):

- Downstream-capacity check (``downstream``). The exit edge of the ambulance's movement is
  *blocked* when its vehicles fill at least ``downstream_occupancy`` of its storage
  (lanes x length / ``vehicle_space_m``) and some of them are halting. ``"defer"``: a due
  activation waits while the exit is blocked (green would only serve a movement that cannot
  move), for at most ``downstream_max_defer_s``. ``"flush"``: the next signalised junction at
  the end of that blocked exit is activated at once (it may be one beyond the look-ahead), so
  the exit drains before the ambulance arrives. ``"both"`` does both.
- Bounded compensation in recovery (``compensation``). After confirmed passage (not after a
  cancellation or timeout, when the ambulance may still need the junction) the coordinator
  keeps ownership and serves the phase with the longest
  queue among the phases the ambulance's phase denied, for as long as the junction was held
  (at most ``compensation_max_s``) and only after a full normal minimum green (no truncation),
  then hands the junction back to normal control. Recovery time is still measured from passage.
  ``compensation_start="exit_clear"`` hands the junction to normal control at passage and takes
  it back for compensation only once the ambulance has left its exit edge.

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
    downstream: str = "off"  # "off", "defer", "flush", "both" (W4)
    downstream_occupancy: float = 0.75  # exit blocked at this share of its storage
    downstream_max_defer_s: float = 20.0
    vehicle_space_m: float = 7.5  # storage per vehicle (5 m car + 2.5 m gap)
    compensation: bool = False  # W4: bounded compensation plan in recovery
    compensation_max_s: float = 20.0
    # "passage": compensate at once; "exit_clear": normal control first, compensation only once
    # the ambulance has left its exit edge (released traffic cannot queue in front of it).
    compensation_start: str = "passage"

    def __post_init__(self):
        if self.downstream not in ("off", "defer", "flush", "both"):
            raise ValueError(f"unknown downstream mode {self.downstream!r}")
        if not 0 < self.downstream_occupancy <= 1:
            raise ValueError("downstream occupancy must be in (0, 1]")
        if self.compensation_start not in ("passage", "exit_clear"):
            raise ValueError(f"unknown compensation start {self.compensation_start!r}")
        if self.compensation_max_s <= 0 or self.downstream_max_defer_s < 0:
            raise ValueError("compensation and defer limits must be positive")


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
    deferred_s: float | None = None  # first time a due activation waited for the exit (W4)
    flush: bool = False  # activated early to drain a blocked exit upstream (W4)


@dataclass
class _Compensation:
    tls: str
    phase: int  # phase served in compensation
    green_s: float  # how long it is served
    started_s: float
    green_since: float | None = None


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
    _last_edge: str = ""  # last normal (non-junction) edge the ambulance was on
    _compensating: dict[str, _Compensation] = field(default_factory=dict)
    compensation_green_s: list[float] = field(default_factory=list)  # served per plan
    deferrals: int = 0
    flushes: int = 0
    _snap: TrafficSnapshot | None = None
    _pending_comp: dict[str, tuple[_Request, float]] = field(default_factory=dict)

    # ----- per step --------------------------------------------------------------------------
    def step(self, snap: TrafficSnapshot, amb: VehicleState | None, plan: RoutePlan | None):
        now, step = snap.sim_time_s, snap.effective_step
        self._snap = snap
        for tls in self.network.intersections:
            h = self._history.setdefault(tls, [])
            h.append(_queue(snap, tls))
            if len(h) > self.params.baseline_s:
                del h[0]
        self._track_recovery(snap)
        self._compensate(snap)
        self._start_pending(snap, amb, plan)
        if plan is None or amb is None:
            return
        if not amb.edge_id.startswith(":"):
            self._last_edge = amb.edge_id
        upcoming = self._upcoming(plan, amb)
        flush = self._flush_targets(snap, upcoming)
        considered = upcoming[: self.params.lookahead] + [
            u
            for u in upcoming[self.params.lookahead : self.params.lookahead + 1]
            if u[0] in flush or u[0] in self._active
        ]  # once requested there, a junction stays in the set until passage or timeout
        wanted = {tls for tls, *_ in considered}

        # Passage: the ambulance is no longer on (or before) the approach edge.
        for tls, req in list(self._active.items()):
            if self._passed(req, plan, amb):
                req.passed_s = now
                self._release(req, now, step, "PASSAGE", snap)
            elif tls not in wanted and req.state == "REQUESTED":
                self._cancel(req, now, step, "out_of_lookahead")

        for tls, approach, exit_, phase, eta in considered:
            if tls in self._compensating:  # route revisited a junction still compensating
                continue
            req = self._active.get(tls)
            if req is None:
                req = _Request(tls, approach, exit_, phase, plan.route_version, created_s=now)
                self._active[tls] = req
                self._event(now, step, req, "REQUESTED", eta=eta)
            due = eta <= self._activation_eta(snap, tls, approach)
            if req.state == "REQUESTED" and tls in flush:  # activated because of the exit
                due, req.flush = True, True
                self.flushes += 1
                self._event(now, step, req, "DOWNSTREAM_FLUSH", eta=eta)
            if req.state == "REQUESTED" and due and self._defer(req, snap, now, step, eta):
                continue
            if req.state == "REQUESTED" and due:
                req.state, req.activated_s = "SAFE_TRANSITION", now
                h = self._history.get(tls) or [0]
                req.queue_at_activation = max(_queue(snap, tls), sum(h) / len(h))
                self.safety.set_owner(tls, Owner.CORRIDOR, now, step)
                self._event(now, step, req, "SAFE_TRANSITION", eta=eta)
            if req.state in ("SAFE_TRANSITION", "ACTIVE_PRIORITY"):
                held_for = now - req.activated_s
                if held_for > self.params.max_priority_s:
                    self._cancel(req, now, step, "timeout", snap)
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

    # ----- W4: downstream check and compensation ---------------------------------------------
    def exit_blocked(self, snap: TrafficSnapshot, exit_: str) -> bool:
        """The exit edge is (nearly) full of vehicles and some of them are halting."""
        e = snap.edges.get(exit_)
        if e is None:
            return False
        edge = self.network.net.getEdge(exit_)
        storage = edge.getLaneNumber() * edge.getLength() / self.params.vehicle_space_m
        return e.halting > 0 and e.vehicles >= self.params.downstream_occupancy * storage

    def _defer(self, req: _Request, snap, now, step, eta) -> bool:
        if self.params.downstream not in ("defer", "both") or req.flush:
            return False
        if not self.exit_blocked(snap, req.exit):
            return False
        if req.deferred_s is None:
            req.deferred_s = now
            self.deferrals += 1
            self._event(now, step, req, "DOWNSTREAM_DEFER", eta=eta)
        return now - req.deferred_s < self.params.downstream_max_defer_s

    def _flush_targets(self, snap: TrafficSnapshot, upcoming) -> set[str]:
        """Junctions to activate early because the ambulance's exit before them is blocked."""
        if self.params.downstream not in ("flush", "both"):
            return set()
        out = set()
        la = self.params.lookahead
        for (tls, approach, exit_, _ph, eta), nxt in zip(upcoming[:la], upcoming[1 : la + 1],
                                                          strict=False):  # fmt: skip
            # Only when this junction is (nearly) due, and the next one sits at that exit.
            soon = eta <= self._activation_eta(snap, tls, approach) + self.params.activate_eta_s
            if soon and nxt[1] == exit_ and self.exit_blocked(snap, exit_):
                out.add(nxt[0])
        return out

    def _start_pending(self, snap, amb, plan) -> None:
        """``exit_clear``: take the junction back for compensation once the ambulance is off its
        exit edge (or has arrived); give up after ``max_priority_s``."""
        now, step = snap.sim_time_s, snap.effective_step
        for tls, (req, passed_s) in list(self._pending_comp.items()):
            if now - passed_s > self.params.max_priority_s:
                del self._pending_comp[tls]
                continue
            if amb is not None and plan is not None and req.exit in plan.edge_ids:
                idx = self._plan_index(plan, amb)
                ei = plan.edge_ids.index(req.exit)
                if idx < ei or (idx == ei and not amb.edge_id.startswith(":")):
                    continue  # still before or on the exit edge
            del self._pending_comp[tls]
            if self.safety.owner(tls) is not Owner.NORMAL:
                continue
            self.safety.set_owner(tls, Owner.CORRIDOR, now, step)
            if not self._start_compensation(req, now, step, snap, held=passed_s - req.activated_s):
                self.safety.set_owner(tls, Owner.NORMAL, now, step)

    def _start_compensation(self, req: _Request, now: float, step: int, snap, held=None) -> bool:
        """Keep ownership and serve the most-queued phase the priority denied (bounded)."""
        if not self.params.compensation or req.activated_s is None:
            return False
        x = self.network.intersections[req.tls]
        amb_state = x.green_phases[req.phase].state
        best, best_q = None, 0
        snap = snap or self._snap
        queues = {a.approach_id: a.queue for a in snap.approaches.get(req.tls, ())} if snap else {}
        for g in x.green_phases:
            if g.index == req.phase:
                continue
            gained = {lk.from_edge for lk in x.links
                      if g.state[lk.index] in "Gg" and amb_state[lk.index] not in "Gg"}  # fmt: skip
            q = sum(queues.get(e, 0) for e in gained)
            if q > best_q:
                best, best_q = g.index, q
        if best is None:  # nobody is waiting for another phase: plain release
            return False
        held = now - req.activated_s if held is None else held
        green = min(max(held, self.safety.config.min_green_s), self.params.compensation_max_s)
        self._compensating[req.tls] = _Compensation(req.tls, best, green, now)
        self.events.append({"time_s": now, "step": step, "tls": req.tls,
                            "state": "COMPENSATION", "phase": best,
                            "green_s": round(green, 1), "queue": best_q})  # fmt: skip
        return True

    def _compensate(self, snap: TrafficSnapshot) -> None:
        now, step = snap.sim_time_s, snap.effective_step
        for tls, c in list(self._compensating.items()):
            showing = self.safety.showing(tls)
            if showing == c.phase and c.green_since is None:
                c.green_since = now
            # Green shown so far (the filter's own clock: the phase began at its last tick).
            served = (
                self.safety.signal_state(tls, now).phase_elapsed_s if showing == c.phase else 0.0
            )
            # Hard cap: the served green plus time to finish min green and clearance.
            cap = c.green_s + self.safety.config.min_green_s + self.safety.config.clearance_s
            if served >= c.green_s or now - c.started_s >= cap:
                del self._compensating[tls]
                self.compensation_green_s.append(served)
                self.safety.set_owner(tls, Owner.NORMAL, now, step)
                self.events.append({"time_s": now, "step": step, "tls": tls,
                                    "state": "COMPENSATION_DONE", "served_s": served})  # fmt: skip
                continue
            if showing != c.phase and self.safety.can_switch(tls, now):  # full min green
                self.safety.submit(
                    ControlRequest(CORRIDOR_ID, tls, c.phase, step, "corridor compensation"),
                    now, step,
                )  # fmt: skip

    @property
    def compensating(self) -> int:
        return len(self._compensating)

    # ----- internals -------------------------------------------------------------------------
    def _plan_index(self, plan: RoutePlan, amb: VehicleState) -> int:
        """Position of the ambulance's current (or, inside a junction, last) edge in the plan.

        SUMO's own route index cannot be used: after ``setRoute`` SUMO keeps the edges already
        driven at the front of the vehicle's route, while ``plan.edge_ids`` starts at the edge
        the ambulance was on when the route was revised (task 3.7 bug fix). Routes never repeat
        an edge, so the edge itself identifies the position.
        """
        edge = self._last_edge if amb.edge_id.startswith(":") else amb.edge_id
        edges = plan.edge_ids
        return edges.index(edge) if edge in edges else 0

    def _upcoming(self, plan: RoutePlan, amb: VehicleState):
        """Signalised junctions still ahead: (tls, approach, exit, phase, free-flow ETA).

        Inside a junction (edge id starting with ':') the last normal edge's junction is the
        one being crossed, so it has been passed.
        """
        edges = plan.edge_ids
        inside = amb.edge_id.startswith(":")
        idx = self._plan_index(plan, amb)
        start = idx + 1 if inside else idx
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
            phase = phase_for(x, a, b)
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
        idx = self._plan_index(plan, amb)
        return idx > ai or (idx == ai and amb.edge_id.startswith(":"))

    def _release(self, req: _Request, now, step, state, snap) -> None:
        self._event(now, step, req, state)
        self._active.pop(req.tls, None)
        if self.safety.owner(req.tls) is Owner.CORRIDOR:
            later = self.params.compensation and self.params.compensation_start == "exit_clear"
            if later and req.activated_s is not None:
                self._pending_comp[req.tls] = (req, now)
            if later or not self._start_compensation(req, now, step, snap):
                self.safety.set_owner(req.tls, Owner.NORMAL, now, step)
            self._recovering[req.tls] = (now, req.queue_at_activation)
            self._event(now, step, req, "RECOVERY")

    def _cancel(self, req: _Request, now, step, reason, snap=None) -> None:
        # No compensation after a cancellation: the ambulance may still have to cross this
        # junction (e.g. after a timeout), and a compensating junction is not served for it.
        self._event(now, step, req, "CANCELLED", reason=reason)
        self._active.pop(req.tls, None)
        if self.safety.owner(req.tls) is Owner.CORRIDOR:
            self.safety.set_owner(req.tls, Owner.NORMAL, now, step)
            self._recovering[req.tls] = (now, req.queue_at_activation)

    def status(self) -> dict[str, str]:
        """Current corridor state per junction that takes part (for display only)."""
        out = {tls: "RECOVERY" for tls in self._recovering}
        out.update({tls: "COMPENSATION" for tls in self._compensating})
        out.update({tls: req.state for tls, req in self._active.items()})
        return out

    def request_state(self, tls: str) -> str | None:
        """State of the open request for this junction, or None (read-only, diagnostics)."""
        req = self._active.get(tls)
        return req.state if req else None

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


def phase_for(x, approach: str, exit_: str) -> int | None:
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
