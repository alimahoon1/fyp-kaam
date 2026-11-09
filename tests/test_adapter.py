"""Task 1.3: the SimulationAdapter steps SUMO, reads state, applies signals, and is sole owner."""

import re
from pathlib import Path

import pytest

from manzil.sim.adapter import QUIET_ARGS as SUMO_QUIET
from manzil.sim.adapter import SimulationAdapter
from manzil.sim.contracts import SCHEMA_VERSION, SourceMode


def _run(model, cfg, backend, steps):
    with SimulationAdapter(model, backend) as sim:
        sim.start(["-c", str(cfg), *SUMO_QUIET])
        for _ in range(steps):
            snap = sim.step()
        return snap


def test_steps_and_reads_state(grid_model, light_cfg):
    snap = _run(grid_model, light_cfg, "libsumo", 300)
    assert snap.schema_version == SCHEMA_VERSION
    assert snap.source_mode is SourceMode.SUMO
    assert snap.effective_step == 300 and snap.sim_time_s == 300.0
    assert snap.departed_total > 0 and snap.arrived_total > 0
    assert snap.network_id == grid_model.network_id
    assert set(snap.signal_states) == set(grid_model.tls_ids)
    assert set(snap.approaches) == set(grid_model.tls_ids)
    for approaches in snap.approaches.values():
        assert len(approaches) == 4
        for a in approaches:
            assert a.queue <= a.count
            assert (a.speed_mps is None) == (a.count == 0)  # missing is not zero


def test_both_backends_agree(grid_model, light_cfg):
    a = _run(grid_model, light_cfg, "libsumo", 200)
    b = _run(grid_model, light_cfg, "traci", 200)
    assert (a.departed_total, a.arrived_total, a.running) == (
        b.departed_total,
        b.arrived_total,
        b.running,
    )
    assert a.lanes == b.lanes


def test_applies_signal_state(grid_model, light_cfg):
    tls = grid_model.tls_ids[0]
    n = grid_model.intersections[tls].num_links
    with SimulationAdapter(grid_model) as sim:
        sim.start(["-c", str(light_cfg), *SUMO_QUIET])
        assert sim.set_signal_state(tls, "r" * n) is True
        assert sim.set_signal_state(tls, "r" * n) is False  # unchanged: no SUMO call
        assert sim.step().signal_states[tls] == "r" * n
        with pytest.raises(ValueError):
            sim.set_signal_state(tls, "r" * (n - 1))


def test_one_libsumo_instance_per_process(grid_model, light_cfg):
    with SimulationAdapter(grid_model) as first:
        first.start(["-c", str(light_cfg), *SUMO_QUIET])
        with pytest.raises(RuntimeError):
            SimulationAdapter(grid_model).start(["-c", str(light_cfg)])
    # After stopping, a new run can start.
    with SimulationAdapter(grid_model) as again:
        again.start(["-c", str(light_cfg), *SUMO_QUIET])
        assert again.step().effective_step == 1


def test_adapter_is_sole_owner_of_sumo():
    """FR-03: no module other than the adapter imports traci or libsumo."""
    pkg = Path(__file__).resolve().parents[1] / "manzil"
    pattern = re.compile(r"^\s*(import|from)\s+(traci|libsumo)\b", re.MULTILINE)
    offenders = [
        str(p.relative_to(pkg))
        for p in pkg.rglob("*.py")
        if p.name != "adapter.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
