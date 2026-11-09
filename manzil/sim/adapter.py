"""SimulationAdapter: the sole owner of SUMO stepping and signal actuation (PLAN task 1.3, FR-03).

No other Manzil module imports ``traci`` or ``libsumo``. Controllers receive snapshots and return
requests; the safety filter turns requests into signal states; only this adapter writes them
to SUMO.

Two backends with the same API:

- ``libsumo`` (default): SUMO runs inside the Python process; fastest; one instance per process.
- ``traci``: SUMO runs as a separate process over a socket; slower, but several runs can be open
  at once and it is what ``sumo-gui`` needs.
"""

from __future__ import annotations

import itertools
import time
from collections.abc import Sequence

from traci import constants as tc

from manzil.sim.contracts import (
    SCHEMA_VERSION,
    ApproachState,
    LaneState,
    SourceMode,
    TrafficSnapshot,
)
from manzil.sim.network import NetworkModel
from manzil.sumo_env import sumo_binary

LANE_VARS = (
    tc.LAST_STEP_VEHICLE_NUMBER,
    tc.LAST_STEP_VEHICLE_HALTING_NUMBER,
    tc.VAR_WAITING_TIME,
    tc.LAST_STEP_MEAN_SPEED,
    tc.LAST_STEP_OCCUPANCY,
)
SIM_VARS = (
    tc.VAR_ARRIVED_VEHICLES_NUMBER,
    tc.VAR_DEPARTED_VEHICLES_NUMBER,
)

# Options that keep SUMO quiet on the console (append to the start arguments).
QUIET_ARGS = ("--no-step-log", "true", "--no-warnings", "true")

_labels = itertools.count()


class SimulationAdapter:
    _libsumo_in_use = False

    def __init__(self, network: NetworkModel, backend: str = "libsumo", gui: bool = False):
        if backend not in ("libsumo", "traci"):
            raise ValueError(f"unknown backend {backend!r}")
        if gui and backend != "traci":
            raise ValueError("sumo-gui needs the traci backend")
        self.network = network
        self.backend = backend
        self.gui = gui
        self._conn = None
        self._step = 0
        self._arrived = 0
        self._departed = 0
        self._applied: dict[str, str] = {}
        self._snapshot: TrafficSnapshot | None = None
        self._lanes = sorted(
            {
                lane
                for x in network.intersections.values()
                for lane in (*x.incoming_lanes, *x.outgoing_lanes)
            }
        )

    # ----- lifecycle -------------------------------------------------------------------------
    def start(self, sumo_args: Sequence[str]) -> TrafficSnapshot:
        """Start SUMO with the given options (e.g. ``["-c", cfg, "--seed", "0"]``)."""
        if self._conn is not None:
            raise RuntimeError("simulation already running")
        cmd = [sumo_binary("sumo-gui" if self.gui else "sumo"), *sumo_args]
        if self.backend == "libsumo":
            if SimulationAdapter._libsumo_in_use:
                raise RuntimeError("libsumo allows one simulation per process; use traci")
            import libsumo

            libsumo.start(cmd)
            SimulationAdapter._libsumo_in_use = True
            self._conn = libsumo
        else:
            import traci

            label = f"manzil-{next(_labels)}"
            traci.start(cmd, label=label)
            self._conn = traci.getConnection(label)
        self._subscribe()
        self._step = 0
        self._snapshot = self._read_snapshot()
        return self._snapshot

    def stop(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        finally:
            if self.backend == "libsumo":
                SimulationAdapter._libsumo_in_use = False
            self._conn = None

    def __enter__(self) -> SimulationAdapter:
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    @property
    def running(self) -> bool:
        return self._conn is not None

    # ----- stepping and reading --------------------------------------------------------------
    def step(self) -> TrafficSnapshot:
        """Advance SUMO by one step and return the new snapshot."""
        self._require_running()
        self._conn.simulationStep()
        self._step += 1
        self._snapshot = self._read_snapshot()
        return self._snapshot

    @property
    def snapshot(self) -> TrafficSnapshot:
        if self._snapshot is None:
            raise RuntimeError("simulation not started")
        return self._snapshot

    @property
    def step_count(self) -> int:
        return self._step

    def sim_time(self) -> float:
        self._require_running()
        return self._conn.simulation.getTime()

    def expected_vehicles(self) -> int:
        """Vehicles still running or waiting to be inserted (0 once all demand has finished)."""
        self._require_running()
        return self._conn.simulation.getMinExpectedNumber()

    # ----- actuation -------------------------------------------------------------------------
    def set_signal_state(self, tls_id: str, state: str) -> bool:
        """Show ``state`` at ``tls_id``. Returns True if SUMO was actually changed."""
        self._require_running()
        x = self.network.intersections[tls_id]
        if len(state) != x.num_links:
            raise ValueError(f"{tls_id}: state length {len(state)} != {x.num_links} links")
        if self._applied.get(tls_id) == state:
            return False
        self._conn.trafficlight.setRedYellowGreenState(tls_id, state)
        self._applied[tls_id] = state
        return True

    # ----- internals -------------------------------------------------------------------------
    def _require_running(self) -> None:
        if self._conn is None:
            raise RuntimeError("simulation not running")

    def _subscribe(self) -> None:
        for lane in self._lanes:
            self._conn.lane.subscribe(lane, LANE_VARS)
        for tls in self.network.tls_ids:
            self._conn.trafficlight.subscribe(tls, (tc.TL_RED_YELLOW_GREEN_STATE,))
        self._conn.simulation.subscribe(SIM_VARS)
        self._arrived = 0
        self._departed = 0

    def _read_snapshot(self) -> TrafficSnapshot:
        conn = self._conn
        lane_res = conn.lane.getAllSubscriptionResults()
        lanes = {}
        for lane_id in self._lanes:
            r = lane_res[lane_id]
            lanes[lane_id] = LaneState(
                lane_id=lane_id,
                vehicles=int(r[tc.LAST_STEP_VEHICLE_NUMBER]),
                halting=int(r[tc.LAST_STEP_VEHICLE_HALTING_NUMBER]),
                waiting_time_s=float(r[tc.VAR_WAITING_TIME]),
                mean_speed_mps=float(r[tc.LAST_STEP_MEAN_SPEED]),
                occupancy_pct=float(r[tc.LAST_STEP_OCCUPANCY]) * 100.0,
            )
        tls_res = conn.trafficlight.getAllSubscriptionResults()
        signals = {t: tls_res[t][tc.TL_RED_YELLOW_GREEN_STATE] for t in self.network.tls_ids}
        sim = conn.simulation.getSubscriptionResults()
        self._arrived += int(sim[tc.VAR_ARRIVED_VEHICLES_NUMBER])
        self._departed += int(sim[tc.VAR_DEPARTED_VEHICLES_NUMBER])

        approaches = {
            tls: tuple(_approach_state(tls, a.edge_id, a.lanes, lanes) for a in x.approaches)
            for tls, x in self.network.intersections.items()
        }
        return TrafficSnapshot(
            schema_version=SCHEMA_VERSION,
            source_mode=SourceMode.SUMO,
            produced_at=time.time(),
            effective_step=self._step,
            sim_time_s=conn.simulation.getTime(),
            valid_until_step=self._step,
            network_id=self.network.network_id,
            lanes=lanes,
            signal_states=signals,
            arrived_total=self._arrived,
            departed_total=self._departed,
            running=conn.vehicle.getIDCount(),
            approaches=approaches,
        )


def _approach_state(tls, edge_id, lane_ids, lanes: dict[str, LaneState]) -> ApproachState:
    ls = [lanes[i] for i in lane_ids]
    count = sum(x.vehicles for x in ls)
    speed = sum(x.mean_speed_mps * x.vehicles for x in ls) / count if count else None
    return ApproachState(
        intersection_id=tls,
        approach_id=edge_id,
        count=count,
        queue=sum(x.halting for x in ls),
        wait_s=sum(x.waiting_time_s for x in ls),
        speed_mps=speed,
        occupancy_pct=sum(x.occupancy_pct for x in ls) / len(ls),
    )
