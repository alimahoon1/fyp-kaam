# Scenario: synthetic 3×3 grid (`grid3x3`)

This network is **synthetic**: it is a test track for the controllers, routing and the corridor, not a real Lahore area (D2 network fallback, team decision 8). All Manzil code reads the network from `grid3x3.net.xml` and uses no hard-coded IDs, so the Lahore network can later replace this file.

## Network (PLAN task 1.1)

Built with `python -m manzil.scenarios.grid` (wraps `netgenerate`; the exact command, SUMO version and checksum are in `network.json`).

| Property | Value |
|---|---|
| Signalised junctions | 9 (`A0` … `C2`), each a four-arm intersection |
| Fringe nodes | 12 dead ends, where traffic enters and leaves |
| Block length / fringe road length | 200 m / 200 m (area 800 m × 800 m) |
| Lanes per direction / speed limit | 2 / 13.89 m/s (50 km/h) |
| Turning | Left turns permitted (yield to oncoming traffic); no U-turns |
| Signal program in the file | SUMO default static: 42 s green, 3 s yellow per axis (90 s cycle) |

The default static program is only what `netgenerate` writes. Manzil's own fixed-time controller (task 1.6) and the other controllers replace it at run time.

`network.json` stores `content_sha256`: the SHA-256 of the file without SUMO's first "generated on <date>" comment, so it stays the same when the network is rebuilt unchanged. `tests/test_grid.py` checks that a rebuild reproduces the committed file.

**GUI check:** cloud sessions are headless, so the network was checked with `sumolib` and headless `sumo`. To look at it on a laptop:

```bash
python -m manzil.scenarios.demand --profile light --seed 0
sumo-gui -c scenarios/grid3x3/demand/light_seed0.sumocfg
```

## Demand profiles (PLAN task 1.2)

Built with `python -m manzil.scenarios.demand --all --seed N`. The files go to `scenarios/grid3x3/demand/`, which git ignores because any seed can be rebuilt in under a second.

- Entry and exit roads come from the network: edges that start or end at a dead-end node.
- Each entry road gets Poisson arrivals at the profile rate (seeded `numpy` generator). Each trip goes to a uniformly chosen exit, never back to its own fringe node.
- `duarouter` writes explicit shortest-path routes, so the same seed always loads the same vehicles.

| Profile | Rate per entry road (veh/h) | Purpose |
|---|---|---|
| light | 200 | Free-flowing traffic |
| medium | 400 | Busy but stable |
| heavy | 600 | Near saturation with default signals; long queues |
| uneven | 800 north-south, 100 east-west | Starvation case: the quiet approach must still be served |

**Calibration.** With SUMO's default static signals, a sweep on seed 0 gave: 600 veh/h per entry gridlock-free; 750 had a jam teleport and about 100 s mean departure delay; 900 and above left vehicles unserved. "heavy" is therefore set just below that limit, so the baseline still finishes and better controllers have room to improve.

## Gridlock check result

Command: `python -m manzil.scenarios.check --seeds 0 1 2 3 4 --out results/phase1/demand_check.json`

Conditions: 3,600 s of demand, then up to 1,800 s to drain, SUMO 1.28.0, default static signals, `--time-to-teleport 300`. A run is **gridlock-free** when there are no jam teleports and every loaded vehicle arrives.

Averages over seeds 0–4 (all 20 runs were gridlock-free, with 0 teleports and 0 collisions):

| Profile | Vehicles | Mean trip time (s) | Mean waiting time (s) | Mean time loss (s) | Mean departure delay (s) |
|---|---|---|---|---|---|
| light | 2,387 | 100.6 | 26.6 | 40.2 | 0.51 |
| medium | 4,803 | 109.2 | 31.4 | 48.8 | 0.53 |
| heavy | 7,218 | 156.0 | 62.6 | 95.6 | 2.79 |
| uneven | 5,411 | 130.1 | 45.6 | 69.9 | 0.56 |

These numbers only check the demand. They are **not** controller results: there is no warm-up, and the signals are SUMO's default program, not a Manzil controller.

## Signal timing and fixed-time plans (PLAN tasks 1.5 and 1.6)

`signals.json` is versioned with the scenario (now version 3: the safety timing and fixed-time plans are unchanged since version 1; versions 2 and 3 added and then froze the adaptive controller's parameters). All controllers share the same safety timing: **minimum green 10 s, yellow 3 s, all-red 2 s**. On this grid, green phase 0 is north-south and phase 1 is east-west at every junction (`tests/test_fixed_time.py` checks this).

**Fixed-time plans.** D2 requires a credible baseline, not a deliberately weak one, with splits chosen from the declared demand. Plans were therefore tuned per profile by a sweep on **dev seeds 100 and 101**, never on the evaluation seeds (0–4), using the full 900 s warm-up + 3,600 s measurement. Mean travel time over the two dev seeds:

| Profile | Plans tried (green s, phase 0 / phase 1) → mean travel time (s) | Chosen |
|---|---|---|
| light | 20/20 → 97.2 · 25/25 → 98.6 · 35/35 → 102.4 | 20/20 (50 s cycle) |
| medium | 20/20 → 110.8 · 25/25 → 109.7 · 35/35 → 112.7 · 45/45 → 115.9 · 55/55 → 121.4 | 25/25 (60 s cycle) |
| heavy | 25/25 → 192.3 · 35/35 → 177.3 · 40/40 → 176.4 · 45/45 → 174.9 · 55/55 → 177.1 | 45/45 (100 s cycle) |
| uneven | 35/35 → 160.0 · 40/25 → 120.8 · 45/25 → 119.3 · 50/25 → 120.9 · 40/30 → 124.3 · 45/30 → 121.9 · 45/20 → 131.8 · 50/20 → 148.7 · 55/15 → 227.1 · 60/20 → 185.3 · 70/25 → 173.4 | 45/25 (80 s cycle) |

On uneven demand, starving east-west (≤ 20 s) is worse even for the busy axis. The east-west links inside the grid also carry vehicles that turned off the north-south roads, so their queues spill back. `equal` (35/35, 80 s) is kept as a reference plan. `--plan auto` (the default) uses the plan that `profile_plans` declares for the demand profile.

## Running one experiment

```bash
python -m manzil.experiments.runner --profile heavy --seed 0
```

This writes `runs/<time>_grid3x3_fixed_time_heavy_s0/`, which contains the manifest, metrics, time series, signal events and applied controls (`runs/` is git-ignored). `results/phase1/fixed_time_seed0.json` holds one full run per profile on seed 0. These are smoke results: a single seed is not a comparison. `unfinished_veh` counts vehicles that departed in the measurement window but were still driving at its end, mostly trips that started in the last minutes.

## Adaptive (pressure) controller parameters (PLAN task 2.1)

One parameter set is used for **every** profile, because an adaptive controller should not need to know the demand in advance. It was chosen by two sweeps on dev seeds 100–101, 60 settings in total; the full list is in `results/phase2/adaptive_tuning_dev_seeds.csv`. The score of a setting is its mean travel time divided by the tuned fixed-time plan's, averaged over the four profiles.

- Sweep 1: α ∈ {0.5, 1}, β ∈ {0, 0.005, 0.02}, switch margin ∈ {0, 3, 6}, max green ∈ {40, 60} s. The best setting tied fixed-time (mean ratio 1.009), but heavy demand was 8 % worse because the controller switched too often.
- Sweep 2 added a controller-side minimum hold ∈ {15, 20, 25} s (and β ∈ {0.02, 0.05}).

**Frozen:** α 0.5, β 0.02, max green 40 s, max red 90 s, switch margin 3, minimum hold 15 s. On the dev seeds its mean ratio is 1.005 and its worst profile is uneven at 1.053. α made little difference.

