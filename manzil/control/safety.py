"""Safety filter: the one path from a controller's request to the signal state (PLAN task 1.5).

Every controller (fixed-time, adaptive, DQN, and later the corridor) only *requests* a green
phase. The filter decides what is shown:

- a requested switch is held until the current green has lasted ``min_green_s`` (FR-08);
- every switch goes green -> yellow (``yellow_s``) -> all-red (``all_red_s``) -> new green;
- requests that arrive during a transition cannot change it;
- unknown phases are rejected.

Each non-trivial request gets an ``AppliedControl`` record (requested vs applied, FR-07). A request
that changes nothing (keep the current phase, or the phase already being switched to) is only
counted, so a controller that asks every second does not flood the log.

Times are simulation seconds. A state set at time ``t`` is shown from ``t`` until the next
change, so a yellow set at ``t`` with ``yellow_s = 3`` is shown for exactly 3 s at 1 s steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from manzil.sim.contracts import AppliedControl, ControlRequest, Owner, SignalEvent, SignalState
from manzil.sim.network import GREEN_CHARS, Intersection, NetworkModel

CORRIDOR_ID = "corridor"  # controller id the corridor coordinator uses for its requests


@dataclass(frozen=True)
class SafetyConfig:
    min_green_s: float = 10.0
    yellow_s: float = 3.0
    all_red_s: float = 2.0

    def __post_init__(self):
        if self.min_green_s <= 0 or self.yellow_s <= 0 or self.all_red_s < 0:
            raise ValueError(f"invalid safety timing {self}")

    @property
    def clearance_s(self) -> float:
        return self.yellow_s + self.all_red_s


class Mode(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ALL_RED = "all_red"


def yellow_state(current: str, target: str) -> str:
    """Links losing green show yellow; links green in both phases keep their green."""
    out = []
    for c, t in zip(current, target, strict=True):
        if c in GREEN_CHARS:
            out.append(c if t in GREEN_CHARS else "y")
        else:
            out.append("r")
    return "".join(out)


def all_red_state(current: str, target: str) -> str:
    """Everything red except links that stay green through the change."""
    return "".join(
        c if (c in GREEN_CHARS and t in GREEN_CHARS) else "r"
        for c, t in zip(current, target, strict=True)
    )


@dataclass
class _Junction:
    x: Intersection
    phase: int  # current green phase, or the phase being left during a transition
    mode: Mode
    since: float  # time the current mode started
    target: int | None = None
    state: str = ""
    owner: Owner = Owner.NORMAL


@dataclass
class SafetyFilter:
    network: NetworkModel
    config: SafetyConfig = field(default_factory=SafetyConfig)
    applied: list[AppliedControl] = field(default_factory=list)
    events: list[SignalEvent] = field(default_factory=list)
    hold_count: int = 0
    owner_held: int = 0  # normal-controller requests ignored while the corridor owns a junction
    _j: dict[str, _Junction] = field(default_factory=dict, repr=False)
    _next_request_id: int = 0

    def reset(self, initial_phases: dict[str, int] | None = None, now: float = 0.0, step: int = 0):
        """Start every junction in a green phase (phase 0 unless given). Returns states to show."""
        initial_phases = initial_phases or {}
        self._j.clear()
        self.applied.clear()
        self.events.clear()
        self.hold_count = 0
        self.owner_held = 0
        for tls, x in self.network.intersections.items():
            phase = initial_phases.get(tls, 0)
            if not 0 <= phase < len(x.green_phases):
                raise ValueError(f"{tls}: invalid initial phase {phase}")
            j = _Junction(x, phase, Mode.GREEN, now, state=x.green_phases[phase].state)
            self._j[tls] = j
            self._event(j, step, now, Mode.GREEN, phase)
        return self.states()

    # ----- requests --------------------------------------------------------------------------
    def submit(self, req: ControlRequest, now: float, step: int) -> AppliedControl | None:
        j = self._j[req.intersection_id]
        is_corridor = req.controller_id == CORRIDOR_ID
        if is_corridor != (j.owner is Owner.CORRIDOR):
            if is_corridor:
                raise PermissionError(f"{j.x.tls_id}: corridor request without ownership")
            self.owner_held += 1  # the corridor owns this junction: normal control waits
            return None
        rid = self._next_request_id
        self._next_request_id += 1
        n_phases = len(j.x.green_phases)

        if not 0 <= req.requested_phase < n_phases:
            return self._record(rid, req, j.phase if j.mode is Mode.GREEN else j.target, step,
                                "invalid_phase")  # fmt: skip
        if j.mode is not Mode.GREEN:
            if req.requested_phase == j.target:  # already on its way: nothing to change
                self.hold_count += 1
                return None
            return self._record(rid, req, j.target, step, "in_transition")
        if req.requested_phase == j.phase:
            self.hold_count += 1
            return None
        if now - j.since < self.config.min_green_s:
            return self._record(rid, req, j.phase, step, "min_green_hold")

        # Start the change: yellow now, then all-red, then the requested green.
        target = j.x.green_phases[req.requested_phase].state
        j.target = req.requested_phase
        j.mode = Mode.YELLOW
        j.since = now
        j.state = yellow_state(j.state, target)
        self._event(j, step, now, Mode.YELLOW, None)
        return self._record(rid, req, req.requested_phase, step, "none")

    # ----- time ------------------------------------------------------------------------------
    def tick(self, now: float, step: int) -> dict[str, str]:
        """Advance yellow / all-red transitions whose time is up. Returns states to show."""
        for j in self._j.values():
            if j.mode is Mode.YELLOW and now - j.since >= self.config.yellow_s:
                target = j.x.green_phases[j.target].state
                if self.config.all_red_s > 0:
                    j.mode, j.since = Mode.ALL_RED, now
                    j.state = all_red_state(j.state, target)
                    self._event(j, step, now, Mode.ALL_RED, None)
                else:
                    self._enter_green(j, now, step)
            elif j.mode is Mode.ALL_RED and now - j.since >= self.config.all_red_s:
                self._enter_green(j, now, step)
        return self.states()

    def states(self) -> dict[str, str]:
        return {tls: j.state for tls, j in self._j.items()}

    def signal_state(self, tls: str, now: float) -> SignalState:
        j = self._j[tls]
        green = j.mode is Mode.GREEN
        legal = tuple(range(len(j.x.green_phases))) if green else (j.target,)
        return SignalState(
            intersection_id=tls,
            program_id="manzil",
            phase_id=j.phase if green else None,
            phase_elapsed_s=now - j.since,
            state=j.state,
            legal_next=legal,
            owner=j.owner,
            in_transition=not green,
        )

    def set_owner(self, tls: str, owner: Owner, now: float, step: int) -> None:
        """Hand a junction to the corridor or back to normal control. Safety rules (minimum
        green, yellow, all-red) apply to every owner, so the hand-over itself is always safe."""
        j = self._j[tls]
        if j.owner is owner:
            return
        j.owner = owner
        self.events.append(
            SignalEvent(step, now, tls, f"owner_{owner.value.lower()}", j.phase, j.state, owner)
        )

    def owner(self, tls: str) -> Owner:
        return self._j[tls].owner

    def showing(self, tls: str) -> int | None:
        """Green phase currently shown, or None during yellow / all-red."""
        j = self._j[tls]
        return j.phase if j.mode is Mode.GREEN else None

    def can_switch(self, tls: str, now: float) -> bool:
        j = self._j[tls]
        return j.mode is Mode.GREEN and now - j.since >= self.config.min_green_s

    # ----- internals -------------------------------------------------------------------------
    def _enter_green(self, j: _Junction, now: float, step: int) -> None:
        j.phase, j.target = j.target, None
        j.mode, j.since = Mode.GREEN, now
        j.state = j.x.green_phases[j.phase].state
        self._event(j, step, now, Mode.GREEN, j.phase)

    def _event(self, j: _Junction, step: int, now: float, mode: Mode, phase: int | None):
        self.events.append(SignalEvent(step, now, j.x.tls_id, mode.value, phase, j.state, j.owner))

    def _record(self, rid, req: ControlRequest, applied, step, intervention) -> AppliedControl:
        rec = AppliedControl(
            request_id=rid,
            controller_id=req.controller_id,
            intersection_id=req.intersection_id,
            requested_phase=req.requested_phase,
            applied_phase=applied,
            effective_step=step,
            safety_intervention=intervention,
            reason=req.reason,
        )
        self.applied.append(rec)
        return rec


@dataclass
class SafetyMonitor:
    """Independent checker of the states actually shown (used by tests and every run).

    Checks, per junction and step: no conflicting greens (exact foe/yield rule), every green
    state is one of the declared green phases or a filter transition, a link that loses green
    shows yellow for at least ``yellow_s`` first, and each green phase lasts at least
    ``min_green_s`` before it is left.
    """

    network: NetworkModel
    config: SafetyConfig
    violations: list[str] = field(default_factory=list)
    _prev: dict[str, str] = field(default_factory=dict)
    _yellow_since: dict[tuple[str, int], float] = field(default_factory=dict)
    _green_since: dict[str, tuple[str, float]] = field(default_factory=dict)

    def observe(self, now: float, states: dict[str, str]) -> None:
        eps = 1e-9
        for tls, state in states.items():
            x = self.network.intersections[tls]
            for a, b in x.conflicts_in(state):
                self.violations.append(f"t={now} {tls}: conflicting greens {a},{b} in {state}")
            greens = {g.state for g in x.green_phases}
            if "y" not in state and any(c in GREEN_CHARS for c in state):
                if state not in greens and not any(_subset(state, g) for g in greens):
                    self.violations.append(f"t={now} {tls}: undeclared green state {state}")

            prev = self._prev.get(tls)
            if prev is not None and prev != state:
                for i, (p, c) in enumerate(zip(prev, state, strict=True)):
                    if p in GREEN_CHARS and c == "r":
                        self.violations.append(f"t={now} {tls}: link {i} green->red without yellow")
                    if p == "y" and c != "y":
                        since = self._yellow_since.pop((tls, i), now)
                        if c == "r" and now - since < self.config.yellow_s - eps:
                            self.violations.append(f"t={now} {tls}: link {i} yellow too short")
                    if c == "y" and p != "y":
                        self._yellow_since[(tls, i)] = now
                # Minimum green: a declared green that is replaced must have lasted long enough.
                g = self._green_since.get(tls)
                if g and g[0] == prev and now - g[1] < self.config.min_green_s - eps:
                    self.violations.append(f"t={now} {tls}: green {prev} left after {now - g[1]}s")
            if state in greens and (self._green_since.get(tls, ("",))[0] != state):
                self._green_since[tls] = (state, now)
            self._prev[tls] = state


def _subset(state: str, green: str) -> bool:
    """True if every green link in ``state`` is also green in ``green`` (an all-red hold)."""
    return all(c not in GREEN_CHARS or g in GREEN_CHARS for c, g in zip(state, green, strict=True))
