# Phase 4 results: DQN vs fixed-time vs adaptive (real SUMO runs)

Synthetic 3×3 grid. Evaluation seeds 0–4 were held out from both training and checkpoint selection. Full D2 run length: 900 s warm-up + 3,600 s measurement. All arms share the same safety filter: minimum green 10 s, yellow 3 s, all-red 2 s, and maximum red 90 s (`signals.json` v5).

## Model and training

- **Model:** parameter-sharing Double DQN (`manzil/control/dqn.py`). One MLP (26 → 128 → 128 → 4) serves all 9 junctions. It sees each junction's local observation (`manzil/control/rl_env.py`) and picks one of the masked phase actions every 5 s. Reward follows Eq 5.3: queue, waiting time, starvation and switch terms. Emergency status is not in the state.
- **Training:** 200 episodes of 1,800 s on training seeds 1001–1200, with a random profile each episode, on CPU in this cloud session (1,005 s of wall time). There were 0 safety violations in all 200 episodes. Settings are in `models/dqn/grid3x3/training.json`, and the learning curve is `training_curve.png`.
- **Checkpoint selection:** the rule was fixed before evaluation. Every 10 episodes the checkpoint is run on dev seeds 100–101 for all four profiles. The score is the mean over profiles of (T_dqn / T_fixed) × (throughput_fixed / throughput_dqn), where T is mean travel time *including unfinished vehicles*. The selected checkpoint is episode 180 (dev score 0.892), saved as `models/dqn/grid3x3/best.pt` (SHA-256 `d1e8cfdbc9345ec33abd3e5ee662284aac9953110c0d5a1dfb1e5049a69c01e4`, 85 KB). Dev scores stayed between 0.89 and 0.94 from episode 10 onward, so the policy learned early and then plateaued.

## Result (`comparison/summary.md`, `comparison/comparison.png`)

DQN vs tuned fixed-time (paired, 95 % CI); every row was better on 5/5 seeds:

| Profile | Mean travel time | Waiting time | Throughput | Max red (fixed → DQN) |
|---|---|---|---|---|
| light | −10.9 s [−11.6, −10.2], −11.0 % | −40.4 % | −0.1 % (n.s.) | 30 → 76 s |
| medium | −10.4 s [−10.6, −10.2], −9.5 % | −33.8 % | −0.1 % (n.s.) | 35 → 62 s |
| heavy | −17.2 s [−23.4, −11.1], −10.0 % | −24.4 % | +0.6 % [+0.2, +1.1] | 55 → 74 s |
| uneven | −10.5 s [−11.8, −9.1], −8.9 % | −30.1 % | +0.1 % (n.s.) | 55 → 75 s |

The same holds for travel time including unfinished vehicles: −8.8 % to −10.9 %, so this is not survivorship. The DQN also beats the adaptive controller on every travel-time and waiting-time row. 0 safety violations, 0 teleports and 0 collisions in all 60 runs.

**Trade-off: fairness.** The DQN lets a phase wait longer than the baselines do: mean max red is 62–76 s against 30–55 s, and the single worst case was 89 s. Before the maximum-red guard was added to the safety filter, one run reached 95 s. D2 puts max red under the safety layer's authority, so the guard was added and the comparison re-run. Fixed-time and adaptive results came out bit-identical, because they never reach the guard; the guard intervened 5 times in 20 DQN runs.

## Limits (for Chapter 9)

- One synthetic network. Training and evaluation use the same four demand *profiles*, on disjoint seeds; there is no held-out demand pattern or network yet (FYP-2: Lahore).
- One training run (seed 0). Training-seed variance is not measured yet.
- Checkpoint selection picks the best of 20 on the dev seeds, which is slightly optimistic for dev; the evaluation seeds were never used for selection.
- Phase 3 (corridor) experiments used fixed-time background signals with `signals.json` v3, before the guard existed. The corridor has not yet been run with the DQN.
