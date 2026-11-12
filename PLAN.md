# Manzil — Work Plan

Status values: `todo` · `in progress (Name)` · `done` · `blocked (reason)`.
Before starting a task, set it to `in progress (Name)` and push. When finished, set it to `done`, note the evidence (commit, result file), and push. See `CLAUDE.md`.

## Current stage

Planning is finished (10 Nov 2026). **Phase 0 done. Phases 1–5 done; vision V.1–V.3 done.** Next: vision V.4 (tracking + counting), Phase 6 report chapters. Coding phases 1–5 mostly run as Claude Code cloud sessions (claude.ai/code), with Ibrahim checking from the phone app.** The vision track (V) can run in parallel at any time after Phase 0 step 0.4.

## Deliverable III requirements (from the university)

- Chapters 1–6 updated, with supervisor feedback incorporated (D2 feedback was positive; main demand is working code)
- Chapter 7: Implementation and Test Cases
- Chapter 9: Experimental Results and Discussion
- Chapter 10: Conclusion and Future Work, including a mandatory FYP-2 plan

## Decisions

| # | Decision |
|---|---|
| 1 | No fixed date to plan around. Target is real coding + real model training + visible output for evaluators. |
| 2 | Train both models: YOLO vision as a parallel track; DQN signal control after SUMO + baselines. |
| 3 | GPU training on Kaggle, driven through the Kaggle API/CLI. |
| 4 | Ibrahim + Claude do most of the work; teammates also use Claude from this same repo plan. |
| 5 | `CLAUDE.md` + `PLAN.md` coordinate all sessions; Claude commits and pushes automatically after each work session. |
| 6 | D2 feedback was positive; main demand is working code at the next evaluation. Chapters 1–6 only need a light update to match the real implementation. |
| 7 | Start fresh around SUMO. The old prototype is archived in `archive/prototype_v0/` and not built on. |
| 8 | Network: synthetic 3×3 SUMO grid first, then a Lahore OSM area (10–20 signals + hospital). All code must read the network from the SUMO files (network-agnostic). **Lahore area/hospital: open, to decide later.** |
| 9 | Video: train on UA-DETRAC; test also on 2–3 own Lahore clips. Labelling is AI pre-labelled + human-corrected; test labels must be human-verified; local clips can use manual line-crossing counts. |
| 10 | YOLO classes for FYP-1: car, bus, truck, motorcycle. Rickshaw is added in FYP-2 with labelled Lahore footage. |
| 11 | The ambulance obeys red lights; only the Manzil corridor speeds it up (measured as corridor off vs on). SUMO's run-the-reds mode is an optional later upper-bound comparison. |
| 12 | FYP-1 scope = balanced option: grid + fixed/adaptive/DQN + comparison + ambulance routing/rerouting + corridor + YOLO track + simple dashboard. Lahore map, full dashboard/DB, full 10-seed protocol, rickshaw, and video→SUMO go to FYP-2. |

## Defaults chosen without a separate question (change if needed)

- Language: Python 3.10+ for everything except the dashboard frontend (React + TypeScript). Backend API: FastAPI.
- SUMO via TraCI during development; `libsumo` (faster, same API) for training and batch runs.
- One `SimulationAdapter` is the only code that steps SUMO or changes signals (D2 rule). Every controller goes through one safety filter (min green, yellow, all-red).
- Results stored as files first (CSV/JSON per run + manifest). A database (SQLite/PostgreSQL behind one interface) comes in FYP-2.
- YOLO: Ultralytics (YOLOv8 or YOLO11, small variant), with ByteTrack from the same library. The exact version is pinned when the task starts.
- Ambulance detection from video stays out of scope (not in D2). In simulation the ambulance is spawned deliberately.
- Large files (datasets, videos, weights) stay out of git; they go to Kaggle datasets, with the link and checksum recorded here.

## Planned repository layout

```
manzil/                 Python package (the new system)
  sim/                  SimulationAdapter (TraCI/libsumo), snapshots, metrics
  control/              fixed, pressure-adaptive, DQN controllers + safety filter
  routing/              graph from .net.xml, edge costs (Eq 5.4), Dijkstra/A*, rerouting (Alg 1)
  corridor/             corridor state machine (Alg 2)
  experiments/          run config, runner, batch comparisons, manifests
  perception/           YOLO + tracker + counting pipeline
  api/                  FastAPI service for the dashboard
scenarios/grid3x3/      SUMO network, demand files, configs (later: scenarios/lahore_<area>/)
dashboard/              React + TypeScript frontend
kaggle/                 Kaggle notebooks/scripts + kernel-metadata.json
tests/                  unit + invariant + small-SUMO integration tests
results/                small result summaries/plots kept in git (raw bulk outputs ignored)
```

## Phases and tasks

### Phase 0 — Setup
| ID | Task | Status | Done when |
|---|---|---|---|
| 0.1 | Install SUMO on Ibrahim's laptop, set `SUMO_HOME`, check `sumo`, `sumo-gui`, `netgenerate` | done: SUMO 1.28.0 via pip `eclipse-sumo` in `.venv`; `SUMO_HOME` set (user env); 3×3 grid smoke test ran with 9 TLS | `sumo --version` works |
| 0.2 | Create the `manzil/` Python project (pyproject, pinned deps, lint/format, pytest) | done: `pyproject.toml`, `manzil/` skeleton, `manzil/sumo_env.py`, `tests/test_setup.py` (4 passed), ruff clean | `pytest` runs green on an empty test |
| 0.3 | Write setup instructions in `README.md` so a teammate's machine can reproduce the setup | done (Windows steps verified; `scripts/cloud_setup.sh` verified on Linux in the first cloud session, 9 Nov, after fixing a non-fatal pip upgrade) | A fresh clone can follow the steps |
| 0.4 | Kaggle: account with phone verification, `kaggle.json` placed by the user, `pip install kaggle`, test `kaggle kernels list` | done (12 Nov): new-style API token (no kaggle.json any more) on laptop (`~/.kaggle/access_token`, CLI 2.2.5 on Python 3.13) and in the cloud environment (`KAGGLE_API_TOKEN`); test kernel `kaggle/gpu_test` ran with 2× Tesla T4 + internet | CLI works |
| 0.5 | Claude Code cloud: install the Claude GitHub app on `alimahoon1/fyp-kaam` (repo owner Ali may need to approve), create a claude.ai/code environment with setup script `bash scripts/cloud_setup.sh`, install the Claude phone app with notifications; first cloud task verifies the setup | done: cloud session ran `pytest` green (9 Nov). Environment setup script corrected to `cd fyp-kaam` first, because it runs from the folder above the repo | A cloud session runs `pytest` green |

### Phase 1 — SUMO foundation (grid + fixed-time)
| ID | Task | Status | Done when |
|---|---|---|---|
| 1.1 | Generate the 3×3 grid (`netgenerate`) with signalised junctions; inspect in `sumo-gui` | done (cloud, 9 Nov): `manzil/scenarios/grid.py` → `scenarios/grid3x3/grid3x3.net.xml` + `network.json`; 9 TLS, 4-arm junctions, checked headless by `tests/test_grid.py`. A `sumo-gui` look on the laptop is still worth doing (command in `scenarios/grid3x3/README.md`) | Network opens; 9 traffic lights |
| 1.2 | Demand profiles: light, medium, heavy, uneven (seeded `randomTrips`/flows) | done (cloud, 9 Nov): `manzil/scenarios/demand.py` (own seeded Poisson generator + `duarouter`, used instead of `randomTrips`), `manzil/scenarios/check.py`; all 4 profiles × seeds 0–4 gridlock-free with default signals → `results/phase1/demand_check.json` | Each profile runs without gridlock in light |
| 1.3 | `SimulationAdapter`: start/step/stop, subscriptions, read lanes/signals, apply phases (sole owner) | done (cloud, 9 Nov): `manzil/sim/adapter.py` (libsumo + traci backends, lane/TLS/sim subscriptions → `TrafficSnapshot`, only module importing TraCI, enforced by `tests/test_adapter.py`), contracts in `manzil/sim/contracts.py` | Integration test steps SUMO and reads state |
| 1.4 | Network reader: junctions, TLS programs, phases, lanes, connections from `.net.xml` (network-agnostic) | done (cloud, 9 Nov): `manzil/sim/network.py`: links, approaches, green phases, foe/yield matrices from `.net.xml`; conflict check; tested on the 3×3 grid and a generated 4×4 grid | Works on the grid with no hard-coded IDs |
| 1.5 | Safety filter: min green, yellow, all-red; requested vs applied record | done (cloud, 9 Nov): `manzil/control/safety.py`: `SafetyFilter` (min green 10 s, yellow 3 s, all-red 2 s; `AppliedControl` requested vs applied) + independent `SafetyMonitor`; a random controller over 5,000 steps and in real SUMO produced 0 violations (`tests/test_safety.py`) | Invariant test: no conflicting greens ever applied |
| 1.6 | Fixed-time controller (declared cycle per junction) | done (cloud, 9 Nov): `manzil/control/fixed_time.py` + `scenarios/grid3x3/signals.json`; plans tuned per profile on dev seeds 100–101; full 900 + 3,600 s runs for all 4 profiles, seed 0 → `results/phase1/fixed_time_seed0.json` | Runs a full scenario |
| 1.7 | Metrics + run manifest: waiting time, queue mean/max, throughput, travel time, phase changes; config, seed, versions | done (cloud, 9 Nov): `manzil/experiments/runner.py` + `metrics.py`: run folder with `manifest.json` (config, seed, versions, git commit, checksums, termination) and `metrics.json` (metric version 1), time series, signal events, applied controls | One run produces a manifest + metrics files |
| 1.8 | Reproducibility check: same seed gives the same metrics | done (cloud, 9 Nov): `tests/test_runner.py`: same seed → identical metrics (also libsumo vs traci); a full-length heavy rerun was also identical | Test passes |

### Phase 2 — Rule-adaptive control + first comparison
| ID | Task | Status | Done when |
|---|---|---|---|
| 2.1 | Pressure-based adaptive controller (Eq 5.2: pressure + wait term, min/max green, max-red promotion) | done (cloud, 10 Nov): `manzil/control/adaptive.py` (Eq 5.2, min/max green, max-red promotion, hysteresis, min hold; scores in every request); one parameter set frozen after 60 dev-seed settings → `results/phase2/adaptive_tuning_dev_seeds.csv` | Runs; explanation fields recorded |
| 2.2 | Batch runner: controller × demand × seeds (FYP-1: about 3–5 seeds, shorter runs) | done (cloud, 10 Nov): `manzil/experiments/batch.py`: parallel arms × profiles × seeds → `results.csv`, FR-18 compatibility check; 60 full runs take about 100 s on 4 cores | One command produces a results table |
| 2.3 | First comparison: fixed vs adaptive, with plots | done (cloud, 10 Nov): `manzil/experiments/compare.py`; fixed (tuned) vs fixed (one plan) vs adaptive, seeds 0–4, 900 + 3,600 s → `results/phase2/comparison/` (`summary.md`, `comparison.png`) | Results + plots in `results/` |

### Phase 3 — Ambulance routing, rerouting, green corridor
| ID | Task | Status | Done when |
|---|---|---|---|
| 3.1 | Routing graph from SUMO legal movements; time-based edge cost (Eq 5.4) | done (cloud, 10 Nov): `manzil/routing/graph.py`: edge graph from SUMO connections (vClass emergency), Eq 5.4 costs (free flow + queue + declared signal delay + closure; reported speed limits), tests for no double counting | Unit tests on costs, no double counting |
| 3.2 | Dijkstra (reference) + A* (admissible heuristic) + no-route handling | done (cloud, 10 Nov): Dijkstra + A* with an admissible heuristic (scaled for junction interiors); A* = Dijkstra on 200 random cost sets; NO_ROUTE handled | Same cost as Dijkstra on tests |
| 3.3 | Ambulance dispatch A→B (obeys signals), route versioning | done (cloud, 10 Nov): `manzil/experiments/emergency.py`: ambulance (obeys signals) dispatched A→B with route versions; arrives in every test and experiment run | Ambulance reaches B |
| 3.4 | Road-closure incident + rerouting (Alg 1: threshold, persistence, cooldown) | done (cloud, 10 Nov): `manzil/routing/mission.py` (Algorithm 1: threshold, persistence, cooldown); a closure on the route triggers v2 and cancels obsolete priority (`tests/test_emergency.py`) | Closure triggers a new route version |
| 3.5 | Corridor state machine (Alg 2: REQUESTED → SAFE_TRANSITION → ACTIVE → PASSAGE → RECOVERY), bounded look-ahead | done (cloud, 10 Nov): `manzil/corridor/coordinator.py` (Algorithm 2: REQUESTED → SAFE_TRANSITION → ACTIVE_PRIORITY → PASSAGE → RECOVERY → IDLE, look-ahead 2, max priority 60 s, timeout, ownership through the safety filter); 0 safety violations | Invariant tests; recovery to normal control |
| 3.6 | Emergency experiments: static vs dynamic route; corridor off vs on; ordinary-traffic impact | done (cloud, 10 Nov): `results/phase3/` (static vs dynamic −53 % / −49 % ambulance time; corridor −33 % / −57 % at a cost of +3.5 % / +5.8 % network queue), see `results/phase3/README.md` | Results + plots |

### Phase 4 — DQN signal control
| ID | Task | Status | Done when |
|---|---|---|---|
| 4.1 | RL environment on top of `SimulationAdapter` (state, action mask, reward Eq 5.3) | done (cloud, 10 Nov): `manzil/control/rl_env.py`: shared 26-value observation, masked actions, Eq 5.3 reward; random policy safe (`tests/test_rl.py`) | Random policy runs safely through the safety filter |
| 4.2 | Parameter-sharing DQN; train on the grid (laptop CPU or Kaggle with `eclipse-sumo` + `libsumo`) | done (cloud, 10 Nov): parameter-sharing Double DQN trained 200 episodes on CPU in the cloud (17 min); `models/dqn/grid3x3/best.pt` + `training_curve.png`, `training.json` | Training curve + saved checkpoint |
| 4.3 | Evaluate the DQN vs fixed vs adaptive on held-out seeds | done (cloud, 10 Nov): `results/phase4/`: DQN −9 % to −11 % travel time vs tuned fixed-time on all profiles, 5/5 held-out seeds; longer max red (≤ 89 s, guarded by the new 90 s max-red rule in the safety filter) | Three-way results + plots |

### Phase V — Vision track (parallel)
| ID | Task | Status | Done when |
|---|---|---|---|
| V.1 | Get UA-DETRAC on Kaggle; convert to YOLO format; class mapping (car/bus/truck; van→car, others→truck, to confirm) | done (cloud, 11 Nov): `kaggle/yolo_data` kernel `manzil-yolo-data` (output = dataset, attached by `kernel_sources`); mapping confirmed (DETRAC types are only car/van/bus/others): car, van→car, bus, others→truck; 7,365 / 867 / 5,625 train/val/test frames, val split by whole sequence → `results/vision/dataset_stats.json` | Dataset version on Kaggle |
| V.2 | Add a motorcycle-containing source so motorcycles aren't forgotten | done (cloud, 11 Nov): 3,502 COCO train2017 images with motorcycles (3,202 train, 300 val), all 4 classes labelled; COCO val2017 motorcycle images (159) kept as a separate motorcycle test set | Merged dataset with 4 classes |
| V.3 | Fine-tune YOLO on Kaggle GPU via the CLI; pull back weights + metrics | done (cloud, 12 Nov): YOLO11s, 50 epochs on 2× T4 (1.8 h). UA-DETRAC test mAP50 0.799 / mAP50-95 0.586 (pretrained 0.752 / 0.530); motorcycle mAP50 0.749 (pretrained 0.761); truck recall weak (0.46). `results/vision/README.md`, `models/yolo/manzil_yolo11s_best.pt` | mAP/precision/recall on the UA-DETRAC test split |
| V.4 | Tracking (ByteTrack) + line-crossing counting + queue proxy on video | in progress (Ibrahim, cloud) | Annotated output video + counts CSV |
| V.5 | Count error (MAE) on held-out clips | in progress (Ibrahim, cloud) | MAE table |
| V.6 | Film 1–2 Lahore clips; AI pre-label + human-verify a small test set; manual counts | deferred (12 Nov: skipped for now by Ibrahim; kept on the list; do if time allows, else FYP-2) | Local-domain accuracy + MAE |

### Phase 5 — Simple dashboard v1
| ID | Task | Status | Done when |
|---|---|---|---|
| 5.1 | FastAPI service: start/stop run, select controller, dispatch ambulance, close road, stream state | done (cloud, 12 Nov): `manzil/api/` (`app.py` FastAPI + WebSocket state stream, `live.py` step-wise live run in a worker thread using the same Algorithm 3 loop as the runner); start/stop, speed, controller fixed/adaptive/DQN, dispatch ambulance, close road; 13 tests in `tests/test_api.py` (full suite 127 passed) | API tests |
| 5.2 | React dashboard: live map from network geometry, signal states, ambulance + route + corridor status | done (cloud, 12 Nov): `dashboard/` (Vite + React 19 + TypeScript, SVG map from the `.net.xml`): signal colours per link, vehicles, queue shading, ambulance + route + corridor states, closures; screenshots of a live DQN/heavy run in `results/phase5/`; Windows steps in `README.md` | Demo-able in a browser |

### Phase 6 — Deliverable III report and demo
| ID | Task | Status | Done when |
|---|---|---|---|
| 6.1 | Light update of Chapters 1–6 to match the real implementation | todo | Compiles |
| 6.2 | Chapter 7: Implementation and Test Cases (modules, key code, test-case tables) | todo | Compiles |
| 6.3 | Chapter 9: Experimental Results and Discussion (controllers, emergency, vision) | todo | Real numbers only |
| 6.4 | Chapter 10: Conclusion + FYP-2 plan | todo | Compiles |
| 6.5 | Demo script + presentation | todo | Rehearsed |

## FYP-2 backlog (goes into the Chapter 10 plan)

- Lahore OSM network (area + hospital to choose), cleanup, validation; rerun all experiments on it
- Full D2 protocol: 10 matched seeds, 900 s warm-up + 3,600 s measurement, held-out scenarios, CIs
- Full five-screen dashboard (G01–G05) + database (SQLite/PostgreSQL behind a repository interface)
- Rickshaw (and van) classes with labelled Lahore footage
- Video-to-SUMO integration study (camera counts feeding a simulated junction)
- Optional: SUMO run-the-reds upper-bound comparison; observation-noise robustness study

## Open items

- Lahore area + hospital (decide before FYP-2)
- Who films the Lahore clips, and where
- Is Chapter 8 (User Manual) required for Deliverable III? Assumed **no**.
