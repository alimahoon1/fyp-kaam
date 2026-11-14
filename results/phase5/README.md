# Phase 5: dashboard v1 (tasks 5.1 and 5.2)

Screenshots of the real dashboard (`dashboard/`, React + TypeScript) served by the FastAPI service
(`manzil/api/`), taken on 12 Nov 2026 and **retaken on 14 Nov 2026 with the corridor v2 (task 3.7)**, in Claude Code cloud sessions with headless Chromium.
Every value on screen comes from a live SUMO run; nothing is mocked.

How they were produced:

```bash
python -m manzil.api                        # API + built dashboard on :8000
node scripts/dashboard_screenshots.js       # drives the page, saves the files below
```

The script starts a run through the UI (DQN controller, heavy demand, seed 0, 10x real time),
dispatches the ambulance through the UI (default `left0A0` -> `C2top2`, corridor on), closes road
`B0B1` (on the first route) through the API, and stops the run after arrival.

| File | Shows |
|---|---|
| `01_idle.png` | Map built from `scenarios/grid3x3/grid3x3.net.xml` before a run |
| `02_running_dqn_heavy.png` | Running: vehicles, signal colours at each stop line, queue shading |
| `03_closure_reroute.png` | `B0B1` closed (red X); route v2 (`closure`) in blue; corridor requests |
| `04_corridor_active.png` | A junction held green for the ambulance (ACTIVE_PRIORITY ring) |
| `05_arrived.png` | Mission ARRIVED with response time, stops and corridor event log |
| `demo_run_state.json` | API state at arrival (the numbers below) |

Result of this one demo run (one seed, one mission, timing of the dispatch depends on when the
script clicked; this is a demonstration, not an experiment; the controlled comparisons are in
`results/phase3/` and `results/phase4/`):

- **14 Nov (corridor v2):** ambulance dispatched at 411 s, arrived at 575 s: response time
  **164 s** (free-flow 78.9 s), **3 stops**; route revised once (trigger `closure`). The ambulance
  stood still for 30 s, all of it in queues in front of it at green lights; 0 s at red lights,
  0 stop lines crossed on red (Decision 11 check). Corridor: 7 activations, all served;
  3 cancellations (2 of them the 60 s priority cap timing out); mean recovery 14.5 s.
  Safety monitor: 0 violations. Values from `demo_run_state.json`.
- **12 Nov (corridor v1, previous screenshots):** same dispatch time, response 197 s, 6 stops,
  6 activations, 1 timeout. Part of that delay was a bug fixed in task 3.7: after the closure
  reroute the corridor skipped the junction right ahead, so the ambulance met ordinary reds.
- The same scenario replayed headless on seeds 0–4 (`results/phase3/corridor_v2/demo_scenario/`)
  gives 145.2 s (v1 with the fix) → 128.6 s (v2), 5/5 seeds better; seed 0 is 164 s, identical
  to this live run.
