# Manzil Prototype Development Plan

## Phase 0 - Analysis and scope lock

- **Objectives:** establish immutable sources, feasibility limits, and acceptance boundary.
- **Tasks:** inspect proposal/report; inventory repository; check SUMO, Python, and Node availability; document alternatives.
- **Dependencies:** existing proposal and Deliverable-2 report.
- **Deliverables:** feasibility analysis, phased plan, checklist, initial context.
- **Completion criteria:** every unavailable dependency has a labelled alternative and proposal files remain unchanged.

## Phase 1 - Foundation and contracts

- **Objectives:** create maintainable backend/frontend structure and shared domain contracts.
- **Tasks:** configure FastAPI and React/TypeScript; define scenario, snapshot, signal, mission, route, corridor, event, and metrics schemas; add health/config endpoints.
- **Dependencies:** Phase 0 scope decisions.
- **Deliverables:** runnable application skeleton and contract tests.
- **Completion criteria:** backend tests pass, frontend builds, and source mode/version fields are exposed.

## Phase 2 - Traffic simulation and controller baselines

- **Objectives:** produce observable traffic behavior and comparable legal signal decisions.
- **Tasks:** implement deterministic network/demand model; fixed controller; pressure-inspired controller; tabular-Q prototype controller; safety filtering; run metrics.
- **Dependencies:** Phase 1 contracts.
- **Deliverables:** step/run API, controller selection, metrics, and automated invariant tests.
- **Completion criteria:** seeded runs are reproducible, queues evolve, controllers share constraints, and incompatible greens cannot occur.

## Phase 3 - Emergency routing and moving corridor

- **Objectives:** demonstrate the proposal's central ambulance scenario.
- **Tasks:** implement time-based Dijkstra routing; candidate costs; mission dispatch; bounded look-ahead; corridor lifecycle; closure-triggered rerouting; recovery and no-route handling.
- **Dependencies:** Phase 2 simulator and safety path.
- **Deliverables:** mission API/events and routing/corridor tests.
- **Completion criteria:** ambulance reaches the destination, route versions are monotonic, obsolete priority is cancelled, and closure rerouting is observable.

## Phase 4 - Dashboard and live workflow

- **Objectives:** make the prototype demonstrable from one responsive operator interface.
- **Tasks:** implement React dashboard; network visualization; controller/scenario controls; dispatch and closure actions; traffic/signal/corridor status; event timeline; metrics and source labels.
- **Dependencies:** Phases 1-3 APIs.
- **Deliverables:** functional dashboard and production frontend build.
- **Completion criteria:** core workflow is operable without direct API calls and all simulated/mock states are labelled.

## Phase 5 - Perception contract and experiment comparison

- **Objectives:** represent the proposal's second evidence path without fabricating CV results.
- **Tasks:** implement mock perception playback; expose freshness/confidence/units; run matched controller comparisons; export manifests and metrics.
- **Dependencies:** Phases 2 and 4.
- **Deliverables:** perception panel, comparison results, downloadable JSON export.
- **Completion criteria:** mock data cannot be confused with simulator truth, comparisons disclose configurations, and exports are schema-versioned.

## Phase 6 - Validation and handoff

- **Objectives:** verify alignment, resilience, and continuation readiness.
- **Tasks:** backend tests; frontend build/type checks; end-to-end API smoke test; documentation audit; update context and checklist.
- **Dependencies:** all implementation phases.
- **Deliverables:** tested prototype, README, final context, known limitations, and remaining SUMO/CV/DQN integration work.
- **Completion criteria:** all automated checks pass, no proposal/report file changed, and another developer can run and extend the system from the documentation.
