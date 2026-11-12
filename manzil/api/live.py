"""One live SUMO run for the dashboard (PLAN task 5.1).

``LiveSession`` runs the same loop as ``manzil.experiments.runner.run`` (D2 Algorithm 3:
snapshot -> routing -> corridor -> controller -> safety filter -> adapter), but step by step in
a background thread so the dashboard can watch it and change it while it runs:

- start / stop a run with a chosen controller (fixed-time, adaptive, DQN), demand profile, seed;
- dispatch an ambulance A -> B, with or without the green corridor (``MissionDriver``);
- close a road (hard closure through the adapter; the ambulance reroutes by Algorithm 1).

Every SUMO call happens in the worker thread. Requests from the API are queued as commands and
run between two simulation steps; the caller waits for the result. The latest state is kept as
a plain dict that the API returns or streams.

Nothing here is simulated or mocked beyond SUMO itself: the signals, vehicles, ambulance route
and corridor states shown are the values of the real run. Each run writes a folder under
``runs/live/`` with SUMO's tripinfo output and a ``summary.json`` (config, safety violations,
every mission's metrics and route versions).
"""

from __future__ import annotations

import json
import queue
import threading
import time
import traceback
from concurrent.futures import Future
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from manzil.control.fixed_time import SignalTiming
from manzil.control.safety import SafetyFilter, SafetyMonitor
from manzil.experiments.emergency import MissionConfig, MissionDriver
from manzil.experiments.runner import REPO_ROOT, RunConfig, make_controller
from manzil.scenarios.demand import build_demand
from manzil.sim.adapter import QUIET_ARGS, SimulationAdapter
from manzil.sim.network import NetworkModel

STATE_INTERVAL_S = 0.1  # rebuild the published state at most this often (wall clock)


@dataclass(frozen=True)
class LiveConfig:
    controller: str = "fixed_time"
    profile: str = "medium"
    seed: int = 0
    duration_s: float = 3600.0
    speed: float = 10.0  # simulated seconds per wall-clock second; 0 = as fast as possible
    scenario: str = "grid3x3"
    backend: str = "traci"  # SUMO in its own process: a crash cannot take the API down

    def run_config(self) -> RunConfig:
        return RunConfig(
            scenario=self.scenario,
            profile=self.profile,
            seed=self.seed,
            controller=self.controller,
            warmup_s=0.0,
            measure_s=self.duration_s,
            backend=self.backend,
        )


class CommandError(Exception):
    """A request that cannot be carried out (bad edge, mission already running, ...)."""


class LiveSession:
    def __init__(self, runs_dir: Path | None = None):
        self.runs_dir = Path(runs_dir) if runs_dir else REPO_ROOT / "runs" / "live"
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._commands: queue.Queue = queue.Queue()
        self._state: dict = {"status": "idle", "version": 0}
        self._version = 0
        self.config: LiveConfig | None = None
        self.speed = 10.0

    # ----- API side --------------------------------------------------------------------------
    @property
    def state(self) -> dict:
        return self._state

    @property
    def status(self) -> str:
        return self._state["status"]

    def start(self, config: LiveConfig) -> dict:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise CommandError("a run is already active; stop it first")
            config.run_config().validate()  # FR-01: reject a bad config before starting
            if config.speed < 0:
                raise CommandError("speed must be >= 0")
            self.config = config
            self.speed = config.speed
            self._stop.clear()
            self._commands = queue.Queue()
            self._publish({"status": "starting", "config": asdict(config)})
            self._thread = threading.Thread(target=self._worker, args=(config,), daemon=True)
            self._thread.start()
            return self._state

    def stop(self, timeout: float = 30.0) -> dict:
        thread = self._thread
        if thread is None or not thread.is_alive():
            return self._state
        self._stop.set()
        thread.join(timeout)
        return self._state

    def set_speed(self, speed: float) -> None:
        if speed < 0:
            raise CommandError("speed must be >= 0")
        self.speed = speed

    def dispatch(self, origin: str, destination: str, corridor: bool, timeout=60.0) -> dict:
        return self._call("dispatch", timeout, origin, destination, corridor)

    def close_road(self, edge_id: str, timeout=60.0) -> dict:
        return self._call("close", timeout, edge_id)

    def wait_for(self, predicate, timeout: float = 120.0, poll: float = 0.05) -> dict:
        """Block until ``predicate(state)`` is true (used by tests and scripts)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            s = self._state
            if predicate(s):
                return s
            if s["status"] == "error":
                raise RuntimeError(s.get("error"))
            time.sleep(poll)
        raise TimeoutError(f"state condition not reached; status {self._state['status']}")

    def _call(self, name: str, timeout: float, *args) -> dict:
        thread = self._thread
        if thread is None or not thread.is_alive() or self._stop.is_set():
            raise CommandError("no run is active; start one first")
        fut: Future = Future()
        self._commands.put((name, args, fut))
        return fut.result(timeout)

    def _publish(self, state: dict) -> None:
        self._version += 1
        self._state = {**state, "version": self._version}

    # ----- worker thread ---------------------------------------------------------------------
    def _worker(self, config: LiveConfig) -> None:
        run = None
        try:
            run = _Run(config, self.runs_dir)
            self._publish(run.state("running"))
            last_pub = 0.0
            wall0, sim0 = time.perf_counter(), run.now
            speed = self.speed
            while not self._stop.is_set():
                self._run_commands(run)
                if run.finished:
                    break
                run.step()
                if self.speed != speed:  # restart pacing from here when the speed changes
                    speed, wall0, sim0 = self.speed, time.perf_counter(), run.now
                if speed > 0:
                    delay = wall0 + (run.now - sim0) / speed - time.perf_counter()
                    if delay > 0:
                        self._stop.wait(delay)
                t = time.perf_counter()
                if t - last_pub >= STATE_INTERVAL_S:
                    self._publish(run.state("running"))
                    last_pub = t
            status = "finished" if run.finished else "stopped"
            run.close(status)
            self._publish(run.state(status))
        except Exception as exc:  # shown on the dashboard; the run folder keeps the trace
            if run is not None:
                run.close(f"error: {type(exc).__name__}: {exc}")
            base = run.state("error") if run is not None else {"config": asdict(config)}
            self._publish({**base, "status": "error", "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc(limit=5)})  # fmt: skip
        finally:
            while not self._commands.empty():  # nobody will run these any more
                _, _, fut = self._commands.get_nowait()
                fut.set_exception(CommandError("the run ended"))

    def _run_commands(self, run: _Run) -> None:
        while True:
            try:
                name, args, fut = self._commands.get_nowait()
            except queue.Empty:
                return
            try:
                result = run.dispatch(*args) if name == "dispatch" else run.close_road(*args)
                self._publish(run.state("running"))
                fut.set_result(result)
            except Exception as exc:
                fut.set_exception(exc)


class _Run:
    """The objects of one run. Used only from the worker thread."""

    def __init__(self, config: LiveConfig, runs_dir: Path):
        rc = config.run_config()
        self.config, self.rc = config, rc
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"{stamp}_{rc.scenario}_{rc.controller}_{rc.profile}_s{rc.seed}"
        self.run_dir = runs_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        net_file = rc.scenario_dir / f"{rc.scenario}.net.xml"
        self.network = NetworkModel.from_file(net_file)
        timing = SignalTiming.load(rc.scenario_dir / "signals.json")
        self.controller = make_controller(rc, timing, self.network)
        demand = build_demand(rc.profile, rc.seed, rc.end_s, net_file, self.run_dir / "demand")
        self.vehicles_planned = demand.vehicles
        args = [
            "--net-file", str(net_file), "--route-files", str(demand.routes),
            "--seed", str(rc.seed), "--begin", "0", "--end", str(rc.end_s), "--step-length", "1",
            "--time-to-teleport", str(rc.time_to_teleport_s),
            "--tripinfo-output", str(self.run_dir / "tripinfo.xml"),
            "--tripinfo-output.write-unfinished", "true",
            # A user may close any road at any time; vehicles inserted later on a route through
            # it are rerouted by the adapter instead of being refused.
            "--ignore-route-errors", "true",
            *QUIET_ARGS,
        ]  # fmt: skip
        self.safety = SafetyFilter(self.network, timing.safety)
        self.monitor = SafetyMonitor(self.network, timing.safety)
        self.sim = SimulationAdapter(self.network, rc.backend, track_positions=True)
        self.missions: list[MissionDriver] = []
        self.mission_metrics: list[dict | None] = []
        self.closures: list[dict] = []
        self.wall0 = time.perf_counter()
        self.snap = self.sim.start(args)
        try:
            initial = self.controller.reset(self.network, timing.safety)
            states = self.safety.reset(initial, now=self.snap.sim_time_s, step=0)
            for tls, s in states.items():
                self.sim.set_signal_state(tls, s)
            self.monitor.observe(self.snap.sim_time_s, states)
        except Exception:
            self.sim.stop()
            raise
        self.closed_reason = ""

    @property
    def now(self) -> float:
        return self.snap.sim_time_s

    @property
    def finished(self) -> bool:
        return self.now >= self.rc.end_s

    @property
    def mission(self) -> MissionDriver | None:
        return self.missions[-1] if self.missions else None

    def step(self) -> None:
        snap = self.sim.step()
        self.snap = snap
        now, step = snap.sim_time_s, snap.effective_step
        if self.finished:
            return
        for i, d in enumerate(self.missions):  # routing + corridor before the controller
            if d.mission.status in ("PENDING", "ACTIVE"):
                d.step(snap)
                if d.mission.status not in ("PENDING", "ACTIVE"):
                    self.mission_metrics[i] = d.metrics()
        signals = {tls: self.safety.signal_state(tls, now) for tls in self.network.tls_ids}
        for req in self.controller.decide(snap, signals):
            self.safety.submit(req, now, step)
        states = self.safety.tick(now, step)
        for tls, s in states.items():
            self.sim.set_signal_state(tls, s)
        self.monitor.observe(now, states)

    # ----- commands --------------------------------------------------------------------------
    def dispatch(self, origin: str, destination: str, corridor: bool) -> dict:
        m = self.mission
        if m is not None and m.mission.status in ("PENDING", "ACTIVE"):
            raise CommandError("an ambulance is already on a mission")
        if self.now + 1 >= self.rc.end_s:
            raise CommandError("the run is about to end")
        cfg = MissionConfig(origin=origin, destination=destination, dispatch_s=self.now + 1,
                            routing="dynamic", corridor=corridor)  # fmt: skip
        try:
            driver = MissionDriver(cfg, self.network, self.safety, self.sim,
                                   vehicle_id=f"ambulance_{len(self.missions) + 1}")  # fmt: skip
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if origin == destination:
            raise CommandError("origin and destination are the same road")
        self.missions.append(driver)
        self.mission_metrics.append(None)
        return {"vehicle_id": driver.vehicle_id, "dispatch_s": cfg.dispatch_s}

    def close_road(self, edge_id: str) -> dict:
        try:
            self.network.net.getEdge(edge_id)
        except KeyError as exc:
            raise CommandError(f"unknown road {edge_id!r}") from exc
        if edge_id in self.sim.closed_edges:
            raise CommandError(f"road {edge_id} is already closed")
        rerouted = self.sim.close_edge(edge_id)
        self.closures.append({"edge_id": edge_id, "time_s": self.now, "rerouted": rerouted})
        return {"edge_id": edge_id, "time_s": self.now, "vehicles_rerouted": rerouted}

    # ----- output ----------------------------------------------------------------------------
    def state(self, status: str) -> dict:
        snap = self.snap
        pos = self.sim.vehicle_positions
        amb_ids = {d.vehicle_id for d in self.missions}
        signals = {}
        for tls in self.network.tls_ids:
            s = self.safety.signal_state(tls, self.now)
            signals[tls] = {
                "state": snap.signal_states.get(tls, s.state),
                "phase": s.phase_id,
                "owner": s.owner.value,
                "in_transition": s.in_transition,
                "elapsed_s": round(s.phase_elapsed_s, 1),
            }
        moving = [v for k, v in pos.items() if k not in amb_ids]
        halting = sum(e.halting for e in snap.edges.values())
        elapsed = time.perf_counter() - self.wall0
        return {
            "status": status,
            "run_id": self.run_id,
            "config": asdict(self.config),
            "sim_time_s": self.now,
            "end_s": self.rc.end_s,
            "stats": {
                "running": snap.running,
                "departed": snap.departed_total,
                "arrived": snap.arrived_total,
                "planned": self.vehicles_planned,
                "halting": halting,
                "mean_speed_mps": round(sum(v[3] for v in moving) / len(moving), 2)
                if moving
                else None,
                "safety_violations": len(self.monitor.violations),
                "sim_rate": round(self.now / elapsed, 1) if elapsed > 0 else None,
            },  # fmt: skip
            "signals": signals,
            "vehicles": [[round(x, 1), round(y, 1), round(a)] for x, y, a, _ in moving],
            "edge_halting": {e: s.halting for e, s in snap.edges.items() if s.halting},
            "closed_edges": sorted(self.sim.closed_edges),
            "ambulance": self._ambulance_state(pos),
            "missions_done": sum(1 for m in self.mission_metrics if m is not None),
        }

    def _ambulance_state(self, pos) -> dict | None:
        d = self.mission
        if d is None:
            return None
        m, plan = d.mission, d.mission.plan
        p = pos.get(d.vehicle_id)
        amb = self.snap.tracked.get(d.vehicle_id)
        metrics = self.mission_metrics[-1]
        return {
            "vehicle_id": d.vehicle_id,
            "status": m.status,
            "origin": d.config.origin,
            "destination": d.config.destination,
            "corridor_enabled": d.corridor is not None,
            "dispatch_s": m.dispatch_s,
            "arrival_s": m.arrival_s,
            "position": [round(p[0], 1), round(p[1], 1), round(p[2])] if p else None,
            "speed_mps": round(amb.speed_mps, 2) if amb else None,
            "edge": amb.edge_id if amb else None,
            "route": list(plan.edge_ids) if plan else [],
            "route_version": m.version,
            "route_triggers": [x.trigger for x in m.plans],
            "stops": d.stops,
            "corridor": d.corridor.status() if d.corridor else {},
            "corridor_events": _jsonable(d.corridor.events[-8:]) if d.corridor else [],
            "metrics": _jsonable(metrics) if metrics else None,
        }

    def close(self, termination: str) -> None:
        try:
            self.sim.stop()
        finally:
            for i, d in enumerate(self.missions):
                if self.mission_metrics[i] is None:
                    self.mission_metrics[i] = d.metrics()
            summary = {
                "run_id": self.run_id,
                "source": "Manzil dashboard live run (real SUMO simulation)",
                "config": asdict(self.config),
                "termination": termination,
                "sim_time_s": self.now,
                "wall_time_s": round(time.perf_counter() - self.wall0, 2),
                "vehicles_departed": self.snap.departed_total,
                "vehicles_arrived": self.snap.arrived_total,
                "safety_violations": len(self.monitor.violations),
                "closures": self.closures,
                "missions": [
                    {
                        "vehicle_id": d.vehicle_id,
                        "metrics": _jsonable(self.mission_metrics[i]),
                        **d.records(),
                    }
                    for i, d in enumerate(self.missions)
                ],  # fmt: skip
            }
            (self.run_dir / "summary.json").write_text(
                json.dumps(_jsonable(summary), indent=2) + "\n", encoding="utf-8"
            )


def _jsonable(obj):
    """Replace infinities (closed-road costs) so the result is strict JSON."""
    if isinstance(obj, float) and obj in (float("inf"), float("-inf")):
        return None
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj
