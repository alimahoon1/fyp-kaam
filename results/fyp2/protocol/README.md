# W3: full evaluation protocol and DQN robustness (synthetic 3×3 grid)

All numbers here come from real SUMO runs on the synthetic 3×3 grid (`scenarios/grid3x3`), produced
15–16 Nov 2026 by the W3 cloud session. The network is **synthetic**, not Lahore. The same commands work
on the Lahore network once W1 delivers it (see "Rerun on another network").

## Protocol (D2 section 5.8)

| Item | Value |
|---|---|
| Warm-up + measurement | 900 s + 3,600 s per run |
| Evaluation seeds | **20–29** (10 matched seeds; every arm sees the same vehicles per profile and seed) |
| Other seed sets (never mixed) | DQN training 1001+ (seed k uses 1000 + 1000k + episode), dev / checkpoint selection and plan selection 100–101, FYP-1 evaluation 0–4 (not reused) |
| Training profiles | light, medium, heavy, uneven (heavy north–south) |
| **Held-out profiles** (never used for training, selection or tuning; fixed before any run) | `uneven_ew`: 100 veh/h north–south, 800 east–west (training only saw the reverse); `tidal`: 650 veh/h on roads heading north or east, 150 on the rest; `peak`: time-varying, 40 % → 100 % → 40 % of 650 veh/h over the run |
| Fixed-time reference | Tuned plan per training profile (Phase 2). For held-out profiles: the best of the scenario's **existing** plans on dev seeds 100–101 (`main/plan_selection.csv`): uneven_ew → equal, tidal → medium, peak → medium. Fixed-time gets to know the demand; adaptive and DQN do not |
| Statistics | Paired difference against tuned fixed-time per profile: mean, 95 % Student-t CI over the 10 seeds, % change, seeds better. Failed runs are kept (there were none) |
| Fairness metrics (new) | From every red interval of every phase in the window: mean, 95th percentile, and share longer than 60 s, next to max red |

Arms (8 × 7 profiles × 10 seeds = **560 runs**): `fixed_time`, `adaptive`, DQN training seeds
`dqn_s0` (the Phase 4 model `models/dqn/grid3x3/best.pt`, unchanged), `dqn_s1`, `dqn_s2`, and the
fairness variant `dqn_fair_s0..2`. `dqn_avg3` / `dqn_fair_avg3` average the three models per
evaluation seed, so their CI covers evaluation seeds while still including all three trainings.

**Totals:** 560 runs, 0 failed, **0 safety violations, 0 collisions**. There were 49 teleports in
4 runs: dqn_s2 heavy seed 29 (39), dqn_fair_s1 heavy seed 22 (8), fixed_time heavy seed 26 (1), and
fixed_time uneven_ew (1).

## 1. Controllers against tuned fixed-time

Mean travel time including unfinished vehicles (s). Δ = paired difference [95 % CI], seeds better
out of 10:

| Profile | fixed-time | adaptive | Δ adaptive | DQN (avg of 3 models) | Δ DQN |
|---|---|---|---|---|---|
| light | 97.0 | 97.6 | +0.7 [0.2, 1.1], 1/10 | 86.9 | −10.1 [−10.3, −9.9] (−10.4 %), 10/10 |
| medium | 108.3 | 103.4 | −4.9 [−5.2, −4.5], 10/10 | 97.9 | −10.4 [−10.6, −10.1] (−9.6 %), 10/10 |
| heavy | 169.9 | 166.2 | −3.8 [−8.4, 0.9], 7/10 | 163.5 | −6.4 [−24.1, 11.2] (−3.8 %), 9/10 |
| uneven | 116.8 | 120.0 | +3.2 [0.2, 6.2], 3/10 | 107.7 | −9.1 [−11.6, −6.6] (−7.8 %), 10/10 |
| uneven_ew (held out) | 147.0 | 119.9 | −27.0 [−33.9, −20.1], 10/10 | 107.7 | −39.3 [−46.9, −31.7] (−26.7 %), 10/10 |
| tidal (held out) | 112.8 | 106.9 | −5.9 [−6.7, −5.0], 10/10 | 100.1 | −12.7 [−13.6, −11.9] (−11.3 %), 10/10 |
| peak (held out) | 139.4 | 130.3 | −9.0 [−11.3, −6.7], 10/10 | 123.9 | −15.5 [−17.2, −13.7] (−11.1 %), 10/10 |

- **The DQN generalises to the held-out demand.** On all three unseen patterns it beats tuned
  fixed-time on 10/10 seeds with every model. Mean waiting time is −29 % to −53 %, mean queue
  −29 % to −56 %, and throughput is equal or higher.
- **The uneven_ew gain is partly a fixed-time limitation:** the scenario has no plan that favours
  east–west, so even the best existing plan (equal 35/35) is poor there. A plan tuned for that
  direction would close part of the gap. Adaptive also gains −27 s there.
- The Phase 4 results on seeds 0–4 hold up on the new seeds 20–29 for the training profiles
  (Phase 4: −9 % to −11 %).
- Throughput differences are within ±1 %. The DQN switches phases more often than fixed-time:
  +13 % to +162 %.

## 2. Training variance (3 training seeds)

Paired Δ in mean travel time against fixed-time for each trained model (`main/per_model_dqn_avg3.csv`):

| Profile | dqn_s0 (Phase 4 model) | dqn_s1 | dqn_s2 |
|---|---|---|---|
| light | −10.8, 10/10 | −9.2, 10/10 | −10.2, 10/10 |
| medium | −10.5, 10/10 | −10.3, 10/10 | −10.3, 10/10 |
| heavy | −22.6, 10/10 | −13.4, 10/10 | **+16.7 [−30.0, 63.4], 7/10** |
| uneven | −9.6, 10/10 | −9.5, 10/10 | −8.2, 10/10 |
| uneven_ew | −39.6, 10/10 | −39.7, 10/10 | −38.5, 10/10 |
| tidal | −12.6, 10/10 | −12.6, 10/10 | −13.0, 10/10 |
| peak | −17.7, 10/10 | −16.4, 10/10 | −12.4, 10/10 |

- On six of the seven profiles, the spread between the three models is small. The SD of the
  per-model means (`between_sd` in `training_variance_dqn_avg3.csv`) is 0.1–2.8 s, against a gain
  of 9–40 s.
- **Heavy demand is not robust to the training seed.** dqn_s2 nearly gridlocked on heavy seed 29:
  372 s mean travel time, 804 unfinished vehicles, 39 teleports. It was also worse than fixed-time
  on 2 more seeds. Across the three models, heavy mean travel time is 147.3 / 156.6 / 186.6 s
  (between-model SD 20.6 s).
- The Phase 4 model (s0) happens to be the best of the three on heavy. So the Phase 4 heavy result
  (−10 %) overstates what a randomly trained model would give. The fair estimate is the 3-model
  average: −3.8 %, with a CI that crosses 0.
- All six models were picked by the same dev-seed rule, and all had similar dev scores
  (0.892–0.907). The dev check (2 seeds × 1,500 s) did not catch dqn_s2's heavy instability.

## 3. Fairness variant

Fixed before evaluation: the reward's starvation term fires when a phase is red for more than
60 s instead of 90 s. Everything else is unchanged, including the same weight c = 2. In base
training the 90 s term fired **0 times in 200 episodes** (the safety filter already forces a switch
at 85 s), so the term had no effect. At 60 s it fired 461–792 times per training. Comparison:
3 fair models against 3 base models, averaged per seed.

| Profile | Max red, base → fair (s) | Δ [95 % CI], better | Red > 60 s, base → fair (%) | Travel time Δ fair − base (s) |
|---|---|---|---|---|
| light | 78.9 → 68.7 | −10.2 [−12.9, −7.5], 10/10 | 0.6 → 0.1 | −0.0, 4/10 |
| medium | 59.5 → 58.8 | −0.7 [−3.3, 2.0], 5/10 | 0.0 → 0.0 | −0.2, 9/10 |
| heavy | 67.5 → 62.4 | −5.1 [−10.7, 0.6], 7/10 | 0.2 → 0.1 | −10.2 [−25.8, 5.4], 9/10 |
| uneven | 77.2 → 69.2 | −8.1 [−10.6, −5.6], 10/10 | 0.4 → 0.2 | −0.6, 7/10 |
| uneven_ew (held out) | 78.3 → 79.4 | +1.1 [−1.9, 4.1], 2/10 | 0.5 → 0.5 | −0.6, 8/10 |
| tidal (held out) | 64.5 → 63.0 | −1.5 [−4.4, 1.4], 4/10 | 0.1 → 0.0 | +0.2, 5/10 |
| peak (held out) | 63.0 → 61.3 | −1.7 [−6.9, 3.5], 6/10 | 0.0 → 0.0 | −1.2, 8/10 |

- The variant lowers the worst red waits where the base DQN was worst (light −13 %, uneven
  −10 %) at **no efficiency cost**. Travel and waiting time are equal or slightly better.
- **It also made heavy demand more stable:** all 3 fair models beat fixed-time on heavy (−15.7,
  −14.1, −20.2 s). Its 3-model average is −16.6 s [−23.1, −10.2] (−9.8 %), 9/10 seeds, against
  −6.4 s with a CI crossing 0 for base.
- **It does not close the fairness gap to fixed-time:** max red is still 59–79 s, against 30–55 s
  for fixed-time and 50 s for adaptive. Red intervals over 60 s stay rare (≤ 0.6 % of all red
  intervals for every arm). The 95th percentile red interval is ≤ fixed-time on heavy and uneven,
  and higher on light (+13 s).
- On held-out uneven_ew, max red did not improve (+1.1 s).
- **Recommendation for the team:** consider `dqn_fair` as the default DQN. On this grid it is at
  least as efficient, fairer on training demand and more stable on heavy demand. This is a
  decision for Ibrahim; the scenario's `signals.json` still points to the Phase 4 model.

## 4. Corridor v2 on new seeds (confirmation of task 3.7)

Same setup as `results/phase3/corridor_v2/`: dispatch at 1,200 s, 900 + 900 s, medium and heavy,
fixed-time and DQN (s0) background. Arms off / v1 / v2 on **new seeds 20–29** (120 runs): **0 safety
violations, 0 ambulance red-light crossings, 0 teleports, 0 collisions**. Full tables:
`corridor_v2_newseeds/contrasts.md`.

Ambulance travel time, paired Δ [95 % CI], seeds better:

| Background, profile | v2 − off, dev seeds 0–4 | v2 − off, new seeds 20–29 | v2 − v1, dev seeds 0–4 | v2 − v1, new seeds 20–29 |
|---|---|---|---|---|
| fixed-time, medium | −53.2, 5/5 | **−69.0 [−91.6, −46.4] (−41 %), 10/10** | −0.6, 1/5 | −8.0 [−11.5, −4.5], 10/10 |
| fixed-time, heavy | −185.8, 5/5 | **−177.5 [−234.7, −120.3] (−55 %), 10/10** | −8.2, 4/5 | **−1.1 [−16.5, 14.3], 5/10** |
| DQN, medium | −35.4, 5/5 | **−52.4 [−77.5, −27.3] (−34 %), 10/10** | −2.4, 3/5 | −6.1 [−10.8, −1.4], 8/10 |
| DQN, heavy | −178.2, 5/5 | **−132.5 [−190.0, −75.0] (−53 %), 10/10** | −6.4, 5/5 | −8.2 [−15.2, −1.2], 8/10 |

- **Confirmed:** the corridor (v2 vs off) cuts ambulance time by 34–55 % on every new seed. The
  ambulance's stopped time falls by 88–97 %.
- **The v2-over-v1 step is confirmed in 3 of 4 settings, but not on fixed-time heavy,** which was
  the setting the 5 s truncation was chosen for. There it is −1.1 s with a CI crossing 0, and the
  network queue in the 600 s after dispatch is +4.0 veh [0.1, 7.9]. The other three settings show
  −6 to −8 s with CIs below 0.
- **Ordinary-traffic cost of the corridor (v2 vs off) on new seeds:**
  - fixed-time heavy: cross-street queueing +32.7 % [CI above 0], network queue +4.3 %, mean
    waiting time +3.4 %;
  - DQN heavy: cross-street queueing +14.3 % [CI above 0];
  - medium: +5 to +11 % cross-street.
- This cost is larger than "no measurable cost" suggests. It should be stated as a trade-off in
  Chapter 9.

## Figures

- `main/paired_controllers_vs_tuned_fixed_time.png`: paired Δ with 95 % CI for adaptive and DQN
  (3-model average) on 8 metrics; held-out profiles shaded.
- `main/paired_fairness_variant_vs_base_dqn.png`, `main/paired_fairness_variant_vs_tuned_fixed_time.png`:
  the same for the fairness variant.

## Files

- `main/results.csv`: one row per run (560), with config, metrics and fairness metrics.
  `main/runs/*/` holds `manifest.json` + `metrics.json`; the per-run CSVs were deleted to save space.
- `main/tables.md`: all tables (every metric, every comparison, per-model tables).
  `main/summary.json`: the same numbers as data.
- `main/training_variance_*.csv`: per model and profile, the per-model means, between-model SD and
  range, and within-model (evaluation-seed) SD. `main/per_model_*.csv`: each model's paired Δ
  against fixed-time.
- `main/plan_selection.csv`: dev-seed plan choice for held-out profiles. `main/protocol.json`: the
  exact protocol.
- `corridor_v2_newseeds/`: `fixed_time/` and `dqn/` (results.csv + runs), `contrasts.csv`/`.md`
  (development against new seeds), `totals.json`.
- Models: `models/dqn/grid3x3_base_s1`, `_base_s2`, `_fair_s0`, `_fair_s1`, `_fair_s2` (best.pt,
  training log, dev evaluation, curve, training.json). The Phase 4 model `models/dqn/grid3x3/`
  is unchanged.

## How it was produced

```bash
# 5 trainings (about 38 min each, all 5 in parallel on 4 CPUs)
python -m manzil.experiments.protocol_train --seed 1 --variant base --workers 2 --out models/dqn/grid3x3_base_s1
#   (likewise --seed 2 base; --seed 0/1/2 --variant fair -> models/dqn/grid3x3_fair_s<k>)
python -m manzil.experiments.protocol run --out results/fyp2/protocol/main \
  --arms fixed_time adaptive dqn_s0=dqn@models/dqn/grid3x3/best.pt \
    dqn_s1=dqn@models/dqn/grid3x3_base_s1/best.pt dqn_s2=dqn@models/dqn/grid3x3_base_s2/best.pt \
    dqn_fair_s0=dqn@models/dqn/grid3x3_fair_s0/best.pt dqn_fair_s1=dqn@models/dqn/grid3x3_fair_s1/best.pt \
    dqn_fair_s2=dqn@models/dqn/grid3x3_fair_s2/best.pt \
  --group dqn_avg3=dqn_s0,dqn_s1,dqn_s2 dqn_fair_avg3=dqn_fair_s0,dqn_fair_s1,dqn_fair_s2
python -m manzil.experiments.protocol_corridor --out results/fyp2/protocol/corridor_v2_newseeds
# tables/plots only, from results.csv:
python -m manzil.experiments.protocol report --out results/fyp2/protocol/main --group ...
```

The 560-run protocol took about 30 min on the 4-CPU cloud machine.

## Rerun on another network (e.g. Lahore, after W1)

The protocol needs a scenario folder with `<name>.net.xml`, `network.json` and `signals.json`.
Demand comes from the network's fringe roads, and held-out headings come from road geometry.
Run `protocol run --scenario <name>` (or `--scenario-root <folder>` for a folder outside
`scenarios/`). Fixed-time plans for held-out profiles are selected from that scenario's plans on dev
seeds. `tests/test_w3_protocol.py::test_protocol_runs_on_another_network` checks this on a
2×2 grid. DQN checkpoints are network-specific in practice: train them on the new network first
with `protocol_train` (its network is currently the grid default and would need a `--net` option).

## Limits

- One synthetic network; 3 training seeds is a small sample of training variance.
- The held-out patterns are new demand on the same grid, not a new network.
- The fixed-time plan library has no east–west-favouring plan, which inflates the uneven_ew gain.
- Corridor v2 was rerun only with the Phase 4 DQN (s0) as background control.
