"""Run one experiment: scenario + demand + controller -> run folder (PLAN tasks 1.6-1.8).

The loop follows D2 Algorithm 3: the adapter steps SUMO once, the snapshot goes to the
controller, its requests go through the safety filter, the adapter applies the resulting states,
and the step is recorded. An independent ``SafetyMonitor`` checks every state shown.

Run folder contents::

    manifest.json        config, seed, versions, checksums, termination reason (FR-17)
    metrics.json         summary metrics (metric version in the file)
    timeseries.csv       network queue / vehicles every 60 s
    signal_events.csv    every shown green / yellow / all-red change
    applied_controls.csv requests that switched or were changed by the safety filter (FR-07)
    tripinfo.xml, statistics.xml, demand/   raw SUMO input and output

Usage::

    python -m manzil.experiments.runner --profile light --seed 0 --controller adaptive
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import manzil
from manzil.control.adaptive import AdaptiveController, AdaptiveParams
from manzil.control.fixed_time import SignalTiming
from manzil.control.safety import SafetyFilter, SafetyMonitor
from manzil.experiments.emergency import MissionConfig, MissionDriver
from manzil.experiments.metrics import (
    METRIC_VERSION,
    QueueCollector,
    signal_metrics,
    statistics_output,
    trip_metrics,
    write_csv,
)
from manzil.scenarios.demand import PROFILES, build_demand
from manzil.scenarios.grid import content_sha256, sumo_version
from manzil.sim.adapter import QUIET_ARGS, SimulationAdapter
from manzil.sim.network import NetworkModel

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROLLERS = ("fixed_time", "adaptive", "dqn")


@dataclass(frozen=True)
class RunConfig:
    scenario: str = "grid3x3"
    profile: str = "light"
    seed: int = 0
    controller: str = "fixed_time"
    plan: str = "auto"  # fixed-time plan from signals.json; "auto" = the plan for the profile
    warmup_s: float = 900.0
    measure_s: float = 3600.0
    backend: str = "libsumo"
    time_to_teleport_s: float = 300.0
    # Overrides of the scenario's controller parameters, e.g. (("beta", 0.02),). A tuple of
    # pairs keeps the config hashable and its digest stable.
    controller_params: tuple[tuple[str, float], ...] = ()
    mission: MissionConfig | None = None  # an ambulance mission inside the run (Phase 3)
    label: str = ""  # name of the experiment arm, e.g. "corridor_on" (used by comparisons)
    checkpoint: str = ""  # DQN checkpoint overriding the scenario's (path from the repo root)

    @property
    def end_s(self) -> float:
        return self.warmup_s + self.measure_s

    @property
    def scenario_dir(self) -> Path:
        return REPO_ROOT / "scenarios" / self.scenario

    def validate(self) -> None:
        """FR-01: reject a bad configuration before anything starts."""
        problems = []
        if not (self.scenario_dir / "network.json").is_file():
            problems.append(f"unknown scenario {self.scenario!r}")
        if self.profile not in PROFILES:
            problems.append(f"unknown demand profile {self.profile!r}")
        if self.controller not in CONTROLLERS:
            problems.append(f"unknown controller {self.controller!r}")
        if self.seed < 0:
            problems.append("seed must be >= 0")
        if self.warmup_s < 0 or self.measure_s <= 0:
            problems.append("warm-up must be >= 0 and measurement > 0")
        if self.warmup_s % 1 or self.measure_s % 1:
            problems.append("durations must be whole seconds (1 s steps)")
        if self.backend not in ("libsumo", "traci"):
            problems.append(f"unknown backend {self.backend!r}")
        if self.mission is not None:
            problems += self.mission.validate()
            if not 0 <= self.mission.dispatch_s < self.end_s:
                problems.append("mission dispatch must be inside the run")
        if problems:
            raise ValueError("invalid run config: " + "; ".join(problems))

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:10]


@dataclass
class RunResult:
    run_dir: Path
    metrics: dict
    manifest: dict
    violations: list[str] = field(default_factory=list)


def make_controller(config: RunConfig, timing: SignalTiming, network: NetworkModel):
    if config.controller == "fixed_time":
        plan = timing.resolve_plan(config.plan, config.profile)
        return timing.fixed_time_controller(network, plan)
    if config.controller == "adaptive":
        params = {**timing.adaptive, **dict(config.controller_params)}
        return AdaptiveController(AdaptiveParams(**params))
    if config.controller == "dqn":
        from manzil.control.dqn import DQNController  # needs the optional torch dependency

        ckpt = config.checkpoint or timing.dqn.get("checkpoint", "")
        if not ckpt:
            raise ValueError("no DQN checkpoint configured")
        path = Path(ckpt) if Path(ckpt).is_absolute() else REPO_ROOT / ckpt
        return DQNController(str(path), decision_s=int(timing.dqn.get("decision_s", 5)))
    raise ValueError(f"unknown controller {config.controller!r}")


def _git_commit() -> dict:
    def git(*args):
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else None

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def run(config: RunConfig, out_dir: Path | None = None) -> RunResult:
    config.validate()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{config.scenario}_{config.controller}_{config.profile}_s{config.seed}"
    run_dir = Path(out_dir) if out_dir else REPO_ROOT / "runs" / f"{stamp}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    net_file = config.scenario_dir / f"{config.scenario}.net.xml"
    network = NetworkModel.from_file(net_file)
    timing = SignalTiming.load(config.scenario_dir / "signals.json")
    controller = make_controller(config, timing, network)
    demand = build_demand(config.profile, config.seed, config.end_s, net_file, run_dir / "demand")

    tripinfo, stats = run_dir / "tripinfo.xml", run_dir / "statistics.xml"
    sumo_args = [
        "--net-file",
        str(net_file),
        "--route-files",
        str(demand.routes),
        "--seed",
        str(config.seed),
        "--begin",
        "0",
        "--end",
        str(config.end_s),
        "--step-length",
        "1",
        "--time-to-teleport",
        str(config.time_to_teleport_s),
        "--tripinfo-output",
        str(tripinfo),
        "--tripinfo-output.write-unfinished",
        "true",
        "--statistic-output",
        str(stats),
        *QUIET_ARGS,
    ]
    if config.mission and config.mission.incident == "closure":
        # Vehicles whose pre-generated route crosses the closure would be refused at insertion.
        # Insert them anyway; the adapter reroutes every new vehicle around closures at once.
        sumo_args += ["--ignore-route-errors", "true"]  # fmt: skip

    manifest = {
        "run_id": run_id,
        "created_at_utc": stamp,
        "config": asdict(config),
        "config_digest": config.digest(),
        "metric_version": METRIC_VERSION,
        "versions": {
            "manzil": manzil.__version__,
            "sumo": sumo_version(),
            "python": platform.python_version(),
            "git": _git_commit(),
        },
        "network": {"id": network.network_id, "content_sha256": content_sha256(net_file)},
        "demand": json.loads(demand.manifest.read_text()),
        "signal_timing": {"version": timing.version, "safety": asdict(timing.safety)},
        "controller": controller.describe(),
        "sumo_args": [a if not a.startswith(str(REPO_ROOT)) else
                      Path(a).relative_to(REPO_ROOT).as_posix() for a in sumo_args],
        "termination": "not started",
    }  # fmt: skip

    safety = SafetyFilter(network, timing.safety)
    monitor = SafetyMonitor(network, timing.safety)
    queues = QueueCollector(config.warmup_s)
    sim = SimulationAdapter(network, config.backend)
    driver = MissionDriver(config.mission, network, safety, sim) if config.mission else None
    wall0 = time.perf_counter()
    try:
        snap = sim.start(sumo_args)
        initial = controller.reset(network, timing.safety)
        states = safety.reset(initial, now=snap.sim_time_s, step=snap.effective_step)
        for tls, s in states.items():
            sim.set_signal_state(tls, s)
        monitor.observe(snap.sim_time_s, states)
        while snap.sim_time_s < config.end_s:
            snap = sim.step()
            now, step = snap.sim_time_s, snap.effective_step
            if now >= config.end_s:
                queues.record(snap)
                break
            if driver:  # routing and corridor act before the normal controller (Alg 3)
                driver.step(snap)
            signals = {tls: safety.signal_state(tls, now) for tls in network.tls_ids}
            for req in controller.decide(snap, signals):
                safety.submit(req, now, step)
            states = safety.tick(now, step)
            for tls, s in states.items():
                sim.set_signal_state(tls, s)
            monitor.observe(now, states)
            queues.record(snap)
        manifest["termination"] = "completed"
    except Exception as exc:  # recorded, then re-raised: failed runs are kept (D2)
        manifest["termination"] = f"error: {type(exc).__name__}: {exc}"
        raise
    finally:
        sim.stop()
        manifest["wall_time_s"] = round(time.perf_counter() - wall0, 2)
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    n_phases = {t: len(x.green_phases) for t, x in network.intersections.items()}
    interventions: dict[str, int] = {}
    for a in safety.applied:
        interventions[a.safety_intervention] = interventions.get(a.safety_intervention, 0) + 1
    metrics = {
        "metric_version": METRIC_VERSION,
        "run_id": run_id,
        "window_s": [config.warmup_s, config.end_s],
        **trip_metrics(tripinfo, config.warmup_s, config.end_s),
        **queues.summary(),
        **signal_metrics(safety.events, n_phases, config.warmup_s, config.end_s),
        **statistics_output(stats),
        "safety_violations": len(monitor.violations),
        "safety_interventions": dict(sorted(interventions.items())),
        "controller_decisions": dict(sorted(getattr(controller, "decisions", {}).items())),
        "corridor_held_requests": safety.owner_held,
    }
    if driver:
        metrics.update(driver.metrics())
        (run_dir / "mission.json").write_text(json.dumps(driver.records(), indent=2) + "\n")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    write_csv(run_dir / "timeseries.csv", queues.samples)
    write_csv(run_dir / "signal_events.csv", [_row(e) for e in safety.events])
    write_csv(run_dir / "applied_controls.csv", [_row(a) for a in safety.applied])
    return RunResult(run_dir, metrics, manifest, monitor.violations)


def _row(obj) -> dict:
    d = dataclasses.asdict(obj)
    return {k: (v.value if hasattr(v, "value") else v) for k, v in d.items()}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--scenario", default="grid3x3")
    p.add_argument("--controller", default="fixed_time", choices=CONTROLLERS)
    p.add_argument("--profile", default="light", choices=sorted(PROFILES))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--plan", default="auto", help='fixed-time plan name, or "auto"')
    p.add_argument("--warmup", type=float, default=900.0)
    p.add_argument("--measure", type=float, default=3600.0)
    p.add_argument("--backend", default="libsumo", choices=("libsumo", "traci"))
    p.add_argument("--out-dir", type=Path, default=None)
    a = p.parse_args(argv)
    cfg = RunConfig(a.scenario, a.profile, a.seed, a.controller, a.plan, a.warmup, a.measure,
                    a.backend)  # fmt: skip
    result = run(cfg, a.out_dir)
    print(json.dumps(result.metrics, indent=2))
    print(f"run folder: {result.run_dir}")


if __name__ == "__main__":
    main()
