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
