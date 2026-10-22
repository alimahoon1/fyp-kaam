# Manzil Functional Prototype

This repository now contains a working local prototype of the Manzil traffic-management and emergency-routing proposal. The original proposal, report, template, and generated PDFs remain unchanged.

## What the prototype demonstrates

- Seeded traffic demand on a documented six-intersection synthetic network.
- Fixed-time, pressure-inspired adaptive, and labelled tabular-Q prototype controllers.
- Shared minimum-green/clearance safety handling.
- Dynamic time-based Dijkstra ambulance routing.
- Road closures, versioned rerouting, and no-route handling.
- Bounded moving green corridor with passage and recovery events.
- React operations dashboard with live traffic, signals, mission route, incidents, events, and metrics.
- Explicit mock-perception contract and matched controller comparison.
- Schema-versioned JSON evidence export.

The fallback simulator is not SUMO, the perception feed is not YOLO output, and the tabular policy is not the proposed DQN. See [the feasibility analysis](docs/FEASIBILITY_ANALYSIS.md) and [deviations](docs/DEVIATIONS.md).

## Run locally

Requirements: Python 3.9+, `uv`, Node.js 20+, and npm.

```bash
cd prototype/backend
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

The committed backend serves the latest built frontend at `http://127.0.0.1:8000/` after running:

```bash
cd prototype/frontend
npm install
npm run build
```

For frontend development, run `npm run dev` and use the Vite URL; `/api` is proxied to port 8000.

## Verify

```bash
cd prototype/backend && uv run pytest -q
cd prototype/frontend && npm run build
```

## Demonstration flow

1. Start the live run and observe queues and signals.
2. Change between fixed, adaptive, and tabular-Q prototype control.
3. Dispatch the ambulance from I-01 to I-06.
4. Click an active route road to close it and observe the versioned reroute.
5. Watch bounded corridor states and restoration of normal signal ownership.
6. Open **Evidence lab** to inspect the mock perception contract.
7. Run the matched comparison and download the current JSON evidence package.

## Documentation

- [Phased development plan](docs/DEVELOPMENT_PLAN.md)
- [Progress checklist](PHASE_CHECKLIST.md)
- [Continuation context](context.md)
- [Feasibility analysis](docs/FEASIBILITY_ANALYSIS.md)
- [Deviations](docs/DEVIATIONS.md)
