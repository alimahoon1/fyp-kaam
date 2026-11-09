"""Rule-based adaptive (pressure) controller, D2 section 5.4.2 / Eq 5.2 (PLAN task 2.1).

Score of a legal green phase ``p`` at time ``t``::

    S_p(t) = sum over served lanes (q_l - alpha * q_m)  +  beta * w_p

- ``q_l``: halting vehicles on each incoming lane the phase serves (each lane counted once,
  even if it feeds several movements, so shared lanes are not double counted);
- ``q_m``: halting vehicles on each outgoing lane the phase feeds (each counted once);
- ``w_p``: the largest accumulated waiting time (vehicle-seconds, SUMO lane waiting time summed
  per approach) among the approaches the phase serves: the anti-starvation term.

Decision rules, every step:

1. During yellow / all-red, or before the minimum green (or the longer ``min_hold_s``): no
   request, so the filter keeps the phase.
2. **Max-red promotion:** if another phase has been red for at least ``max_red_s`` minus the
   clearance, request the longest-waiting one (reason ``max_red``).
3. **Max green:** if the current green has reached ``max_green_s``, request the best other
   phase (reason ``max_green``).
4. Otherwise request the best-scoring phase; the current phase is kept unless another one
   scores more than ``switch_margin`` above it (reason ``pressure``).

Every request carries its scores in ``reason`` so a reviewer can tell whether a switch came from
pressure, fairness promotion or max green. The controller never actuates SUMO.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from manzil.control.safety import SafetyConfig
from manzil.sim.contracts import ControlRequest, SignalState, TrafficSnapshot
from manzil.sim.network import NetworkModel


@dataclass(frozen=True)
class AdaptiveParams:
    alpha: float = 1.0
    beta: float = 0.01
    max_green_s: float = 60.0
    max_red_s: float = 90.0
    switch_margin: float = 0.0
    # Shortest green the controller itself chooses before it considers switching. 0 means the
    # safety filter's minimum green. Longer holds lose less time in yellow / all-red.
    min_hold_s: float = 0.0

    def __post_init__(self):
        if min(self.alpha, self.beta, self.switch_margin, self.min_hold_s) < 0:
            raise ValueError("alpha, beta, switch_margin and min_hold_s must be >= 0")


@dataclass(frozen=True)
class _PhaseLanes:
    in_lanes: tuple[str, ...]
    out_lanes: tuple[str, ...]
    approaches: frozenset[str]


@dataclass
class AdaptiveController:
    params: AdaptiveParams = field(default_factory=AdaptiveParams)
    controller_id: str = "adaptive"
    decisions: dict[str, int] = field(default_factory=dict)
    _phases: dict[str, tuple[_PhaseLanes, ...]] = field(default_factory=dict, repr=False)
    _last_green: dict[str, list[float]] = field(default_factory=dict, repr=False)
    _safety: SafetyConfig | None = field(default=None, repr=False)

    def reset(self, network: NetworkModel, safety: SafetyConfig) -> dict[str, int]:
        if self.params.max_green_s < max(safety.min_green_s, self.params.min_hold_s):
            raise ValueError("max green must be at least the minimum green and the minimum hold")
        if self.params.max_red_s <= safety.clearance_s:
            raise ValueError("max red must be longer than the clearance time")
        self._safety = safety
        self.decisions = {}
        self._phases = {}
        self._last_green = {}
        for tls, x in network.intersections.items():
            phases = []
            for g in x.green_phases:
                links = [x.links[i] for i in sorted(g.green_links())]
                phases.append(
                    _PhaseLanes(
                        tuple(dict.fromkeys(link.from_lane for link in links)),
                        tuple(dict.fromkeys(link.to_lane for link in links)),
                        frozenset(link.from_edge for link in links),
                    )
                )
            self._phases[tls] = tuple(phases)
            self._last_green[tls] = [0.0] * len(phases)
        return dict.fromkeys(network.tls_ids, 0)

    def scores(self, tls: str, snap: TrafficSnapshot) -> list[float]:
        lanes = snap.lanes
        wait = {a.approach_id: a.wait_s for a in snap.approaches[tls]}
        out = []
        for ph in self._phases[tls]:
            pressure = sum(lanes[lane].halting for lane in ph.in_lanes) - self.params.alpha * sum(
                lanes[lane].halting for lane in ph.out_lanes
            )
            w = max(wait[a] for a in ph.approaches)
            out.append(pressure + self.params.beta * w)
        return out

    def decide(
        self, snapshot: TrafficSnapshot, signals: dict[str, SignalState]
    ) -> list[ControlRequest]:
        now = snapshot.sim_time_s
        p = self.params
        requests = []
        for tls, sig in signals.items():
            last = self._last_green[tls]
            if sig.phase_id is None:  # in transition
                continue
            last[sig.phase_id] = now  # the current phase is being served
            if sig.phase_elapsed_s < max(self._safety.min_green_s, p.min_hold_s):
                continue
            current = sig.phase_id
            s = self.scores(tls, snapshot)
            others = [k for k in range(len(s)) if k != current]
            red_for = {k: now - last[k] for k in others}
            overdue = [k for k in others if red_for[k] >= p.max_red_s - self._safety.clearance_s]
            if overdue:
                choice, why = max(overdue, key=lambda k: red_for[k]), "max_red"
            elif sig.phase_elapsed_s >= p.max_green_s:
                choice, why = max(others, key=lambda k: s[k]), "max_green"
            else:
                best = max(others, key=lambda k: s[k])
                if s[best] > s[current] + p.switch_margin:
                    choice, why = best, "pressure"
                else:
                    choice, why = current, "extend"
            self.decisions[why] = self.decisions.get(why, 0) + 1
            requests.append(
                ControlRequest(
                    controller_id=self.controller_id,
                    intersection_id=tls,
                    requested_phase=choice,
                    snapshot_step=snapshot.effective_step,
                    reason=f"{why} S={[round(v, 2) for v in s]}",
                )
            )
        return requests

    def describe(self) -> dict:
        return {"controller": self.controller_id, "params": asdict(self.params)}
