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
    EdgeState,
    LaneState,
    SourceMode,
    TrafficSnapshot,
    VehicleState,
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
EDGE_VARS = (
    tc.LAST_STEP_VEHICLE_NUMBER,
    tc.LAST_STEP_VEHICLE_HALTING_NUMBER,
    tc.LAST_STEP_MEAN_SPEED,
)
VEHICLE_VARS = (
    tc.VAR_ROAD_ID,
    tc.VAR_LANE_ID,
    tc.VAR_LANEPOSITION,
    tc.VAR_SPEED,
    tc.VAR_WAITING_TIME,
    tc.VAR_ROUTE_INDEX,
    tc.VAR_POSITION,
    tc.VAR_ANGLE,
)
# Background vehicles, only when positions are tracked (the live dashboard map).
POSITION_VARS = (tc.VAR_POSITION, tc.VAR_ANGLE, tc.VAR_SPEED)
SIM_VARS = (
    tc.VAR_ARRIVED_VEHICLES_IDS,
    tc.VAR_DEPARTED_VEHICLES_IDS,
)
AMBULANCE_TYPE = "ambulance"

# Options that keep SUMO quiet on the console (append to the start arguments).
QUIET_ARGS = ("--no-step-log", "true", "--no-warnings", "true")

_labels = itertools.count()


class SimulationAdapter:
    _libsumo_in_use = False

    def __init__(
        self,
        network: NetworkModel,
        backend: str = "libsumo",
        gui: bool = False,
        track_positions: bool = False,
    ):
        if backend not in ("libsumo", "traci"):
            raise ValueError(f"unknown backend {backend!r}")
        if gui and backend != "traci":
            raise ValueError("sumo-gui needs the traci backend")
        self.network = network
        self.backend = backend
        self.gui = gui
        self.track_positions = track_positions  # x/y of every vehicle (for a live map)
        self._positions: dict[str, tuple[float, float, float, float]] = {}
        self._conn = None
        self._step = 0
        self._arrived = 0
        self._departed = 0
        self._applied: dict[str, str] = {}
        self._snapshot: TrafficSnapshot | None = None
        self._tracked: set[str] = set()
        self._closed: set[str] = set()
        self._speed_limits: dict[str, float] = {}
        self._edges = sorted(e.getID() for e in network.net.getEdges())
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
    def vehicle_positions(self) -> dict[str, tuple[float, float, float, float]]:
        """vehicle id -> (x m, y m, angle deg, speed m/s) after the last step. Empty unless the
        adapter was created with ``track_positions=True`` (only the dashboard needs it)."""
        return dict(self._positions)

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

    # ----- vehicles and incidents -------------------------------------------------------------
    def add_ambulance_type(self, color=(255, 255, 255, 255)) -> str:
        """An ambulance that obeys signals: vClass ``emergency``, no blue-light device (D11)."""
        self._require_running()
        vt = self._conn.vehicletype
        if AMBULANCE_TYPE not in vt.getIDList():
            vt.copy("DEFAULT_VEHTYPE", AMBULANCE_TYPE)
            vt.setVehicleClass(AMBULANCE_TYPE, "emergency")
            vt.setShapeClass(AMBULANCE_TYPE, "emergency")
            vt.setColor(AMBULANCE_TYPE, color)
            vt.setImperfection(AMBULANCE_TYPE, 0.0)  # deterministic driver (sigma = 0)
            vt.setSpeedFactor(AMBULANCE_TYPE, 1.0)
        return AMBULANCE_TYPE

    def add_vehicle(self, vehicle_id: str, edges: Sequence[str], type_id: str) -> None:
        """Insert a vehicle now on the given route and track its state in every snapshot."""
        self._require_running()
        route_id = f"route_{vehicle_id}"
        self._conn.route.add(route_id, list(edges))
        self._conn.vehicle.add(
            vehicle_id, route_id, typeID=type_id, depart="now", departLane="best",
            departSpeed="max",
        )  # fmt: skip
        self._conn.vehicle.subscribe(vehicle_id, VEHICLE_VARS)
        self._tracked.add(vehicle_id)

    def set_route(self, vehicle_id: str, edges: Sequence[str]) -> None:
        """Replace a vehicle's route; ``edges[0]`` must be the edge it is on."""
        self._require_running()
        self._conn.vehicle.setRoute(vehicle_id, list(edges))

    def vehicle_route(self, vehicle_id: str) -> tuple[str, ...]:
        self._require_running()
        return tuple(self._conn.vehicle.getRoute(vehicle_id))

    def close_edge(self, edge_id: str) -> int:
        """Hard closure: no vehicle may enter. Background vehicles that would use the edge are
        rerouted by SUMO's own router; tracked vehicles (the ambulance) are left to Manzil.
        Returns the number of vehicles rerouted now."""
        self._require_running()
        for lane in self.network.net.getEdge(edge_id).getLanes():
            self._conn.lane.setDisallowed(lane.getID(), ["all"])
        self._closed.add(edge_id)
        return self._reroute_around_closures(self._conn.vehicle.getIDList())

    def slow_edge(self, edge_id: str, speed_mps: float) -> None:
        """Obstruction: lower the speed limit on every lane of the edge."""
        self._require_running()
        for lane in self.network.net.getEdge(edge_id).getLanes():
            self._conn.lane.setMaxSpeed(lane.getID(), speed_mps)
        self._speed_limits[edge_id] = speed_mps

    @property
    def closed_edges(self) -> frozenset[str]:
        return frozenset(self._closed)

    @property
    def speed_limits(self) -> dict[str, float]:
        """Edges whose speed limit was lowered by an incident (edge -> m/s)."""
        return dict(self._speed_limits)

    def _reroute_around_closures(self, vehicle_ids) -> int:
        n = 0
        for vid in vehicle_ids:
            if vid in self._tracked:
                continue
            v = self._conn.vehicle
            route, idx = v.getRoute(vid), v.getRouteIndex(vid)
            if any(e in self._closed for e in route[max(idx, 0) + 1 :]):
                v.rerouteTraveltime(vid)
                n += 1
        return n

    # ----- internals -------------------------------------------------------------------------
    def _require_running(self) -> None:
        if self._conn is None:
            raise RuntimeError("simulation not running")

    def _subscribe(self) -> None:
        for lane in self._lanes:
            self._conn.lane.subscribe(lane, LANE_VARS)
        for tls in self.network.tls_ids:
            self._conn.trafficlight.subscribe(tls, (tc.TL_RED_YELLOW_GREEN_STATE,))
        for edge in self._edges:
            self._conn.edge.subscribe(edge, EDGE_VARS)
        self._conn.simulation.subscribe(SIM_VARS)
        self._tracked = set()
        self._closed = set()
        self._speed_limits = {}
        self._positions = {}
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
        arrived_ids = tuple(sim[tc.VAR_ARRIVED_VEHICLES_IDS])
        departed_ids = sim[tc.VAR_DEPARTED_VEHICLES_IDS]
        self._arrived += len(arrived_ids)
        self._departed += len(departed_ids)
        if self._closed and departed_ids:  # new vehicles may have routes through a closure
            self._reroute_around_closures(departed_ids)
        if self.track_positions:
            for vid in departed_ids:
                if vid not in self._tracked:
                    conn.vehicle.subscribe(vid, POSITION_VARS)
        edge_res = conn.edge.getAllSubscriptionResults()
        edges = {
            e: EdgeState(
                e,
                int(r[tc.LAST_STEP_VEHICLE_NUMBER]),
                int(r[tc.LAST_STEP_VEHICLE_HALTING_NUMBER]),
                float(r[tc.LAST_STEP_MEAN_SPEED]),
            )
            for e, r in edge_res.items()
        }
        tracked = {}
        veh_res = conn.vehicle.getAllSubscriptionResults()
        if self.track_positions:
            self._positions = {
                vid: (*r[tc.VAR_POSITION], float(r[tc.VAR_ANGLE]), float(r[tc.VAR_SPEED]))
                for vid, r in veh_res.items()
                if tc.VAR_POSITION in r and vid not in arrived_ids
            }
        for vid in list(self._tracked):
            if vid in arrived_ids:
                self._tracked.discard(vid)
                continue
            r = veh_res.get(vid)
            if r:
                tracked[vid] = VehicleState(
                    vid,
                    r[tc.VAR_ROAD_ID],
                    r[tc.VAR_LANE_ID],
                    float(r[tc.VAR_LANEPOSITION]),
                    float(r[tc.VAR_SPEED]),
                    float(r[tc.VAR_WAITING_TIME]),
                    int(r[tc.VAR_ROUTE_INDEX]),
                )

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
            edges=edges,
            tracked=tracked,
            arrived_ids=arrived_ids,
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
