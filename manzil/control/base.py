"""The one controller interface every signal controller implements (D2 NFR-09)."""

from __future__ import annotations

from typing import Protocol

from manzil.control.safety import SafetyConfig
from manzil.sim.contracts import ControlRequest, SignalState, TrafficSnapshot
from manzil.sim.network import NetworkModel


class Controller(Protocol):
    controller_id: str

    def reset(self, network: NetworkModel, safety: SafetyConfig) -> dict[str, int]:
        """Prepare for a new run; return the initial green phase per intersection."""
        ...

    def decide(
        self, snapshot: TrafficSnapshot, signals: dict[str, SignalState]
    ) -> list[ControlRequest]:
        """Return phase requests for this step. Requests have no side effects."""
        ...

    def describe(self) -> dict:
        """Parameters for the run manifest."""
        ...
