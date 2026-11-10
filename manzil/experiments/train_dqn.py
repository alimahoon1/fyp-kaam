"""Train the parameter-sharing DQN on the grid (PLAN task 4.2), on CPU.

Seeds are split three ways and never mixed:

- **training**: seeds 1000, 1001, ... (one new seed per episode, random profile);
- **checkpoint selection (dev)**: seeds 100 and 101, all four profiles, every ``eval_every``
  episodes, with the real runner. Selection rule, fixed before any evaluation: the checkpoint
  with the lowest mean over profiles of ``(T_dqn / T_fixed) x (throughput_fixed /
  throughput_dqn)``, where T is ``travel_time_all_mean_s`` (unfinished vehicles included).
  Mean travel time over finished trips alone would reward a policy that strands vehicles;
- **evaluation**: seeds 0-4, used only by the comparison afterwards (task 4.3).

Outputs in ``--out``: ``training_log.csv``, ``dev_eval.csv``, ``checkpoints/ep*.pt``,
``best.pt``, ``training_curve.png`` and ``training.json`` (settings + selected checkpoint).

Usage::

    python -m manzil.experiments.train_dqn --episodes 200 --out models/dqn/grid3x3
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
from manzil.experiments.runner import RunConfig
from manzil.scenarios.demand import DEFAULT_NET, PROFILES
from manzil.sim.network import NetworkModel

DEV_SEEDS = (100, 101)
REWARD_SCALE = 10.0  # rewards are divided by this before learning


def dev_runs(arm: str, checkpoint: str, warmup_s: float, measure_s: float) -> list[RunConfig]:
    return [
        RunConfig(profile=p, seed=s, controller=arm, warmup_s=warmup_s, measure_s=measure_s,
                  checkpoint=checkpoint, label=arm)
        for p in sorted(PROFILES)
        for s in DEV_SEEDS
    ]  # fmt: skip


def per_profile(rows, metric) -> dict[str, float]:
    by = {}
    for r in rows:
        by.setdefault(r["profile"], []).append(float(r[metric]))
    return {p: st.mean(v) for p, v in by.items()}


def selection_score(rows, fixed_rows) -> tuple[float, dict]:
    tt, ftt = (
        per_profile(rows, "travel_time_all_mean_s"),
        per_profile(fixed_rows, "travel_time_all_mean_s"),
    )
    th, fth = per_profile(rows, "throughput_veh"), per_profile(fixed_rows, "throughput_veh")
    per = {p: (tt[p] / ftt[p]) * (fth[p] / max(th[p], 1.0)) for p in tt}
    return st.mean(per.values()), {"tt_all": tt, "throughput": th, "score": per}


def train(episodes: int, episode_s: float, eval_every: int, out: Path, seed: int,
          eval_warmup_s: float = 300.0, eval_measure_s: float = 1200.0) -> dict:  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    network = NetworkModel.from_file(DEFAULT_NET)
    timing = SignalTiming.load(DEFAULT_NET.parent / "signals.json")
    reward = RewardParams()
    params = DQNParams()
    agent = DQNAgent(params, seed=seed)
    rng = random.Random(seed)
    work = Path(tempfile.mkdtemp(prefix="dqn_env_"))
    env = TrafficEnv(network, timing, reward, work_dir=str(work))

    with tempfile.TemporaryDirectory() as d:
        fixed_rows = run_batch(dev_runs("fixed_time", "", eval_warmup_s, eval_measure_s), Path(d))
    fixed_info = {"tt_all": per_profile(fixed_rows, "travel_time_all_mean_s"),
                  "throughput": per_profile(fixed_rows, "throughput_veh")}  # fmt: skip

    log, dev_log = [], []
    best = (float("inf"), None)
    t0 = time.time()
    for ep in range(1, episodes + 1):
        profile = rng.choice(sorted(PROFILES))
        ep_seed = 1000 + ep
        obs, masks = env.reset(profile, ep_seed, episode_s)
        done, ret, losses, n = False, 0.0, [], 0
        while not done:
            acts = agent.act(obs, masks)
            obs2, masks2, rew, done = env.step(acts)
            for t, a in acts.items():
                agent.remember(obs[t], a, rew[t] / REWARD_SCALE, obs2[t], masks2[t], done)
                ret += rew[t]
            agent.env_steps += 1
            loss = agent.learn()
            if loss is not None:
                losses.append(loss)
            obs, masks, n = obs2, masks2, n + 1
        violations = len(env.monitor.violations)
        row = {
            "episode": ep, "profile": profile, "seed": ep_seed,
            "return_per_junction": round(ret / len(env.layouts), 2),
            "mean_loss": round(st.mean(losses), 5) if losses else None,
            "epsilon": round(agent.epsilon, 4), "decisions": n,
            "safety_violations": violations, "wall_s": round(time.time() - t0, 1),
        }  # fmt: skip
        log.append(row)
        print(json.dumps(row), flush=True)
        if violations:
            raise RuntimeError(f"safety violation during training episode {ep}")

        if ep % eval_every == 0 or ep == episodes:
            ck = out / "checkpoints" / f"ep{ep:04d}.pt"
            agent.save(ck, {"episode": ep, "env_steps": agent.env_steps, "seed": seed})
            with tempfile.TemporaryDirectory() as d:
                rows = run_batch(dev_runs("dqn", str(ck), eval_warmup_s, eval_measure_s), Path(d))
            ratio, info = selection_score(rows, fixed_rows)
            dev = {"episode": ep, "dev_score": round(ratio, 4),
                   **{f"tt_all_{p}": round(v, 2) for p, v in info["tt_all"].items()},
                   **{f"throughput_{p}": round(v, 1) for p, v in info["throughput"].items()},
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
        "selection_rule": "lowest mean over profiles of (T_dqn/T_fixed) x "
                          "(throughput_fixed/throughput_dqn), T = travel_time_all_mean_s, "
                          "dev seeds 100-101, checked every "
                          f"{eval_every} episodes",
        "selected_checkpoint": best[1].name if best[1] else None,
        "selected_dev_score": round(best[0], 4),
        "fixed_time_dev": {k: {p: round(v, 2) for p, v in d.items()}
                           for k, d in fixed_info.items()},
        "episodes": episodes, "episode_s": episode_s, "seed": seed,
        "dev_protocol": {"warmup_s": eval_warmup_s, "measure_s": eval_measure_s},
        "dqn_params": asdict(params), "reward_params": asdict(reward),
        "reward_scale": REWARD_SCALE, "training_seeds": f"1001..{1000 + episodes}",
        "wall_time_s": round(time.time() - t0, 1),
    }  # fmt: skip
    (out / "training.json").write_text(json.dumps(summary, indent=2) + "\n")
    plot_curve(log, dev_log, out / "training_curve.png")
    return summary


def plot_curve(log, dev_log, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    for prof in sorted(PROFILES):
        pts = [(r["episode"], r["return_per_junction"]) for r in log if r["profile"] == prof]
        if pts:
            a1.plot(*zip(*pts, strict=True), ".", label=prof, alpha=0.7)
    a1.set_xlabel("episode")
    a1.set_ylabel("return per junction")
    a1.set_title("Training return (training seeds)")
    a1.legend()
    a1.grid(alpha=0.3)
    if dev_log:
        eps = [r["episode"] for r in dev_log]
        a2.plot(eps, [r["dev_score"] for r in dev_log], "o-")
        a2.axhline(1.0, color="grey", ls="--", label="tuned fixed-time")
        a2.set_xlabel("episode")
        a2.set_ylabel("selection score (lower is better)")
        a2.set_title("Dev seeds 100-101 (checkpoint selection)")
        a2.legend()
        a2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--episode-s", type=float, default=1800.0)
    ap.add_argument("--eval-every", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    s = train(a.episodes, a.episode_s, a.eval_every, a.out, a.seed)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
