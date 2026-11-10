"""Reinforcement-learning environment on top of the SimulationAdapter (PLAN task 4.1, D2 5.4.3).

Parameter sharing: every junction is described by the same fixed-length local observation and
chooses among the same number of action slots (green phases, padded and masked), so one network
serves all junctions. The safety filter stays authoritative: the agent only *requests* a phase,
and the action mask allows a switch only when minimum green has been served.

Observation (``OBS_SIZE`` floats per junction):

- per approach (up to ``MAX_APPROACHES``, ordered by compass direction, zero-padded):
  halting vehicles / (lanes x 20), vehicles / (lanes x 20), waiting time / (lanes x 300),
  1 if the approach has green now;
- per phase slot (``MAX_PHASES``): one-hot current phase, and the phase pressure
  (served incoming halting - fed outgoing halting) / 20;
- elapsed green / 60 and a transition flag.

Reward per junction between two decisions, Eq 5.3: ``r = -(a P + b W) - c X - d C`` with ``P``
the mean halting vehicles on its approaches, ``W`` the mean summed waiting time / 100, ``X`` = 1
when any phase has been red longer than ``max_red_s`` (starvation), and ``C`` = 1 if the agent
asked for a switch. Emergency status is not part of the state (D2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from manzil.control.fixed_time import SignalTiming
from manzil.control.safety import SafetyFilter, SafetyMonitor
from manzil.scenarios.demand import build_demand
from manzil.sim.adapter import QUIET_ARGS, SimulationAdapter
from manzil.sim.contracts import ControlRequest, SignalState, TrafficSnapshot
from manzil.sim.network import NetworkModel

MAX_APPROACHES = 4
MAX_PHASES = 4
OBS_SIZE = MAX_APPROACHES * 4 + MAX_PHASES * 2 + 2
RL_ID = "dqn"


@dataclass(frozen=True)
class RewardParams:
    a: float = 1.0  # queue (pressure) weight
    b: float = 0.5  # waiting-time weight
    c: float = 2.0  # starvation penalty
    d: float = 0.5  # switch penalty
    max_red_s: float = 90.0
    decision_s: int = 5  # seconds between decisions


@dataclass(frozen=True)
class JunctionLayout:
    tls: str
    approaches: tuple  # Approach objects in compass order
    lanes: tuple[int, ...]
    phase_in: tuple[tuple[str, ...], ...]  # incoming lanes served by each phase
    phase_out: tuple[tuple[str, ...], ...]
    approach_links: tuple[frozenset[int], ...]  # link indices of each approach
    n_phases: int


def build_layouts(network: NetworkModel) -> dict[str, JunctionLayout]:
    layouts = {}
    for tls, x in network.intersections.items():
        if len(x.approaches) > MAX_APPROACHES or len(x.green_phases) > MAX_PHASES:
            raise NotImplementedError(f"{tls}: more approaches/phases than the RL layout allows")

        def bearing(a):  # direction of travel on the approach, clockwise from north
            e = network.net.getEdge(a.edge_id)
            (x0, y0), (x1, y1) = e.getFromNode().getCoord(), e.getToNode().getCoord()
            return math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360

        apps = tuple(sorted(x.approaches, key=bearing))
        phase_in, phase_out = [], []
        for g in x.green_phases:
            links = [x.links[i] for i in sorted(g.green_links())]
            phase_in.append(tuple(dict.fromkeys(lk.from_lane for lk in links)))
            phase_out.append(tuple(dict.fromkeys(lk.to_lane for lk in links)))
        layouts[tls] = JunctionLayout(
            tls,
            apps,
            tuple(len(a.lanes) for a in apps),
            tuple(phase_in),
            tuple(phase_out),
            tuple(frozenset(lk.index for lk in x.links if lk.from_edge == a.edge_id) for a in apps),
            len(x.green_phases),
        )
    return layouts


def observe(lay: JunctionLayout, snap: TrafficSnapshot, sig: SignalState) -> np.ndarray:
    obs = np.zeros(OBS_SIZE, dtype=np.float32)
    by_edge = {a.approach_id: a for a in snap.approaches[lay.tls]}
    for k, (app, lanes) in enumerate(zip(lay.approaches, lay.lanes, strict=True)):
        a = by_edge[app.edge_id]
        cap = lanes * 20.0
        green = any(sig.state[i] in "Gg" for i in lay.approach_links[k])
        obs[4 * k : 4 * k + 4] = (
            min(a.queue / cap, 2.0),
            min(a.count / cap, 2.0),
            min(a.wait_s / (lanes * 300.0), 2.0),
            1.0 if green else 0.0,
        )
    base = MAX_APPROACHES * 4
    if sig.phase_id is not None:
        obs[base + sig.phase_id] = 1.0
    lanes = snap.lanes
    for p in range(lay.n_phases):
        press = sum(lanes[ln].halting for ln in lay.phase_in[p]) - sum(
            lanes[ln].halting for ln in lay.phase_out[p]
        )
        obs[base + MAX_PHASES + p] = np.clip(press / 20.0, -2.0, 2.0)
    obs[-2] = min(sig.phase_elapsed_s / 60.0, 2.0)
    obs[-1] = 1.0 if sig.in_transition else 0.0
    return obs


def action_mask(lay: JunctionLayout, sig: SignalState, min_green_s: float) -> np.ndarray:
    mask = np.zeros(MAX_PHASES, dtype=bool)
    if sig.in_transition or sig.phase_id is None:
        mask[sig.legal_next[0]] = True  # only the phase already coming (a plain hold)
        return mask
    if sig.phase_elapsed_s >= min_green_s:
        mask[: lay.n_phases] = True
    else:
        mask[sig.phase_id] = True  # only "keep"
    return mask


@dataclass
class TrafficEnv:
    """Multi-junction environment: one shared observation/action format for every junction."""

    network: NetworkModel
    timing: SignalTiming
    reward: RewardParams = field(default_factory=RewardParams)
    backend: str = "libsumo"
    work_dir: str = "/tmp"

    def __post_init__(self):
        self.layouts = build_layouts(self.network)
        self.sim: SimulationAdapter | None = None

    def reset(self, profile: str, seed: int, duration_s: float):
        self.close()
        demand = build_demand(profile, seed, duration_s, self.network.net_file, self.work_dir)
        self.sim = SimulationAdapter(self.network, self.backend)
        self.safety = SafetyFilter(self.network, self.timing.safety)
        self.monitor = SafetyMonitor(self.network, self.timing.safety)
        self.end_s = duration_s
        snap = self.sim.start(["-c", str(demand.sumocfg), "--seed", str(seed), *QUIET_ARGS])
        states = self.safety.reset({}, now=snap.sim_time_s, step=0)
        for tls, s in states.items():
            self.sim.set_signal_state(tls, s)
        self.snap = snap
        self._last_green = {t: [0.0] * lay.n_phases for t, lay in self.layouts.items()}
        return self._observe()

    def _signals(self) -> dict[str, SignalState]:
        now = self.snap.sim_time_s
        return {t: self.safety.signal_state(t, now) for t in self.layouts}

    def _observe(self):
        sig = self._signals()
        ms = self.timing.safety.min_green_s
        obs = {t: observe(lay, self.snap, sig[t]) for t, lay in self.layouts.items()}
        masks = {t: action_mask(lay, sig[t], ms) for t, lay in self.layouts.items()}
        return obs, masks

    def step(self, actions: dict[str, int]):
        """Apply phase requests, run ``decision_s`` seconds; returns obs, masks, rewards, done."""
        rp = self.reward
        now, step = self.snap.sim_time_s, self.snap.effective_step
        switched = {}
        for tls, a in actions.items():
            cur = self.safety.showing(tls)
            switched[tls] = cur is not None and a != cur
            self.safety.submit(ControlRequest(RL_ID, tls, int(a), step, "dqn"), now, step)
        p_sum = dict.fromkeys(self.layouts, 0.0)
        w_sum = dict.fromkeys(self.layouts, 0.0)
        for _ in range(rp.decision_s):
            states = self.safety.tick(self.snap.sim_time_s, self.snap.effective_step)
            for tls, s in states.items():
                self.sim.set_signal_state(tls, s)
            self.monitor.observe(self.snap.sim_time_s, states)
            self.snap = self.sim.step()
            for tls in self.layouts:
                apps = self.snap.approaches[tls]
                p_sum[tls] += sum(a.queue for a in apps) / len(apps)
                w_sum[tls] += sum(a.wait_s for a in apps) / len(apps) / 100.0
        t = self.snap.sim_time_s
        rewards = {}
        for tls in self.layouts:
            sig_phase = self.safety.showing(tls)
            if sig_phase is not None:
                self._last_green[tls][sig_phase] = t
            starving = any(t - last > rp.max_red_s for last in self._last_green[tls])
            rewards[tls] = (
                -(rp.a * p_sum[tls] + rp.b * w_sum[tls]) / rp.decision_s
                - rp.c * float(starving)
                - rp.d * float(switched.get(tls, False))
            )
        obs, masks = self._observe()
        done = t >= self.end_s
        return obs, masks, rewards, done

    def close(self):
        if self.sim is not None:
            self.sim.stop()
            self.sim = None
