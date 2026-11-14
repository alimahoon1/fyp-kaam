# Phase 3 results: ambulance routing and green corridor (real SUMO runs)

Rerun on 14 Nov 2026 (task 3.7) with the corridor v2 defaults and the ambulance speed fix; the task 3.7 study itself is in `corridor_v2/`. Synthetic 3×3 grid, tuned fixed-time signals for ordinary traffic, evaluation seeds 0–4, warm-up 900 s. One ambulance (vClass `emergency`, obeys signals, no blue-light device) is dispatched at 1,200 s from `left0A0` (south-west) to `C2top2` (north-east exit). Its free-flow trip takes about 79 s; it drives at exactly the speed limit (speed factor 1, no random spread since task 3.7). Ambulance travel time counts from dispatch, so time spent waiting to enter a full road is included. Reproduce with:

```bash
python -m manzil.experiments.emergency_study --seeds 0 1 2 3 4 --out results/phase3
```

## Experiment 1: static vs dynamic route (`routing/`)

The corridor is off. An obstruction (speed limit 2 m/s) starts at 1,000 s on `A1A2`, an edge of the route that static routing picks on free-flow costs. Static routing plans once on free-flow costs; dynamic routing uses Eq 5.4 live costs, which include the reported speed limit, and Algorithm 1. Measurement runs for 1,800 s, so every ambulance can arrive. A first run with 900 s left 4 of 5 heavy static trips unfinished, and was discarded for that reason.

| Profile | Ambulance travel time, static → dynamic | Paired difference (95 % CI) | Seeds better |
|---|---|---|---|
| medium | 309.0 → 145.4 s | −163.6 s [−201.7, −125.5], −53 % | 5/5 |
| heavy | 587.8 → 302.0 s | −285.8 s [−408.6, −163.0], −49 % | 5/5 |

Ordinary traffic is not harmed: network queue from dispatch to 300 s after arrival −5.1 % (medium, CI crosses 0) and −8.2 % (heavy, [−25.9, −5.9] vehicles). All 20 ambulances arrived; no safety violations; 0 red-light crossings by the ambulance. There were 12 background teleports in total (mostly heavy), caused by the long jam behind the obstruction.

## Experiment 2: corridor off vs on (`corridor/`)

Dynamic routing in both arms, no incident, 900 s measurement. Corridor v2: look-ahead 2, activation at ETA ≤ 15 s + queue clearance, emergency truncation of minimum green to 5 s for corridor requests (yellow and all-red kept).

| Profile | Ambulance travel time, off → on | Paired difference (95 % CI) | Time stopped, off → on |
|---|---|---|---|
| medium | 155.8 → 102.6 s | −53.2 s [−69.2, −37.2], −34 %, 5/5 seeds | 45.2 → 4.4 s |
| heavy | 313.6 → 127.8 s | −185.8 s [−278.5, −93.1], −59 %, 5/5 seeds | 173.2 → 12.4 s |

**Cost to ordinary traffic.** Network queue from dispatch to 300 s after arrival rises by +2.5 % on medium and +3.0 % on heavy (both CIs cross 0; v1 had +3.5 % / +5.8 %). Mean waiting time over the whole window rises by +2.4 % (medium) and +1.9 % (heavy). Mean junction recovery time is 8.6 s (medium) and 13.8 s (heavy). Recovery means the junction queue is back to its typical level, the mean of the 120 s before activation; 5 recoveries were still open at run end and are reported as unfinished. All 20 ambulances arrived, with 0 safety violations, 0 teleports, 0 priority timeouts and 0 red-light crossings by the ambulance. The previous (v1) numbers were 154.0 → 102.6 s and 313.8 → 133.4 s; `corridor_v2/` has the controlled v1 vs v2 comparison.

## Limits

- One synthetic network, one origin–destination pair, one dispatch time. The experiments here use fixed-time background signals; `corridor_v2/` also runs the corridor with the DQN (not yet with the adaptive controller).
- The incident site was chosen on the static route on purpose; the experiment asks whether live costs avoid a *reported* incident, not whether incidents happen there.
- Minimum-green truncation to 5 s for the corridor is a deliberate deviation from D2 FR-08 (context §50.15).
- The downstream-capacity check in D2 §5.6 is not implemented yet. The bounded compensation plan in recovery is also not implemented: ownership returns to normal control at once, and the safety filter keeps that hand-over legal.
