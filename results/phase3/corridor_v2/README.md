# Task 3.7: green corridor v2 — why the ambulance still stopped, and what was changed

Real SUMO runs, 14 Nov 2026 (cloud session). Synthetic 3×3 grid, the Phase 3 corridor setup:
dynamic routing, no incident, ambulance dispatched at 1,200 s from `left0A0` to `C2top2`,
900 s warm-up + 900 s measurement, **medium and heavy demand, seeds 0–4**, every arm on the same
seeded demand (paired). Run twice: with the Phase 3 background controller (tuned fixed-time,
`fixed_time/`) and with the DQN (`dqn/`), because Ibrahim's laptop demo that showed the
problem used the DQN. Nothing is simulated beyond SUMO itself; nothing was retrained.

Reproduce:

```bash
python -m manzil.experiments.corridor_v2_study --out results/phase3/corridor_v2/fixed_time
python -m manzil.experiments.corridor_v2_study --controller dqn --out results/phase3/corridor_v2/dqn
python -m manzil.experiments.corridor_v2_study --demo --out results/phase3/corridor_v2/demo_scenario
python -m manzil.experiments.corridor_v2_report results/phase3/corridor_v2
```

## How "why it stopped" is measured

Every second the ambulance stands still (speed < 0.1 m/s, after it has entered the network),
`MissionDriver` asks SUMO for its next traffic light and its leader and records one reason
(`amb_stop_reasons` in `metrics.json`, one row per second in `mission.json` → `stop_log`):

| Group (plots/tables) | Reasons | Meaning |
|---|---|---|
| red, corridor junction | `red_corridor_not_active`, `_min_green`, `_clearance`, `_other` | first in line at a red; the junction has a corridor request (not yet active / filter finishing min green / yellow or all-red) |
| red, outside look-ahead | `red_outside_lookahead` | first in line at a red with **no** corridor request for that junction |
| queue in front | `queue_at_red`, `queue_at_green` | other vehicles between the ambulance and the stop line |
| other | `inside_junction`, `green_blocked`, `no_signal_ahead` | waiting inside a junction (e.g. a permissive left turn yielding to oncoming traffic) or first at a green but blocked |
| red, corridor off | `red_no_corridor` | first at a red, corridor switched off |

Decision 11 check: every stop line the ambulance crosses is logged with the signal shown at that
moment (`signal_crossings`); `amb_red_crossings` must be 0 (it is 0 in every run here).

Ordinary-traffic cost: **cross-street queueing** = halting vehicles summed over the 600 s after
dispatch on the approaches that get no green in the ambulance's phase, at every junction it
drove through (veh·s); **network queue** = mean halting vehicles in the same 600 s (the same
window in every arm, so a faster ambulance does not shorten its own window). Also kept: the
Phase 3 metric "network queue, mission + 300 s".

## Finding 1: a bug — after a reroute the corridor skipped the junction right ahead

SUMO's `setRoute` keeps the edges already driven at the front of the vehicle's route, so SUMO's
route index stays ahead of Manzil's route plan (which starts at the current edge). The corridor
used SUMO's index, so after **every route revision** it skipped the next junction and the
ambulance met an ordinary red there. The Phase 3 fixed-time corridor runs had no route revisions,
so their published numbers were not affected; the DQN runs and the dashboard demo (closure →
reroute) were. Fix: the corridor now finds the ambulance's position in the plan by its edge
(`CorridorCoordinator._plan_index`), test `tests/test_corridor_v2.py`.

Evidence (`dqn_before_fix/`, same seeds, old code): DQN, heavy, seed 0 — the ambulance waited
**65 s at red lights with no corridor request** (mean over 5 seeds: 13 s "red, outside
look-ahead"). With the fix (`dqn/`, arm `v1`) that is 0 s, and the mean response time drops
from 149.4 s to 130.6 s.

## Finding 2: what the ambulance waits for once the bug is fixed

With the v1 corridor the ambulance is **never** stopped first in line at a red light at a
corridor junction (0 s in all 20 runs per controller). Its remaining stops are: queues in front
of it that are still discharging (most of the time), and waiting inside a junction, mainly the
last left turn at C2, which is permissive (`g`) in the grid's two-phase programs, so it yields to
oncoming traffic. See `stop_reasons.png`.

## Finding 3: the four candidate changes (one at a time vs `v1`, then combined)

Mean of 5 seeds; Δ = paired difference vs `v1`, with the number of seeds that improved. Full
table: `key_table.md` / `key_table.csv`; per run: `*/results.csv`, `*/runs/*/metrics.json`.

| Background, demand | v1 response | early30 (look-ahead 3) | trunc5 | giveway | combined | cost of early30 (cross-street) |
|---|---|---|---|---|---|---|
| fixed-time, medium | 103.2 s | −1.4 s (2/5) | −0.6 s (1/5) | +0.4 s (2/5) | −2.8 s (4/5) | +9.6 % |
| fixed-time, heavy | 136.0 s | −2.0 s (3/5) | **−8.2 s (4/5)** | −7.4 s (2/5) | **+51.2 s (2/5)** | +14.2 % |
| DQN, medium | 103.4 s | −2.2 s (4/5) | −2.4 s (3/5) | +0.2 s (3/5) | −6.6 s (5/5) | +6.9 % |
| DQN, heavy | 130.6 s | −8.0 s (3/5) | **−6.4 s (5/5)** | −8.8 s (5/5) | −19.8 s (5/5) | +13.8 % |

- **Earlier activation (25 or 30 s) + look-ahead 3:** small and inconsistent gains (early25 is
  worse on DQN heavy), always at a clear ordinary-traffic cost (cross-street queueing +4 to +14 %,
  network queue up to +11 vehicles) because junctions are held longer; with fixed-time heavy it
  also caused a few seconds of red waits at corridor junctions (priority held to its 60 s limit,
  then timed out). **Not kept.**
- **Emergency truncation of minimum green to 5 s** (corridor requests only; yellow 3 s and
  all-red 2 s kept): helps on heavy demand (−8.2 s, 4/5 seeds; −6.4 s, 5/5 seeds), neutral on
  medium, and costs ordinary traffic nothing measurable (cross-street queueing +2.4 % / −3.7 %,
  network queue −1.0 / −1.5 vehicles). 0 safety violations. **Kept.**
- **Ordinary vehicles give way (SUMO bluelight device):** that device makes the ambulance run red
  lights (speed mode 7: 1–2 red crossings per run in a first test). Speed mode 31 is set again so
  the ambulance stops at red (0 red crossings in every run). Even so it is **not kept**: without
  SUMO's sublane model the "rescue lane" behaviour causes gridlocks — teleports appear only in the
  give-way arms (1 in fixed-time heavy, 2 in DQN heavy, 2 + 2 in `combined`), and in `combined`
  fixed-time heavy seed 1 the ambulance itself was stuck 300 s inside junction C2 (416 s response,
  vs 135 s with trunc5). Switching the whole simulation to the sublane model would change every
  earlier result, so it is left for FYP-2.
- **Combined (early30 + trunc5 + giveway):** best mean on DQN but has the give-way gridlocks and the
  early-activation cost; `early30_trunc5` (no give-way) is no better than trunc5 alone and costs
  +8 to +15 % cross-street queueing. **Not kept.**

## The new default (`v2`) and the reruns

`v2` = v1 + the route-index fix + minimum-green truncation to 5 s for corridor requests
(`scenarios/grid3x3/signals.json`, version 6, `corridor_min_green_s: 5`). Look-ahead 2 and
activation at ETA ≤ 15 s + queue clearance are unchanged. `v2` gives exactly the `trunc5`
numbers above (same runs, deterministic).

- Phase 3 corridor comparison rerun with v2: `results/phase3/corridor/` (see
  `results/phase3/README.md`).
- **Phase 5 demo scenario replayed headless** (`demo_scenario/`: DQN, heavy, 3,600 s without
  warm-up as in the dashboard, dispatch at 411 s, road `B0B1` closed 2 s later, seeds 0–4):
  response time off 258.4 s → v1 (with the fix) 145.2 s → **v2 128.6 s** (Δ −16.6 s vs v1, 5/5
  seeds); time stopped 23.8 → 10.8 s; 0 red crossings; 0 safety violations. Teleports (mean per
  run): off 0.2, v1 1.2, v2 0.4 — this scenario has no warm-up and heavy demand, so jams form.
- **Live dashboard demo** rerun with the same clicks (`results/phase5/`): dispatched at 411 s,
  arrived at 575 s, **response 164 s** (was 197 s on 12 Nov), 3 stops (was 6), all 30 s of
  stopping were queues in front at green lights, 0 red crossings, 0 safety violations. This is
  the same as the headless replay of seed 0 (164 s).

## Files

| File | What it is |
|---|---|
| `stop_reasons.png` | Ambulance time stopped, by reason, per arm (both controllers, both demands) |
| `response_and_cost.png` | Response time and ordinary-traffic cost per arm; dots = seeds, bar = mean |
| `key_table.md`, `key_table.csv` | Means, paired differences vs v1 and seeds better, for all studies |
| `fixed_time/`, `dqn/` | `results.csv` (one row per run), `summary.md/json` (paired 95 % CIs vs v1), `runs/*/{manifest,metrics,mission}.json` |
| `demo_scenario/` | The Phase 5 demo scenario replayed headless, arms off / v1 / v2 |
| `dqn_before_fix/` | Arms off and v1 with the code before the route-index fix (DQN), the evidence for Finding 1; `run_dir` paths point to the session's scratch folder where they were run |

Limits: one network, one origin–destination pair, 5 seeds (not the D2 10-seed protocol), a
single 900 s mission window per run. All ambulance speeds are now exactly the speed limit (the
ambulance type had SUMO's default ±10 % speed spread; fixed in this task, so all Phase 3 numbers
were rerun).
