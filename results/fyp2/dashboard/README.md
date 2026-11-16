# W5 Dashboard v2: screenshots, store summary and export sample (real, 15–16 Nov 2026)

Every screenshot shows **one real live SUMO run**: run `20261115T233630Z_grid3x3_dqn_heavy_s0` (DQN, heavy demand, seed 0, synthetic 3×3 grid, TraCI backend). No value on any screen is mocked. The run is a demonstration: it has no warm-up and one seed, so it is not a D2 protocol result.

**How they were made.** Start the API with `python -m manzil.api` (after `cd dashboard && npm run build`). Then run:

```bash
API_PID=<pid of the API> NODE_PATH=$(npm root -g) node dashboard/scripts/capture_screens.mjs results/fyp2/dashboard
```

The script drives the dashboard with Playwright (Chromium, 1440×900, scale 2) and writes `capture_log.txt`.

## What happened in the run (`capture_log.txt`)

- **G01.** The configuration planned an ambulance `left0A0 → C2top2`, dispatched at 120 s with the corridor on, and a road closure of `B1C1` at 100 s.
- **Dispatch.** At 120 s the ambulance got route v1 `left0A0 > A0B0 > B0B1 > B1B2 > B2C2 > C2top2`.
- **Closure on the route.** At 121 s the script closed `B0B1`, the road two ahead of the ambulance, through the API. Route v2 (trigger `closure`) followed at 123 s, and the corridor gave A0 `ACTIVE_PRIORITY`.
- **Arrival.** The ambulance arrived at 234 s: 114 s travel time, 2 stops.
- **FR-02.** The run was paused, then resumed.
- **FR-16 fallback.** The operator injected an RL service loss at 510 s. From 515 s the DQN's own FR-20 fallback held the current phase, and the screen shows the count of held decisions.
- **FR-16 invalid.** The script closed `C1C2` and `B2C2` and dispatched a second ambulance to `C2top2`. It got `NO_ROUTE`, shown as invalid.
- **FR-16 stale.** The SUMO processes were frozen with `SIGSTOP` for 3.4 s. The API reported "no new simulation state for 3.4 s", then SUMO was resumed.
- **End of run.** The run was stopped at 701 s with **0 safety violations**, and imported into the store.
- **FR-16 disconnected.** Finally the API process itself was stopped. The browser shows DISCONNECTED and keeps the last values.

## Files

| File | What it shows |
|---|---|
| `01_g01_configuration.png` | G01: the form and a validation summary with every check; Start enabled |
| `01b_g01_validation_error.png` | G01: origin = destination is an error, so Start stays disabled |
| `02_g02_traffic_overview.png` | G02: live map (signals, queues, closures, route, corridor ring); run card with source, step and age; pause, stop and fault controls; vehicles and halting chart; emergency summary |
| `03_g03_perception_intersection.png` | G03: junction B1 from SUMO (approach table with units, signal owner, requested vs applied controls) and prepared UA-DETRAC results for MVI_40714 with provenance (model sha256, tracker, kernel, ground-truth source, "not live", no calibration), counts vs truth, queue proxy vs truth, tracked frame |
| `04_g04_emergency_dispatch.png` | G04: route v1 dashed and v2 current on the map; route-version table (trigger, cost, step); routing log; corridor lifecycle |
| `04b_g04_mission_arrived.png` | G04 after arrival: travel time and excess delay |
| `05_g05_comparative_analytics.png` | G05: `results/phase4/comparison`, heavy demand; comparability check passed; one dot per run with mean and 95 % CI; paired difference against fixed-time; seed coverage; run list; export |
| `05b_g05_comparability_warning.png` | G05: `results/phase3/corridor_v2/dqn` with both profiles, which triggers the mixed-profiles warning |
| `06_fr02_paused.png` | FR-02: paused run (status PAUSED, state still fresh) |
| `07_fr16_fallback.png` | FR-16: FALLBACK banner after the injected RL loss |
| `08_fr16_stale.png` | FR-16: STALE banner while SUMO was frozen |
| `09_fr16_disconnected.png` | FR-16: DISCONNECTED banner after the API was stopped |
| `10_fr16_invalid_no_route.png` | FR-16: INVALID banner (NO_ROUTE) on G04 |
| `capture_log.txt` | Times and values logged during the capture run |
| `store_summary.json` | Store built from the committed `results/` only (main after the W3 and W4 merges): 1,575 runs, 56,130 metric samples, 895 missions, 932 route versions, 24,645 priority events, 40 video jobs, 2,477 observations, 4,049 artifacts |
| `export_phase4_heavy.json`, `.csv` | FR-19 sample export: the 15 Phase 4 heavy runs (format in `manzil/store/README.md`) |

## Check against committed results

On the Phase 4 heavy runs, G05 shows:

- DQN mean travel time **155.68 s**;
- paired difference against fixed-time **−17.25 s ± 6.13 (95 % CI)**.

Both equal `results/phase4/comparison/summary.json`. The Phase 2 summary is reproduced exactly by `tests/test_w5_store.py`.
