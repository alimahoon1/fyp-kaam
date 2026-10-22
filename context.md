# Manzil Prototype Context

## Project overview

Manzil is a traffic-management research prototype combining traffic observation, comparable signal controllers, dynamic emergency routing, a moving green corridor, and a monitoring dashboard. The immutable proposal/report are the specification and have not been edited.

## Current progress

Phases 0, 1, 2, 3, and 5 are complete. Phase 4 implementation and build verification are complete; its in-app visual browser QA remains open because no browser surface was available. Phase 6 automated validation and documentation are complete.

## Phase completion log

- **Phase 0:** proposal/report scope locked; feasibility substitutions and acceptance boundary documented.
- **Phase 1:** FastAPI and React workspaces, source-labelled contracts, health/configuration/state APIs, and build tooling verified.
- **Phase 2:** deterministic demand, fixed/adaptive/tabular prototype control, shared clearance handling, metrics, and reproducibility tests completed.
- **Phase 3:** time-based Dijkstra dispatch, ambulance movement, bounded corridor, road closure, route-version revision, passage, recovery, and arrival verified.
- **Phase 4:** complete operations/evidence dashboard implemented, built, and served locally; visual browser QA remains explicitly open.
- **Phase 5:** mock perception contract, matched controller comparison, limitations disclosure, and JSON export verified.
- **Phase 6:** unit/integration tests, production build, HTTP checks, API smoke flow, preservation audit, README, checklist, and continuation context completed.

## Implemented architecture

- `prototype/frontend`: React, TypeScript, Vite, and a responsive traffic-operations dashboard.
- `prototype/backend`: FastAPI command/query boundary and static frontend host.
- `app.engine.Engine`: sole owner of fallback simulation time and state.
- `app.network`: documented six-intersection synthetic graph with alternative routes.
- Controller registry behavior: fixed, pressure-inspired adaptive, and labelled tabular-Q prototype.
- Shared safe signal request path with minimum-green and clearance behavior.
- Dynamic time-based Dijkstra routing with closures, thresholds, route versions, and no-route state.
- One active ambulance mission with movement, stops, arrival, and reroute count.
- Bounded moving corridor with requested, active-priority, passage, cancellation, and normal-ownership recovery behavior.
- Explicit `prototype-sim` and `mock-perception` source modes.
- Matched-seed controller comparison and schema-versioned JSON export.

## Functional dashboard workflows

1. Start/pause repeated simulation steps.
2. Select balanced, north-south pressure, or rush-hour demand.
3. Switch among the three controller modes.
4. Inspect queue levels, signals, traffic metrics, and the audit trail.
5. Dispatch one ambulance from I-01 to I-06.
6. Observe the selected route, route version, live progress, stops, and bounded corridor.
7. Click a road to close/reopen it; a closure on the remaining path forces a versioned reroute.
8. Inspect explicitly labelled mock perception observations.
9. Run a matched fallback-simulator controller comparison.
10. Download the current run manifest, state, events, perception metadata, and limitations as JSON.

## Verification evidence

- Backend: `8 passed` using `uv run pytest -q`.
- Frontend: TypeScript and Vite production build completed successfully.
- HTTP: `/api/health` and the built `/` page returned 200.
- End-to-end smoke: reset -> dispatch -> close active road -> route version increased from 1 to 2 -> ambulance arrived after 22 mission steps -> comparison returned all controllers.
- Reproducibility: two seeded adaptive runs produce equal metrics.
- Signal invariant: all controllers expose only EW, NS, or CLEARANCE states.
- Proposal preservation: Git shows no modifications to proposal/report/template source files.
- Visual browser QA: not completed because the local browser-control surface reported no available browser.

## Important observed result

The current fallback simulator does not make adaptive control artificially win. In the verified rush-hour matched run, fixed timing outperformed the simple adaptive and tabular prototype policies on some measures. This is retained as honest prototype evidence, not tuned away. It is not a SUMO or academic result.

## Known limitations

- The current runtime is a compact queue-based fallback, not SUMO/TraCI microscopic simulation.
- The network is synthetic and must not be described as Lahore.
- The perception panel uses synthetic observations and does not run YOLO or a tracker.
- The tabular-Q prototype is not the proposed parameter-sharing DQN and has no trained checkpoint.
- Runtime state is in memory; PostgreSQL is not connected.
- Controller comparison uses one fallback-simulator seed from the UI, not the report's final ten-seed SUMO protocol.
- Corridor state is intentionally simplified for demonstrability; certified real signal timing is out of scope.

## Deviations and rationale

See `docs/DEVIATIONS.md` and `docs/FEASIBILITY_ANALYSIS.md`. The implementation alternatives preserve source disclosure, single ownership, safe action filtering, route versions, bounded priority, failure visibility, and exportable evidence.

## Remaining tasks for the next implementation stage

1. Complete visual browser QA when a browser surface is available; check responsive layout and every control.
2. Install SUMO, implement a `SumoAdapter`, and validate a small network before importing OSM.
3. Select the Lahore bounding box and version the cleaned network, routes, signals, and demand.
4. Acquire licensed video and annotations; implement a bounded YOLO/tracker worker against the existing perception contract.
5. Implement durable run persistence through a repository adapter.
6. Train and evaluate the proposed parameter-sharing DQN only after fixed and pressure baselines are stable in SUMO.
7. Execute the declared warm-up, measurement interval, ten matched seeds, held-out scenarios, variability reporting, and emergency ablations.

## Commands

```bash
cd prototype/backend
uv sync --extra dev
uv run pytest -q
uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd prototype/frontend
npm install
npm run build
```

After the frontend build, FastAPI serves the complete application at `http://127.0.0.1:8000/`.
