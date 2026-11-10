"""Data contracts passed between modules (D2 Table 6.3), as plain dataclasses.

Field names follow Python naming; their meaning follows D2. ``SCHEMA_VERSION`` is bumped whenever
a field's meaning changes, and consumers reject snapshots with an unknown version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = 1


class SourceMode(str, Enum):
    SUMO = "sumo"  # exact simulator state
    VIDEO = "video"  # perception output (separate evidence path, never mixed with SUMO)


class Owner(str, Enum):
    NORMAL = "NORMAL"
    CORRIDOR = "CORRIDOR"


@dataclass(frozen=True)
class LaneState:
    """Simulator values for one lane in the last step. Units: vehicles, s, m/s, percent."""

    lane_id: str
    vehicles: int
    halting: int  # vehicles slower than 0.1 m/s: SUMO's queue measure
    waiting_time_s: float  # summed waiting time of vehicles currently on the lane
    mean_speed_mps: float
    occupancy_pct: float


@dataclass(frozen=True)
class EdgeState:
    """Simulator values for one road edge (all lanes) in the last step."""

    edge_id: str
    vehicles: int
    halting: int
    mean_speed_mps: float


@dataclass(frozen=True)
class VehicleState:
    """A tracked vehicle (the ambulance). ``edge_id`` starts with ':' inside a junction."""

    vehicle_id: str
    edge_id: str
    lane_id: str
    position_m: float
    speed_mps: float
    waiting_time_s: float  # current continuous standstill
    route_index: int


@dataclass(frozen=True)
class ApproachState:
    intersection_id: str
    approach_id: str  # incoming edge id
    count: int
    queue: int
    wait_s: float
    speed_mps: float | None  # None when the approach is empty: missing is not zero
    occupancy_pct: float
    units: str = "veh, veh, s, m/s, %"
    confidence: float = 1.0  # simulator values are exact


@dataclass(frozen=True)
class SignalState:
    intersection_id: str
    program_id: str
    phase_id: int | None  # current green phase index, None during yellow / all-red
    phase_elapsed_s: float
    state: str  # the SUMO red/yellow/green string currently shown
    legal_next: tuple[int, ...]
    owner: Owner = Owner.NORMAL
    in_transition: bool = False


@dataclass(frozen=True)
class TrafficSnapshot:
    schema_version: int
    source_mode: SourceMode
    produced_at: float  # wall-clock time (diagnostics only)
    effective_step: int
    sim_time_s: float
    valid_until_step: int
    network_id: str
    lanes: dict[str, LaneState]
    signal_states: dict[str, str]  # tls id -> state string read back from SUMO
    arrived_total: int  # vehicles that have reached their destination so far
    departed_total: int
    running: int
    approaches: dict[str, tuple[ApproachState, ...]] = field(default_factory=dict)
    edges: dict[str, EdgeState] = field(default_factory=dict)
    tracked: dict[str, VehicleState] = field(default_factory=dict)  # tracked vehicles en route
    arrived_ids: tuple[str, ...] = ()  # vehicles that arrived in the last step

    def is_valid_at(self, step: int) -> bool:
        return self.schema_version == SCHEMA_VERSION and step <= self.valid_until_step


@dataclass(frozen=True)
class ControlRequest:
    """A controller's wish. It has no side effect; the safety filter may reject or change it."""

    controller_id: str
    intersection_id: str
    requested_phase: int
    snapshot_step: int
    reason: str = ""
    request_id: int = -1  # assigned by the safety filter


@dataclass(frozen=True)
class AppliedControl:
    """What the safety filter actually did with a request. Authoritative for analysis."""

    request_id: int
    controller_id: str
    intersection_id: str
    requested_phase: int
    applied_phase: int | None  # green phase that is (or will be) shown; None if rejected
    effective_step: int
    safety_intervention: str  # "none", "min_green_hold", "in_transition", "invalid_phase"
    reason: str


@dataclass(frozen=True)
class SignalEvent:
    """One change of the shown signal state, as enacted by the adapter."""

    step: int
    sim_time_s: float
    intersection_id: str
    kind: str  # "green", "yellow", "all_red"
    phase_id: int | None
    state: str
    owner: Owner
