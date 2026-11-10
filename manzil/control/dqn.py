"""Parameter-sharing Double DQN for signal control (PLAN task 4.2, D2 5.4.3).

One Q-network maps a junction's local observation to a value per phase slot; every junction of
the network uses the same weights. Invalid phases are masked out of both action choice and the
bootstrap target. ``DQNController`` runs a trained checkpoint inside normal experiment runs
through the same safety filter as every other controller. If inference fails it falls back to
holding the current phase and counts the fallback (FR-20).
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
from torch import nn

from manzil.control.rl_env import (
    MAX_PHASES,
    OBS_SIZE,
    RL_ID,
    action_mask,
    build_layouts,
    observe,
)
from manzil.control.safety import SafetyConfig
from manzil.sim.contracts import ControlRequest, SignalState, TrafficSnapshot
from manzil.sim.network import NetworkModel


@dataclass(frozen=True)
class DQNParams:
    hidden: int = 128
    lr: float = 5e-4
    gamma: float = 0.95
    batch: int = 128
    replay: int = 100_000
    target_sync: int = 1000  # gradient steps between target-network copies
    eps_start: float = 1.0
    eps_end: float = 0.05
    eps_decay_steps: int = 20_000  # environment decision steps
    warmup_transitions: int = 2_000


class QNet(nn.Module):
    def __init__(self, hidden: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(OBS_SIZE, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, MAX_PHASES),
        )  # fmt: skip

    def forward(self, x):
        return self.net(x)


def masked_argmax(q: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    return q.masked_fill(~mask, -1e9).argmax(dim=-1)


@dataclass
class DQNAgent:
    params: DQNParams = field(default_factory=DQNParams)
    seed: int = 0

    def __post_init__(self):
        torch.manual_seed(self.seed)
        self.rng = random.Random(self.seed)
        self.online = QNet(self.params.hidden)
        self.target = QNet(self.params.hidden)
        self.target.load_state_dict(self.online.state_dict())
        self.opt = torch.optim.Adam(self.online.parameters(), lr=self.params.lr)
        self.buffer: deque = deque(maxlen=self.params.replay)
        self.env_steps = 0
        self.grad_steps = 0

    @property
    def epsilon(self) -> float:
        p = self.params
        frac = min(self.env_steps / p.eps_decay_steps, 1.0)
        return p.eps_start + frac * (p.eps_end - p.eps_start)

    def act(self, obs: dict, masks: dict, greedy: bool = False) -> dict[str, int]:
        keys = list(obs)
        with torch.no_grad():
            q = self.online(torch.as_tensor(np.stack([obs[k] for k in keys])))
            best = masked_argmax(q, torch.as_tensor(np.stack([masks[k] for k in keys])))
        out = {}
        for i, k in enumerate(keys):
            if not greedy and self.rng.random() < self.epsilon:
                out[k] = self.rng.choice(list(np.flatnonzero(masks[k])))
            else:
                out[k] = int(best[i])
        return out

    def remember(self, o, a, r, o2, m2, done) -> None:
        self.buffer.append((o, a, r, o2, m2, done))

    def learn(self) -> float | None:
        p = self.params
        if len(self.buffer) < max(p.warmup_transitions, p.batch):
            return None
        batch = self.rng.sample(self.buffer, p.batch)
        o, a, r, o2, m2, d = (np.array(x) for x in zip(*batch, strict=True))
        o, o2 = torch.as_tensor(o), torch.as_tensor(o2)
        a = torch.as_tensor(a, dtype=torch.int64)
        r = torch.as_tensor(r, dtype=torch.float32)
        d = torch.as_tensor(d, dtype=torch.float32)
        m2 = torch.as_tensor(m2)
        q = self.online(o).gather(1, a[:, None]).squeeze(1)
        with torch.no_grad():  # Double DQN: online picks, target evaluates
            a2 = masked_argmax(self.online(o2), m2)
            q2 = self.target(o2).gather(1, a2[:, None]).squeeze(1)
            y = r + p.gamma * (1 - d) * q2
        loss = nn.functional.smooth_l1_loss(q, y)
        self.opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 10.0)
        self.opt.step()
        self.grad_steps += 1
        if self.grad_steps % p.target_sync == 0:
            self.target.load_state_dict(self.online.state_dict())
        return float(loss)

    def save(self, path: Path, meta: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {"state_dict": self.online.state_dict(), "params": asdict(self.params),
             "obs_size": OBS_SIZE, "max_phases": MAX_PHASES, "meta": meta},
            path,
        )  # fmt: skip


def load_qnet(path: str | Path) -> tuple[QNet, dict]:
    ck = torch.load(Path(path), map_location="cpu", weights_only=False)
    if ck["obs_size"] != OBS_SIZE or ck["max_phases"] != MAX_PHASES:
        raise ValueError("checkpoint observation/action layout does not match this code")
    net = QNet(ck["params"]["hidden"])
    net.load_state_dict(ck["state_dict"])
    net.eval()
    return net, ck


@dataclass
class DQNController:
    checkpoint: str
    decision_s: int = 5
    controller_id: str = RL_ID
    decisions: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.net, self._ck = load_qnet(self.checkpoint)  # fail early on a bad checkpoint

    def reset(self, network: NetworkModel, safety: SafetyConfig) -> dict[str, int]:
        self.layouts = build_layouts(network)
        self._min_green = safety.min_green_s
        self.decisions = {"greedy": 0, "fallback": 0}
        return dict.fromkeys(network.tls_ids, 0)

    def decide(
        self, snapshot: TrafficSnapshot, signals: dict[str, SignalState]
    ) -> list[ControlRequest]:
        if int(snapshot.sim_time_s) % self.decision_s:
            return []
        keys = [t for t in self.layouts if not signals[t].in_transition]
        if not keys:
            return []
        try:
            obs = np.stack([observe(self.layouts[t], snapshot, signals[t]) for t in keys])
            masks = np.stack([action_mask(self.layouts[t], signals[t], self._min_green)
                              for t in keys])  # fmt: skip
            with torch.no_grad():
                q = self.net(torch.as_tensor(obs))
                best = masked_argmax(q, torch.as_tensor(masks)).tolist()
            self.decisions["greedy"] += len(keys)
            reason = "dqn"
        except Exception:  # FR-20: never leave a junction without a safe decision
            best = [signals[t].phase_id for t in keys]
            self.decisions["fallback"] += len(keys)
            reason = "dqn_fallback_hold"
        return [
            ControlRequest(self.controller_id, t, int(a), snapshot.effective_step, reason)
            for t, a in zip(keys, best, strict=True)
        ]

    def describe(self) -> dict:
        meta = self._ck.get("meta", {})
        return {"controller": self.controller_id, "checkpoint": self.checkpoint,
                "decision_s": self.decision_s, "training": meta}  # fmt: skip
