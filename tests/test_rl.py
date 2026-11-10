"""Phase 4: RL environment (4.1) and DQN controller (4.2). Skipped when torch is missing."""

import numpy as np
import pytest

from manzil.control.fixed_time import SignalTiming
from manzil.control.rl_env import (
    MAX_PHASES,
    OBS_SIZE,
    TrafficEnv,
    action_mask,
    build_layouts,
)
from manzil.scenarios.demand import DEFAULT_NET
from manzil.sim.contracts import SignalState

torch = pytest.importorskip("torch")

from manzil.control.dqn import DQNAgent, DQNParams, masked_argmax  # noqa: E402
from manzil.experiments.runner import RunConfig, run  # noqa: E402

TIMING = SignalTiming.load(DEFAULT_NET.parent / "signals.json")


def test_layouts_use_compass_order_and_fixed_size(grid_model):
    lays = build_layouts(grid_model)
    assert len(lays) == 9
    for lay in lays.values():
        assert len(lay.approaches) == 4 and lay.n_phases == 2


def test_action_mask_respects_min_green_and_transitions(grid_model):
    lay = build_layouts(grid_model)["B1"]
    early = SignalState("B1", "m", 0, 3.0, "", (0, 1))
    late = SignalState("B1", "m", 0, 12.0, "", (0, 1))
    moving = SignalState("B1", "m", None, 1.0, "", (1,), in_transition=True)
    assert action_mask(lay, early, 10).tolist() == [True, False, False, False]
    assert action_mask(lay, late, 10).tolist() == [True, True, False, False]
    assert action_mask(lay, moving, 10).tolist() == [False, True, False, False]


def test_random_policy_runs_safely(grid_model, tmp_path):
    """Task 4.1 done-when: a random policy runs safely through the safety filter."""
    env = TrafficEnv(grid_model, TIMING, work_dir=str(tmp_path))
    rng = np.random.default_rng(0)
    obs, masks = env.reset("heavy", 1000, 600)
    done, steps = False, 0
    while not done:
        acts = {t: int(rng.choice(np.flatnonzero(m))) for t, m in masks.items()}
        obs, masks, rew, done = env.step(acts)
        steps += 1
        assert all(o.shape == (OBS_SIZE,) and np.isfinite(o).all() for o in obs.values())
        assert all(r <= 0 for r in rew.values())  # every Eq 5.3 term is a cost
    assert steps == 120 and env.monitor.violations == []
    assert sum(e.kind == "yellow" for e in env.safety.events) > 50
    env.close()


def test_masked_argmax_never_picks_a_masked_action():
    q = torch.tensor([[5.0, 1.0, 9.0, 0.0]])
    mask = torch.tensor([[True, True, False, False]])
    assert masked_argmax(q, mask).item() == 0


def test_agent_learns_a_simple_contextual_bandit():
    """Sanity check: reward 1 for action = (first feature > 0), else 0."""
    agent = DQNAgent(DQNParams(warmup_transitions=64, batch=64, lr=1e-2, gamma=0.0,
                               target_sync=50), seed=0)  # fmt: skip
    rng = np.random.default_rng(0)
    mask = np.array([True, True, False, False])
    for _ in range(3000):
        o = rng.normal(size=OBS_SIZE).astype(np.float32)
        a = int(rng.integers(2))
        r = 1.0 if a == int(o[0] > 0) else 0.0
        agent.remember(o, a, r, o, mask, True)
    for _ in range(400):
        agent.learn()
    test = rng.normal(size=(200, OBS_SIZE)).astype(np.float32)
    acts = agent.act({i: test[i] for i in range(200)}, {i: mask for i in range(200)}, True)
    acc = np.mean([acts[i] == int(test[i, 0] > 0) for i in range(200)])
    assert acc > 0.9


def test_dqn_controller_runs_through_the_runner(tmp_path):
    ck = tmp_path / "untrained.pt"
    DQNAgent(seed=1).save(ck, {"note": "untrained, for the test"})
    r = run(RunConfig(controller="dqn", checkpoint=str(ck), profile="light", warmup_s=60,
                      measure_s=240), tmp_path / "run")  # fmt: skip
    assert r.manifest["termination"] == "completed"
    assert r.metrics["safety_violations"] == 0
    assert r.metrics["controller_decisions"]["greedy"] > 0
    assert r.manifest["controller"]["training"]["note"] == "untrained, for the test"


def test_mismatched_checkpoint_rejected(tmp_path):
    from manzil.control.dqn import load_qnet

    ck = tmp_path / "bad.pt"
    torch.save({"obs_size": OBS_SIZE + 1, "max_phases": MAX_PHASES}, ck)
    with pytest.raises(ValueError, match="layout"):
        load_qnet(ck)
