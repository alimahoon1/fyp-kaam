"""Fixed-time controller: a declared cycle per junction (PLAN task 1.6, D2 section 5.4.1).

Each junction runs its green phases in order with declared green times; every change uses the
safety filter's yellow + all-red, so the cycle length is ``sum(green) + n_phases * clearance``.
An offset shifts the cycle start per junction (all zero on the grid for now).

The controller is time-driven: at time ``t`` it requests the phase whose window contains
``(t + offset) mod cycle``. During the clearance after phase ``k`` it already requests ``k+1``,
which is exactly when the filter must be showing yellow / all-red, so schedule and filter stay
in step. Plans are validated so that every green is at least the minimum green.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from manzil.control.safety import SafetyConfig
from manzil.sim.contracts import ControlRequest, SignalState, TrafficSnapshot
from manzil.sim.network import NetworkModel


@dataclass(frozen=True)
class JunctionPlan:
    green_s: tuple[float, ...]
    offset_s: float = 0.0

    def cycle_s(self, clearance_s: float) -> float:
        return sum(self.green_s) + len(self.green_s) * clearance_s

    def phase_at(self, t: float, clearance_s: float) -> int:
        """Phase to request at ``t``: the current green window, or the next one during clearance."""
        pos = (t + self.offset_s) % self.cycle_s(clearance_s)
        start = 0.0
        n = len(self.green_s)
        for k, g in enumerate(self.green_s):
            if pos < start + g:
                return k
            if pos < start + g + clearance_s:
                return (k + 1) % n
            start += g + clearance_s
        return 0  # floating-point edge at the very end of the cycle


@dataclass
class FixedTimeController:
    plans: dict[str, JunctionPlan]
    plan_name: str = "default"
    plan_version: int = 1
    controller_id: str = "fixed_time"
    _clearance: float = field(default=0.0, repr=False)

    def reset(self, network: NetworkModel, safety: SafetyConfig) -> dict[str, int]:
        self._clearance = safety.clearance_s
        missing = set(network.tls_ids) - set(self.plans)
        if missing:
            raise ValueError(f"no fixed-time plan for {sorted(missing)}")
        for tls, plan in self.plans.items():
            n = len(network.intersections[tls].green_phases)
            if len(plan.green_s) != n:
                raise ValueError(f"{tls}: plan has {len(plan.green_s)} greens, junction has {n}")
            if min(plan.green_s) < safety.min_green_s:
                raise ValueError(f"{tls}: green below minimum green {safety.min_green_s}s")
        return {tls: self.plans[tls].phase_at(0.0, self._clearance) for tls in network.tls_ids}

    def decide(
        self, snapshot: TrafficSnapshot, signals: dict[str, SignalState]
    ) -> list[ControlRequest]:
        t = snapshot.sim_time_s
        return [
            ControlRequest(
                controller_id=self.controller_id,
                intersection_id=tls,
                requested_phase=plan.phase_at(t, self._clearance),
                snapshot_step=snapshot.effective_step,
                reason="schedule",
            )
            for tls, plan in self.plans.items()
        ]

    def describe(self) -> dict:
        return {
            "controller": self.controller_id,
            "plan_name": self.plan_name,
            "plan_version": self.plan_version,
            "plans": {t: {"green_s": list(p.green_s), "offset_s": p.offset_s}
                      for t, p in sorted(self.plans.items())},
        }  # fmt: skip


@dataclass(frozen=True)
class SignalTiming:
    """Scenario signal file: safety timing and named fixed-time plans, versioned together."""

    version: int
    safety: SafetyConfig
    plans: dict[str, dict]  # plan name -> {"default": {...}, "junctions": {tls: {...}}}
    profile_plans: dict[str, str]  # demand profile -> plan name used when the plan is "auto"
    adaptive: dict  # parameters of the pressure controller
    dqn: dict  # trained DQN checkpoint (path relative to the repo root) and decision interval

    @classmethod
    def load(cls, path: str | Path) -> SignalTiming:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            version=int(data["version"]),
            safety=SafetyConfig(**data["safety"]),
            plans=data["fixed_time_plans"],
            profile_plans=data.get("profile_plans", {}),
            adaptive={k: v for k, v in data.get("adaptive", {}).items() if k != "description"},
            dqn={k: v for k, v in data.get("dqn", {}).items() if k != "description"},
        )

    def resolve_plan(self, plan_name: str, profile: str) -> str:
        """``"auto"`` means the plan declared for the demand profile."""
        if plan_name != "auto":
            return plan_name
        if profile not in self.profile_plans:
            raise KeyError(f"no fixed-time plan declared for profile {profile!r}")
        return self.profile_plans[profile]

    def fixed_time_controller(self, network: NetworkModel, plan_name: str) -> FixedTimeController:
        if plan_name not in self.plans:
            raise KeyError(f"unknown fixed-time plan {plan_name!r}; have {sorted(self.plans)}")
        spec = self.plans[plan_name]
        default = spec.get("default")
        per = spec.get("junctions", {})
        plans = {}
        for tls in network.tls_ids:
            p = per.get(tls, default)
            if p is None:
                raise ValueError(f"plan {plan_name!r} has no entry for {tls}")
            greens = tuple(float(g) for g in p["green_s"])
            plans[tls] = JunctionPlan(greens, float(p.get("offset_s", 0)))
        return FixedTimeController(plans, plan_name=plan_name, plan_version=self.version)
