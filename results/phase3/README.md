# Phase 3 results: ambulance routing and green corridor (real SUMO runs)

Synthetic 3×3 grid, tuned fixed-time signals for ordinary traffic, evaluation seeds 0–4, warm-up 900 s. One ambulance (vClass `emergency`, obeys signals, no blue-light device) is dispatched at 1,200 s from `left0A0` (south-west) to `C2top2` (north-east exit). Its free-flow trip takes about 79 s. Ambulance travel time counts from dispatch, so time spent waiting to enter a full road is included. Reproduce with:

```bash
python -m manzil.experiments.emergency_study --seeds 0 1 2 3 4 --out results/phase3
```

## Experiment 1: static vs dynamic route (`routing/`)

The corridor is off. An obstruction (speed limit 2 m/s) starts at 1,000 s on `A1A2`, an edge of the route that static routing picks on free-flow costs. Static routing plans once on free-flow costs; dynamic routing uses Eq 5.4 live costs, which include the reported speed limit, and Algorithm 1. Measurement runs for 1,800 s, so every ambulance can arrive. A first run with 900 s left 4 of 5 heavy static trips unfinished, and was discarded for that reason.

| Profile | Ambulance travel time, static → dynamic | Paired difference (95 % CI) | Seeds better |
|---|---|---|---|
| medium | 307.8 → 144.6 s | −163.2 s [−200.4, −126.0], −53 % | 5/5 |
| heavy | 588.2 → 298.0 s | −290.2 s [−411.7, −168.7], −49 % | 5/5 |

Ordinary traffic is not harmed: network queue from dispatch to 300 s after arrival −4 % (medium, CI crosses 0) and −7.5 % (heavy, [−24.9, −4.7] vehicles). All 20 ambulances arrived; no safety violations. There were 10 background teleports in total (4 runs, mostly heavy), caused by the long jam behind the obstruction.

## Experiment 2: corridor off vs on (`corridor/`)

Dynamic routing in both arms, no incident, 900 s measurement.

| Profile | Ambulance travel time, off → on | Paired difference (95 % CI) | Time stopped, off → on |
|---|---|---|---|
| medium | 154.0 → 102.6 s | −51.4 s [−67.1, −35.7], −33 %, 5/5 seeds | 47.4 → 3.6 s |
| heavy | 313.8 → 133.4 s | −180.4 s [−263.3, −97.5], −57 %, 5/5 seeds | 174.6 → 17.2 s |

**Cost to ordinary traffic.** Network queue from dispatch to 300 s after arrival rises by +3.5 % on medium (CI crosses 0) and +5.8 % on heavy ([+1.4, +15.6] vehicles). Mean waiting time over the whole window rises by +2.3 % (medium) and +3.9 % (heavy). Mean junction recovery time is 8.3 s (medium) and 12.0 s (heavy). Recovery means the junction queue is back to its typical level, the mean of the 120 s before activation; 8 recoveries out of all junctions served were still open at run end and are reported as unfinished. All 20 ambulances arrived, with 0 safety violations, 0 teleports and 1 priority timeout.

## Limits

- One synthetic network, one origin–destination pair, one dispatch time, and fixed-time background signals only. The corridor has not yet been run with the adaptive or DQN controllers.
- The incident site was chosen on the static route on purpose; the experiment asks whether live costs avoid a *reported* incident, not whether incidents happen there.
- The downstream-capacity check in D2 §5.6 is not implemented yet. The bounded compensation plan in recovery is also not implemented: ownership returns to normal control at once, and the safety filter keeps that hand-over legal.
