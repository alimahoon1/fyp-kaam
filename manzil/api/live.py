"""One live SUMO run for the dashboard (PLAN task 5.1).

``LiveSession`` runs the same loop as ``manzil.experiments.runner.run`` (D2 Algorithm 3:
snapshot -> routing -> corridor -> controller -> safety filter -> adapter), but step by step in
a background thread so the dashboard can watch it and change it while it runs:

- start / stop a run with a chosen controller (fixed-time, adaptive, DQN), demand profile, seed;
- dispatch an ambulance A -> B, with or without the green corridor (``MissionDriver``);
- close a road (hard closure through the adapter; the ambulance reroutes by Algorithm 1);
- pause and resume the run (FR-02, W5): while paused SUMO is not stepped, commands still run;
- schedule an ambulance mission and a road closure in the configuration (G01, W5);
- inject a controller fault (W5): "rl_loss" makes the DQN unavailable from that step, so the
  controller's own FR-20 fallback (hold the current legal phase) takes over and is shown.

The published state carries freshness (``produced_at``, ``effective_step``) and a list of
``warnings`` (FR-16): ``fallback`` (DQN decisions held by the fallback), ``invalid`` (safety
violation, invalid snapshot, ambulance without a route), ``disconnected`` (SUMO connection
lost); ``stale`` is added by :meth:`LiveSession.view` when the worker has not published for
``STALE_AFTER_S`` seconds of wall-clock time.

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
PAUSED_PUBLISH_S = 0.5  # while paused the state is re-published this often (stays fresh)
STALE_AFTER_S = 2.0  # FR-16: no new state for this long while running = stale
STARTING_STALE_AFTER_S = 60.0  # starting SUMO and building demand can take a while
HISTORY_EVERY_S = 10  # network indicators kept every 10 simulated seconds (G02 chart)
FAULTS = ("rl_loss",)


@dataclass(frozen=True)
class PlannedMission:
    """An ambulance mission set in the run configuration (dispatched at ``dispatch_s``)."""

    origin: str
    destination: str
    corridor: bool = True
    dispatch_s: float = 60.0


@dataclass(frozen=True)
class PlannedIncident:
    """A road closure set in the run configuration (applied at ``time_s``)."""

    edge_id: str
    time_s: float = 120.0


@dataclass(frozen=True)
class LiveConfig:
    controller: str = "fixed_time"
    profile: str = "medium"
    seed: int = 0
    duration_s: float = 3600.0
    speed: float = 10.0  # simulated seconds per wall-clock second; 0 = as fast as possible
    scenario: str = "grid3x3"
    backend: str = "traci"  # SUMO in its own process: a crash cannot take the API down
    mission: PlannedMission | None = None
    incident: PlannedIncident | None = None

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
    def __init__(self, runs_dir: Path | None = None, on_run_closed=None):
        self.runs_dir = Path(runs_dir) if runs_dir else REPO_ROOT / "runs" / "live"
        self.on_run_closed = on_run_closed  # called with the run folder (store import)
        self._paused = threading.Event()
        self._published_mono = time.monotonic()
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
            self._paused.clear()
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

    def pause(self) -> dict:
        """FR-02: stop stepping SUMO; the run, its state and its commands stay alive."""
        if self.status != "running":
            raise CommandError(f"only a running run can be paused (status {self.status})")
        self._paused.set()
        return self.wait_for(lambda s: s["status"] in ("paused", "finished", "error"), 30.0)

    def resume(self) -> dict:
        if self.status != "paused":
            raise CommandError(f"the run is not paused (status {self.status})")
        self._paused.clear()
        return self.wait_for(lambda s: s["status"] != "paused", 30.0)

    def inject_fault(self, kind: str, timeout=60.0) -> dict:
        if kind not in FAULTS:
            raise ValueError(f"unknown fault {kind!r}; known: {FAULTS}")
        return self._call("fault", timeout, kind)

    def view(self) -> dict:
        """The latest state plus its age and the stale warning (FR-16)."""
        s = self._state
        age = time.monotonic() - self._published_mono
        out = {**s, "age_s": round(age, 2)}
        limit = STARTING_STALE_AFTER_S if s["status"] == "starting" else STALE_AFTER_S
        if s["status"] in ("starting", "running", "paused") and age > limit:
            out["warnings"] = [*s.get("warnings", []), {
                "code": "stale", "level": "error",
                "message": f"no new simulation state for {age:.1f} s (limit {limit:.0f} s);"
                           " the values shown are old",
            }]  # fmt: skip
        return out

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
        self._published_mono = time.monotonic()

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
                if self._paused.is_set():
                    run.pause_started()
                    self._publish(run.state("paused"))
                    while self._paused.is_set() and not self._stop.is_set():
                        self._stop.wait(PAUSED_PUBLISH_S)
                        self._run_commands(run)
                        self._publish(run.state("paused"))
                    run.pause_ended()
                    wall0, sim0 = time.perf_counter(), run.now  # pacing restarts after a pause
                    continue
                if run.finished:
                    break
                run.run_scheduled()
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
            run.pause_ended()
            run.close(status)
            self._publish(run.state(status))
        except Exception as exc:  # shown on the dashboard; the run folder keeps the trace
            lost = _is_disconnect(exc)
            if run is not None:
                if lost:
                    run.warn_once(
                        "disconnected",
                        "error",
                        f"lost the connection to SUMO: {type(exc).__name__}: {exc}",
                    )
                try:
                    run.close(f"error: {type(exc).__name__}: {exc}")
                except Exception:  # SUMO already gone; the summary may be incomplete
                    pass
            base = run.state("error") if run is not None else {"config": asdict(config)}
            if run is None and lost:
                base["warnings"] = [{"code": "disconnected", "level": "error",
                                     "message": f"could not reach SUMO: {exc}"}]  # fmt: skip
            self._publish({**base, "status": "error", "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc(limit=5)})  # fmt: skip
        finally:
            if run is not None and self.on_run_closed is not None:
                try:
                    self.on_run_closed(run.run_dir)
                except Exception as exc:  # the run folder is still there; import it later
                    print(f"store import of {run.run_dir} failed: {exc}")
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
                handler = {"dispatch": run.dispatch, "close": run.close_road,
                           "fault": run.inject_fault}[name]  # fmt: skip
                result = handler(*args)
                self._publish(run.state("paused" if self._paused.is_set() else "running"))
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
        self.started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.network_id = self.network.network_id
        self.demand_generator = "manzil.scenarios.demand (Poisson per entry road, numpy PCG64)"
        self.pauses: list[dict] = []
        self._pause_wall: float | None = None
        self.faults: list[dict] = []
        self.fallback_since: float | None = None
        self.warnings_seen: dict[str, dict] = {}  # code -> first warning (kept in summary.json)
        self._sticky: list[dict] = []  # warnings that stay until the run ends (disconnect)
        self.history: list[list] = []
        self.pending_mission = config.mission
        self.pending_incident = config.incident
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
        if self.fallback_since is None and self._fallbacks():
            self.fallback_since = now
        states = self.safety.tick(now, step)
        for tls, s in states.items():
            self.sim.set_signal_state(tls, s)
        self.monitor.observe(now, states, self.safety.owners())
        if int(now) % HISTORY_EVERY_S == 0:
            moving = [v[3] for k, v in self.sim.vehicle_positions.items()
                      if not k.startswith("ambulance")]  # fmt: skip
            self.history.append([
                now, snap.running, sum(e.halting for e in snap.edges.values()),
                snap.arrived_total, round(sum(moving) / len(moving), 2) if moving else None,
            ])  # fmt: skip

    def _fallbacks(self) -> int:
        return int(getattr(self.controller, "decisions", {}).get("fallback", 0) or 0)

    # ----- pause, schedule, faults (W5) -------------------------------------------------------
    def pause_started(self) -> None:
        if self._pause_wall is None:
            self._pause_wall = time.perf_counter()
            self.pauses.append({"sim_time_s": self.now, "wall_s": None})

    def pause_ended(self) -> None:
        if self._pause_wall is not None:
            self.pauses[-1]["wall_s"] = round(time.perf_counter() - self._pause_wall, 2)
            self._pause_wall = None

    def run_scheduled(self) -> None:
        """Apply the configured incident and mission when their time comes (G01)."""
        inc = self.pending_incident
        if inc is not None and self.now >= inc.time_s:
            self.pending_incident = None
            self.close_road(inc.edge_id)
        m = self.pending_mission
        if m is not None and self.now + 1 >= m.dispatch_s:
            self.pending_mission = None
            self.dispatch(m.origin, m.destination, m.corridor)

    def inject_fault(self, kind: str) -> dict:
        if kind == "rl_loss":
            if not hasattr(self.controller, "net"):
                raise CommandError("the rl_loss fault needs the DQN controller")
            if any(f["kind"] == kind for f in self.faults):
                raise CommandError("the RL service is already unavailable in this run")
            self.controller.net = _UnavailablePolicy()
        rec = {"kind": kind, "sim_time_s": self.now, "step": self.snap.effective_step,
               "note": "operator fault injection (W5): the DQN policy raises from now on, so"
                       " the controller's own FR-20 fallback holds the current phase"}  # fmt: skip
        self.faults.append(rec)
        return rec

    def warn_once(self, code: str, level: str, message: str) -> None:
        w = {"code": code, "level": level, "message": message, "since_s": self.now}
        self._sticky.append(w)
        self.warnings_seen.setdefault(code, w)

    def warnings(self) -> list[dict]:
        """FR-16 warnings computed from the real run state (``stale`` is added by the session)."""
        out = list(self._sticky)
        fb = self._fallbacks()
        if fb:
            cause = (f"fault injected at {self.faults[0]['sim_time_s']:.0f} s"
                     if self.faults else "the policy raised an error")  # fmt: skip
            out.append({"code": "fallback", "level": "error", "since_s": self.fallback_since,
                        "message": f"DQN unavailable ({cause}): {fb} decisions so far held the"
                                   " current legal phase (FR-20 safe fallback)"})  # fmt: skip
        if self.monitor.violations:
            out.append({"code": "invalid", "level": "error",
                        "message": f"safety monitor: {len(self.monitor.violations)} violation(s);"
                                   f" first: {self.monitor.violations[0]}"})  # fmt: skip
        if not self.snap.is_valid_at(self.snap.effective_step):
            msg = (f"snapshot schema {self.snap.schema_version} or validity"
                   f" (step {self.snap.valid_until_step}) does not match")  # fmt: skip
            out.append({"code": "invalid", "level": "error", "message": msg})
        for d in self.missions:
            if d.mission.status == "NO_ROUTE":
                out.append({"code": "invalid", "level": "warning",
                            "message": f"{d.vehicle_id}: no route from {d.config.origin} to"
                                       f" {d.config.destination} (NO_ROUTE); no corridor"
                                       " was activated"})  # fmt: skip
        for w in out:
            self.warnings_seen.setdefault(w["code"], {**w, "since_s": w.get("since_s", self.now)})
        return out

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
            "source_mode": snap.source_mode.value,
            "network_id": self.network_id,
            "produced_at": round(time.time(), 3),
            "effective_step": snap.effective_step,
            "sim_time_s": self.now,
            "end_s": self.rc.end_s,
            "warnings": self.warnings(),
            "pauses": self.pauses,
            "faults": self.faults,
            "controller_decisions": dict(getattr(self.controller, "decisions", {}) or {}),
            "history": self.history,
            "approaches": {
                tls: [
                    {
                        "approach_id": a.approach_id,
                        "count": a.count,
                        "queue": a.queue,
                        "wait_s": round(a.wait_s, 1),
                        "speed_mps": None if a.speed_mps is None else round(a.speed_mps, 2),
                        "occupancy_pct": round(a.occupancy_pct, 1),
                    }
                    for a in apps
                ]
                for tls, apps in snap.approaches.items()
            },  # fmt: skip
            "applied_controls": [
                {
                    "request_id": a.request_id,
                    "controller": a.controller_id,
                    "tls": a.intersection_id,
                    "requested_phase": a.requested_phase,
                    "applied_phase": a.applied_phase,
                    "effective_step": a.effective_step,
                    "intervention": a.safety_intervention,
                    "reason": a.reason,
                }
                for a in self.safety.applied[-60:]
            ],  # fmt: skip
            "scheduled": {
                "mission": asdict(self.pending_mission) if self.pending_mission else None,
                "incident": asdict(self.pending_incident) if self.pending_incident else None,
            },
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
                "started_at_utc": self.started_at,
                "network_id": self.network_id,
                "demand_generator": self.demand_generator,
                "versions": _versions(),
                "termination": termination,
                "pauses": self.pauses,
                "faults": self.faults,
                "controller_decisions": dict(getattr(self.controller, "decisions", {}) or {}),
                "warnings": list(self.warnings_seen.values()),
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


class _UnavailablePolicy:
    """Stands in for the DQN network after an ``rl_loss`` fault: every call fails, as a lost
    inference service would, so ``DQNController`` takes its FR-20 fallback path."""

    def __call__(self, *_a, **_k):
        raise RuntimeError("RL policy unavailable (fault injected by the operator)")


def _is_disconnect(exc: BaseException) -> bool:
    name = type(exc).__name__
    return name in ("FatalTraCIError", "TraCIException") or isinstance(
        exc, (ConnectionError, BrokenPipeError, EOFError)
    )


_VERSIONS: dict | None = None


def _versions() -> dict:
    global _VERSIONS
    if _VERSIONS is None:
        from manzil.experiments.runner import _git_commit
        from manzil.scenarios.grid import sumo_version

        try:
            sumo = sumo_version()
        except Exception:  # version lookup must never break a run summary
            sumo = None
        _VERSIONS = {"sumo": sumo, "git": _git_commit()}
    return _VERSIONS


def _jsonable(obj):
    """Replace infinities (closed-road costs) so the result is strict JSON."""
    if isinstance(obj, float) and obj in (float("inf"), float("-inf")):
        return None
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj
