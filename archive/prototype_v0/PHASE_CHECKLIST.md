# Manzil Prototype Phase Checklist

Tasks are checked only after implementation and verification.

## Phase 0 - Analysis and scope lock

- [x] Review proposal, Deliverable-2 report, and project context.
- [x] Inventory repository and available toolchain.
- [x] Document feasibility concerns and justified alternatives.
- [x] Create phased plan and initial continuation context.

## Phase 1 - Foundation and contracts

- [x] Create backend and frontend workspaces.
- [x] Define versioned domain/API contracts.
- [x] Implement health and configuration endpoints.
- [x] Verify backend tests and frontend build.

## Phase 2 - Simulation and controllers

- [x] Implement deterministic traffic simulator.
- [x] Implement fixed-time controller.
- [x] Implement pressure-inspired adaptive controller.
- [x] Implement labelled tabular-Q prototype controller.
- [x] Enforce shared safety constraints and collect metrics.
- [x] Verify reproducibility and signal invariants.

## Phase 3 - Emergency workflow

- [x] Implement time-based Dijkstra routing and route versions.
- [x] Implement ambulance dispatch and movement.
- [x] Implement bounded moving-corridor lifecycle.
- [x] Implement closure-triggered rerouting and no-route handling.
- [x] Verify passage, cancellation, recovery, and destination arrival.

## Phase 4 - Dashboard

- [x] Implement responsive React operator dashboard.
- [x] Add network, traffic, signal, route, and corridor views.
- [x] Add simulation, controller, ambulance, and incident controls.
- [x] Add event timeline, metrics, warnings, and source labels.
- [x] Verify production build and local HTTP delivery.
- [ ] Complete in-app visual browser QA (browser unavailable in current session).

## Phase 5 - Perception and comparisons

- [x] Implement labelled mock-perception stream and freshness state.
- [x] Implement matched controller comparison workflow.
- [x] Implement schema-versioned JSON export.
- [x] Verify source separation and comparison disclosure.

## Phase 6 - Final validation

- [x] Run backend unit/integration tests.
- [x] Run frontend type/build checks.
- [x] Run end-to-end API smoke test.
- [x] Audit proposal preservation and deviations.
- [x] Finalize README and `context.md`.
