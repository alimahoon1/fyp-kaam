# Prototype Deviations and Justifications

This document records implementation substitutions only. It does not revise the proposal or report.

| Proposal element | Prototype implementation | Justification | Upgrade path |
| --- | --- | --- | --- |
| SUMO/TraCI runtime | Deterministic Python fallback simulator labelled `prototype-sim` | SUMO is absent and no validated network exists. The fallback makes the workflow executable without inventing SUMO evidence. | Implement `SumoAdapter` with the same snapshot/action contracts. |
| Lahore/OSM network | Six-intersection synthetic graph with two principal routes and cross-links | The exact area, bounding box, signal programs, and cleanup are unconfirmed. | Import, validate, and version a selected OSM extract. |
| YOLO + tracker | Mock observation stream labelled `mock-perception`, with confidence, validity, and uncalibrated proxies | No licensed clip, annotations, model checkpoint, or tracker configuration was supplied. | Add a bounded worker that emits the existing perception contract. |
| DQN policy | Frozen tabular-Q-style prototype policy | It demonstrates controller selection and the safety boundary without claiming unperformed training. | Train/evaluate the proposed parameter-sharing DQN on SUMO scenarios. |
| PostgreSQL | In-memory runtime plus downloadable JSON evidence package | No database service is configured; a database is unnecessary for a single-session prototype. | Implement a repository adapter with migrations and immutable manifests. |
| Repeated academic evaluation | One-click matched-seed fallback-simulator comparison | Valid academic conclusions require SUMO, frozen demand, repetitions, and trained checkpoints. | Run the report's 900-second warm-up, 3,600-second measurement, ten-seed protocol. |

All substitutions preserve the proposal's functional boundaries: one simulation owner, requested versus applied control, explicit source mode, safe transitions, dynamic route versions, bounded corridor priority, visible failure, and reproducible configuration.
