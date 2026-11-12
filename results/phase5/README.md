# Phase 5: dashboard v1 (tasks 5.1 and 5.2)

Screenshots of the real dashboard (`dashboard/`, React + TypeScript) served by the FastAPI service
(`manzil/api/`), taken on 12 Nov 2026 in a Claude Code cloud session with headless Chromium.
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

- Ambulance dispatched at 411 s, arrived at 608 s: response time 197 s (free-flow 78.9 s),
  6 stops; route revised once (trigger `closure`), route computation < 0.1 ms.
- Corridor: 6 junction activations, all served; 2 cancelled (route change), 1 timeout
  (60 s cap); mean recovery 16 s.
- Network safety monitor: 0 violations.
