"""Deterministic, auditable fallback simulation for the Manzil prototype.

This module deliberately keeps the same ownership boundaries proposed for a
future SUMO/TraCI adapter. It is not a traffic-engineering replacement for SUMO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import random
from typing import Dict, List, Optional

from .network import ADJACENCY, EDGES, NODES


CONTROLLERS = ("fixed", "adaptive", "q_learning")
SCENARIOS = ("balanced", "north_pressure", "rush_hour")


@dataclass
class Signal:
    phase: str = "EW"
    elapsed: int = 0
    clearance_remaining: int = 0
    pending_phase: Optional[str] = None
    owner: str = "NORMAL"


@dataclass
class Mission:
    id: str
    origin: str
    destination: str
    route: List[str]
    route_version: int = 1
    status: str = "ACTIVE"
    progress: float = 0.0
    travel_steps: int = 0
    reroutes: int = 0
    stops: int = 0
    last_blocked: bool = False

    @property
    def current_node(self) -> str:
        return self.route[0]


@dataclass
class Engine:
    seed: int = 104
    scenario: str = "balanced"
    controller: str = "adaptive"
    step_number: int = 0
    running: bool = False
    signals: Dict[str, Signal] = field(default_factory=dict)
    queues: Dict[str, Dict[str, float]] = field(default_factory=dict)
    closed_edges: set = field(default_factory=set)
    events: List[dict] = field(default_factory=list)
    mission: Optional[Mission] = None
    corridor: Dict[str, str] = field(default_factory=dict)
    throughput: int = 0
    total_wait: float = 0.0
    completed_travel_time: float = 0.0
    fallback_interventions: int = 0

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        if self.scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {self.scenario}")
        if self.controller not in CONTROLLERS:
            raise ValueError(f"Unknown controller: {self.controller}")
        if not self.signals:
            self.signals = {node: Signal(phase="EW" if i % 2 == 0 else "NS") for i, node in enumerate(NODES)}
        if not self.queues:
            self.queues = {node: {"EW": 2.0 + (i % 3), "NS": 2.0 + ((i + 1) % 3)} for i, node in enumerate(NODES)}
        self._event("SYSTEM", "Prototype simulation initialized", source="prototype-sim")

    def _event(self, kind: str, message: str, **details):
        self.events.append({"step": self.step_number, "kind": kind, "message": message, **details})
        self.events = self.events[-80:]

    def reset(self, seed: Optional[int] = None, scenario: Optional[str] = None, controller: Optional[str] = None):
        fresh = Engine(seed=seed if seed is not None else self.seed,
                       scenario=scenario or self.scenario,
                       controller=controller or self.controller)
        self.__dict__.update(fresh.__dict__)
        return self.snapshot()

    def set_controller(self, controller: str):
        if controller not in CONTROLLERS:
            raise ValueError("Unsupported controller")
        self.controller = controller
        self._event("CONTROLLER", f"Controller changed to {controller}")

    def _arrivals(self, node: str, direction: str) -> float:
        base = {"balanced": 0.72, "north_pressure": 0.72, "rush_hour": 1.18}[self.scenario]
        if self.scenario == "north_pressure" and direction == "NS":
            base *= 1.7
        node_factor = 0.86 + (list(NODES).index(node) % 3) * 0.08
        return base * node_factor + self.rng.random() * 0.48

    def _normal_request(self, node: str) -> str:
        signal = self.signals[node]
        if self.controller == "fixed":
            return "EW" if (self.step_number // 10) % 2 == 0 else "NS"
        ew, ns = self.queues[node]["EW"], self.queues[node]["NS"]
        if self.controller == "adaptive":
            # Pressure-inspired local proxy with an elapsed-time fairness term.
            ew_score = ew + (1.2 if signal.phase != "EW" and signal.elapsed > 8 else 0)
            ns_score = ns + (1.2 if signal.phase != "NS" and signal.elapsed > 8 else 0)
            return "EW" if ew_score >= ns_score else "NS"
        # Labelled tabular-Q prototype: a compact frozen policy over queue imbalance.
        imbalance = ew - ns
        if imbalance > 1.5:
            return "EW"
        if imbalance < -1.5:
            return "NS"
        return signal.phase

    def _apply_safe_request(self, node: str, requested: str, owner: str = "NORMAL"):
        signal = self.signals[node]
        if requested not in ("EW", "NS"):
            self.fallback_interventions += 1
            requested = signal.phase
        if signal.clearance_remaining:
            signal.clearance_remaining -= 1
            signal.elapsed += 1
            if signal.clearance_remaining == 0 and signal.pending_phase:
                signal.phase = signal.pending_phase
                signal.pending_phase = None
                signal.elapsed = 0
                signal.owner = owner
            return
        if requested != signal.phase and signal.elapsed >= 4:
            signal.pending_phase = requested
            signal.clearance_remaining = 1
            signal.owner = owner
            self._event("SIGNAL", f"{node} entered safe clearance", requested=requested, owner=owner)
        else:
            signal.elapsed += 1
            if owner == "CORRIDOR":
                signal.owner = owner

    def edge_cost(self, edge: dict) -> float:
        if edge["id"] in self.closed_edges:
            return float("inf")
        target_queue = self.queues[edge["target"]][edge["direction"]]
        signal = self.signals[edge["target"]]
        residual = 0 if signal.phase == edge["direction"] and not signal.clearance_remaining else 4
        return edge["freeFlowSeconds"] + target_queue * 0.8 + residual

    def shortest_path(self, origin: str, destination: str) -> tuple[List[str], float]:
        if origin not in NODES or destination not in NODES:
            raise ValueError("Origin and destination must be valid intersections")
        heap = [(0.0, origin, [origin])]
        best = {origin: 0.0}
        while heap:
            cost, node, path = heapq.heappop(heap)
            if node == destination:
                return path, round(cost, 2)
            if cost > best.get(node, float("inf")):
                continue
            for edge in ADJACENCY[node]:
                value = self.edge_cost(edge)
                if value == float("inf"):
                    continue
                new_cost = cost + value
                if new_cost < best.get(edge["target"], float("inf")):
                    best[edge["target"]] = new_cost
                    heapq.heappush(heap, (new_cost, edge["target"], path + [edge["target"]]))
        return [], float("inf")

    def dispatch(self, origin: str, destination: str):
        if self.mission and self.mission.status == "ACTIVE":
            raise ValueError("Only one active ambulance mission is supported")
        route, cost = self.shortest_path(origin, destination)
        if not route:
            raise ValueError("No valid route is available")
        self.mission = Mission(id=f"EV-{self.step_number + 1:03d}", origin=origin,
                               destination=destination, route=route)
        self._event("MISSION", "Ambulance dispatched", route=route, costSeconds=cost, routeVersion=1)
        self._refresh_corridor()
        return self.snapshot()

    def set_closure(self, edge_id: str, closed: bool = True):
        if edge_id not in EDGES:
            raise ValueError("Unknown edge")
        reverse = f"{EDGES[edge_id]['target']}>{EDGES[edge_id]['source']}"
        for candidate in (edge_id, reverse):
            if closed:
                self.closed_edges.add(candidate)
            else:
                self.closed_edges.discard(candidate)
        self._event("INCIDENT", f"Road {'closed' if closed else 'reopened'}", edge=edge_id)
        if closed:
            self._consider_reroute(force_if_blocked=True)

    def _refresh_corridor(self):
        if not self.mission or self.mission.status != "ACTIVE":
            self.corridor = {}
            return
        wanted = self.mission.route[1:3]
        self.corridor = {node: self.corridor.get(node, "REQUESTED") for node in wanted}
        if wanted:
            self.corridor[wanted[0]] = "ACTIVE_PRIORITY"

    def _consider_reroute(self, force_if_blocked: bool = False):
        mission = self.mission
        if not mission or mission.status != "ACTIVE" or len(mission.route) < 2:
            return
        remaining = mission.route
        blocked = any(f"{a}>{b}" in self.closed_edges for a, b in zip(remaining, remaining[1:]))
        candidate, candidate_cost = self.shortest_path(mission.current_node, mission.destination)
        if not candidate:
            mission.status = "BLOCKED"
            self.corridor = {}
            self._event("MISSION", "No route remains; corridor cancelled", routeVersion=mission.route_version)
            return
        current_cost = 0.0
        for a, b in zip(remaining, remaining[1:]):
            current_cost += self.edge_cost(EDGES[f"{a}>{b}"])
        improved = current_cost - candidate_cost > 5.0
        if (blocked and force_if_blocked) or improved:
            if candidate != remaining:
                old = remaining[:]
                mission.route = candidate
                mission.route_version += 1
                mission.reroutes += 1
                mission.progress = 0.0
                self._event("REROUTE", "Route revised and obsolete priority cancelled",
                            oldRoute=old, route=candidate, routeVersion=mission.route_version,
                            reason="closure" if blocked else "sustained improvement")
                self._refresh_corridor()

    def _advance_mission(self):
        mission = self.mission
        if not mission or mission.status != "ACTIVE":
            return
        mission.travel_steps += 1
        if len(mission.route) == 1:
            mission.status = "ARRIVED"
            self.corridor = {}
            self._event("MISSION", "Ambulance arrived at destination", travelSteps=mission.travel_steps)
            return
        source, target = mission.route[0], mission.route[1]
        edge = EDGES[f"{source}>{target}"]
        if edge["id"] in self.closed_edges:
            mission.stops += 1
            self._consider_reroute(force_if_blocked=True)
            return
        signal = self.signals[target]
        requested = edge["direction"]
        self._apply_safe_request(target, requested, owner="CORRIDOR")
        can_move = signal.phase == requested and signal.clearance_remaining == 0
        if can_move:
            mission.progress += 0.28
        else:
            mission.stops += 1
        if mission.progress >= 1.0:
            passed = mission.route.pop(0)
            mission.progress = 0.0
            if target in self.corridor:
                self.corridor[target] = "PASSAGE"
            self.signals[target].owner = "NORMAL"
            self._event("CORRIDOR", f"Ambulance passed {target}; normal control restored", intersection=target)
            self._refresh_corridor()
        elif mission.travel_steps % 8 == 0:
            self._consider_reroute()

    def step(self, count: int = 1):
        count = max(1, min(int(count), 500))
        self.running = True
        for _ in range(count):
            self.step_number += 1
            for node in NODES:
                for direction in ("EW", "NS"):
                    self.queues[node][direction] += self._arrivals(node, direction)
                request = self._normal_request(node)
                if node not in self.corridor or self.corridor[node] not in ("ACTIVE_PRIORITY", "SAFE_TRANSITION"):
                    self._apply_safe_request(node, request)
                signal = self.signals[node]
                if not signal.clearance_remaining:
                    served = min(self.queues[node][signal.phase], 2.15)
                    self.queues[node][signal.phase] -= served
                    self.throughput += int(served)
                    self.completed_travel_time += served * (7 + self.queues[node][signal.phase] * 0.3)
                self.total_wait += self.queues[node]["EW"] + self.queues[node]["NS"]
            self._advance_mission()
        self.running = False
        return self.snapshot()

    def perception_snapshot(self):
        values = []
        for index, (node, queues) in enumerate(self.queues.items()):
            observed = round(max(0.0, sum(queues.values()) + ((self.step_number + index) % 3 - 1) * 0.6), 1)
            values.append({
                "intersectionId": node,
                "vehicleCount": observed,
                "queueProxy": round(observed * 0.72, 1),
                "occupancy": round(min(0.95, observed / 30), 2),
                "confidence": round(0.82 + (index % 3) * 0.04, 2),
                "unit": "vehicles/proxy",
            })
        return {
            "sourceMode": "mock-perception",
            "effectiveStep": self.step_number,
            "validUntil": self.step_number + 3,
            "calibrated": False,
            "notice": "Synthetic observations demonstrate the perception contract; no YOLO inference is running.",
            "observations": values,
        }

    def snapshot(self):
        total_queue = sum(sum(value.values()) for value in self.queues.values())
        mission = None
        if self.mission:
            mission = {
                "id": self.mission.id, "origin": self.mission.origin,
                "destination": self.mission.destination, "route": self.mission.route,
                "routeVersion": self.mission.route_version, "status": self.mission.status,
                "progress": round(self.mission.progress, 2), "travelSteps": self.mission.travel_steps,
                "reroutes": self.mission.reroutes, "stops": self.mission.stops,
            }
        return {
            "schemaVersion": "1.0",
            "sourceMode": "prototype-sim",
            "step": self.step_number,
            "running": self.running,
            "seed": self.seed,
            "scenario": self.scenario,
            "controller": self.controller,
            "nodes": [{"id": key, **value, "queues": {k: round(v, 1) for k, v in self.queues[key].items()},
                       "signal": {"phase": self.signals[key].phase,
                                  "displayPhase": "CLEARANCE" if self.signals[key].clearance_remaining else self.signals[key].phase,
                                  "elapsed": self.signals[key].elapsed,
                                  "owner": self.signals[key].owner}}
                      for key, value in NODES.items()],
            "edges": [{**edge, "closed": edge["id"] in self.closed_edges,
                       "costSeconds": None if self.edge_cost(edge) == float("inf") else round(self.edge_cost(edge), 1)}
                      for edge in EDGES.values() if edge["source"] < edge["target"]],
            "corridor": self.corridor,
            "mission": mission,
            "metrics": {
                "totalQueue": round(total_queue, 1),
                "meanQueue": round(total_queue / (len(NODES) * 2), 2),
                "meanWaitProxy": round(self.total_wait / max(1, self.step_number * len(NODES) * 2), 2),
                "throughput": self.throughput,
                "fallbackInterventions": self.fallback_interventions,
            },
            "events": list(reversed(self.events[-20:])),
        }


def compare_controllers(seed: int = 104, scenario: str = "rush_hour", steps: int = 120):
    results = []
    for controller in CONTROLLERS:
        engine = Engine(seed=seed, scenario=scenario, controller=controller)
        engine.step(steps)
        metrics = engine.snapshot()["metrics"]
        results.append({"controller": controller, **metrics, "steps": steps, "seed": seed, "scenario": scenario})
    return {
        "schemaVersion": "1.0",
        "sourceMode": "prototype-sim",
        "comparisonType": "matched-seed prototype comparison",
        "warning": "These fallback-simulator results are not SUMO or academic evaluation results.",
        "results": results,
    }
