"""DQN training for the W3 robustness study: several training seeds and a fairness variant.

Same agent, observation, action mask, episode length, checkpoint-selection rule and dev seeds as
Phase 4 (``manzil.experiments.train_dqn``); only two things can change:

- the **training seed** ``k``: agent initialisation, exploration, the order of training
  profiles, and the training demand seeds ``1000 + 1000 k + episode``. ``k = 0`` reproduces the
  Phase 4 setting (demand seeds 1001..1200), whose checkpoint ``models/dqn/grid3x3/best.pt`` is
  kept unchanged and used as training seed 0;
- the **reward variant**: ``base`` is Eq 5.3 as in Phase 4; ``fair`` is the fairness variant
  fixed before any evaluation: the starvation term fires when a phase has been red for more
  than 60 s instead of 90 s (same weight c = 2). In Phase 4 the 90 s term almost never fired,
  because the safety filter already forces a switch at 85 s, while the DQN's max red was
  62-76 s; at 60 s the term is active in exactly that range.

Training uses only ``PROFILES`` (light, medium, heavy, uneven); held-out profiles
(``HELDOUT_PROFILES``) and evaluation seeds are never seen here.

Usage::

    python -m manzil.experiments.protocol_train --seed 1 --variant base \\
        --out models/dqn/grid3x3_base_s1
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics as st
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from manzil.control.dqn import DQNAgent, DQNParams
from manzil.control.fixed_time import SignalTiming
from manzil.control.rl_env import RewardParams, TrafficEnv
from manzil.experiments.batch import run_batch, write_table
from manzil.experiments.train_dqn import (
    DEV_SEEDS,
    REWARD_SCALE,
    dev_runs,
    per_profile,
    plot_curve,
    selection_score,
)
from manzil.scenarios.demand import DEFAULT_NET, PROFILES
from manzil.sim.network import NetworkModel

REWARD_VARIANTS: dict[str, RewardParams] = {
    "base": RewardParams(),
    "fair": RewardParams(max_red_s=60.0),
}
TRAINING_PROFILES = tuple(sorted(PROFILES))


def demand_seed(train_seed: int, episode: int) -> int:
    """Training demand seed; disjoint from dev seeds (100-101) and evaluation seeds (< 1000)."""
    return 1000 + 1000 * train_seed + episode


def train(
    out: Path,
    seed: int = 0,
    variant: str = "base",
    episodes: int = 200,
    episode_s: float = 1800.0,
    eval_every: int = 10,
    eval_warmup_s: float = 300.0,
    eval_measure_s: float = 1200.0,
    workers: int = 0,
) -> dict:
    import torch

    torch.set_num_threads(1)  # several trainings run side by side on a small CPU
    # Dev runs must use worker processes: libsumo allows one simulation per process, and the
    # training environment holds this process's simulation.
    workers = max(workers, 2)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    network = NetworkModel.from_file(DEFAULT_NET)
    timing = SignalTiming.load(DEFAULT_NET.parent / "signals.json")
    reward = REWARD_VARIANTS[variant]
    params = DQNParams()
    agent = DQNAgent(params, seed=seed)
    rng = random.Random(seed)
    work = Path(tempfile.mkdtemp(prefix="dqn_env_"))
    env = TrafficEnv(network, timing, reward, work_dir=str(work))

    with tempfile.TemporaryDirectory() as d:
        fixed_rows = run_batch(
            dev_runs("fixed_time", "", eval_warmup_s, eval_measure_s), Path(d), workers
        )
    fixed_info = {"tt_all": per_profile(fixed_rows, "travel_time_all_mean_s"),
                  "throughput": per_profile(fixed_rows, "throughput_veh")}  # fmt: skip

    log, dev_log = [], []
    best: tuple[float, Path | None] = (float("inf"), None)
    starving_steps = 0
    t0 = time.time()
    for ep in range(1, episodes + 1):
        profile = rng.choice(TRAINING_PROFILES)
        ep_seed = demand_seed(seed, ep)
        obs, masks = env.reset(profile, ep_seed, episode_s)
        done, ret, losses, n, starve = False, 0.0, [], 0, 0
        while not done:
            acts = agent.act(obs, masks)
            obs2, masks2, rew, done = env.step(acts)
            for t, a in acts.items():
                agent.remember(obs[t], a, rew[t] / REWARD_SCALE, obs2[t], masks2[t], done)
                ret += rew[t]
            starve += env.last_starving
            agent.env_steps += 1
            loss = agent.learn()
            if loss is not None:
                losses.append(loss)
            obs, masks, n = obs2, masks2, n + 1
        starving_steps += starve
        violations = len(env.monitor.violations)
        row = {
            "episode": ep, "profile": profile, "seed": ep_seed,
            "return_per_junction": round(ret / len(env.layouts), 2),
            "mean_loss": round(st.mean(losses), 5) if losses else None,
            "epsilon": round(agent.epsilon, 4), "decisions": n,
            "starvation_penalties": starve,
            "safety_violations": violations, "wall_s": round(time.time() - t0, 1),
        }  # fmt: skip
        log.append(row)
        print(json.dumps(row), flush=True)
        if violations:
            raise RuntimeError(f"safety violation during training episode {ep}")

        if ep % eval_every == 0 or ep == episodes:
            ck = out / "checkpoints" / f"ep{ep:04d}.pt"
            meta = {"episode": ep, "env_steps": agent.env_steps, "seed": seed, "variant": variant}
            agent.save(ck, meta)
            with tempfile.TemporaryDirectory() as d:
                rows = run_batch(
                    dev_runs("dqn", str(ck), eval_warmup_s, eval_measure_s), Path(d), workers
                )
            ratio, info = selection_score(rows, fixed_rows)
            dev = {"episode": ep, "dev_score": round(ratio, 4),
                   **{f"tt_all_{p}": round(v, 2) for p, v in info["tt_all"].items()},
                   **{f"throughput_{p}": round(v, 1) for p, v in info["throughput"].items()},
                   "max_red_mean": round(st.mean(float(r["max_red_s"]) for r in rows), 1),
                   "violations": sum(r["safety_violations"] for r in rows)}  # fmt: skip
            dev_log.append(dev)
            print("DEV", json.dumps(dev), flush=True)
            if ratio < best[0]:
                best = (ratio, ck)
                shutil.copy(ck, out / "best.pt")
    env.close()
    shutil.rmtree(work, ignore_errors=True)

    write_table(log, out / "training_log.csv")
    write_table(dev_log, out / "dev_eval.csv")
    summary = {
        "trainer": "manzil.experiments.protocol_train",
        "selection_rule": "lowest mean over profiles of (T_dqn/T_fixed) x "
                          "(throughput_fixed/throughput_dqn), T = travel_time_all_mean_s, "
                          f"dev seeds {DEV_SEEDS[0]}-{DEV_SEEDS[-1]}, checked every "
                          f"{eval_every} episodes (same rule as Phase 4)",
        "selected_checkpoint": best[1].name if best[1] else None,
        "selected_dev_score": round(best[0], 4),
        "fixed_time_dev": {k: {p: round(v, 2) for p, v in d.items()}
                           for k, d in fixed_info.items()},
        "episodes": episodes, "episode_s": episode_s, "seed": seed, "variant": variant,
        "training_profiles": list(TRAINING_PROFILES),
        "dev_protocol": {"warmup_s": eval_warmup_s, "measure_s": eval_measure_s},
        "dqn_params": asdict(params), "reward_params": asdict(reward),
        "reward_scale": REWARD_SCALE,
        "training_seeds": f"{demand_seed(seed, 1)}..{demand_seed(seed, episodes)}",
        "starvation_penalties_total": starving_steps,
        "wall_time_s": round(time.time() - t0, 1),
    }  # fmt: skip
    (out / "training.json").write_text(json.dumps(summary, indent=2) + "\n")
    plot_curve(log, dev_log, out / "training_curve.png")
    return summary


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--variant", choices=sorted(REWARD_VARIANTS), default="base")
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--episode-s", type=float, default=1800.0)
    ap.add_argument("--eval-every", type=int, default=10)
    ap.add_argument("--workers", type=int, default=0, help="dev-evaluation processes (at least 2)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    s = train(a.out, a.seed, a.variant, a.episodes, a.episode_s, a.eval_every, workers=a.workers)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
