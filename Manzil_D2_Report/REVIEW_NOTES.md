# Manzil Deliverable 2 Review Notes

## Governing scope

- Deliverable plan applied as the primary chapter/content authority.
- Approved proposal applied for project identity, scope, and current status.
- FAST `FastFyp.cls` and its logos retained as the formatting foundation.
- Chapters 1--6 only, plus front matter, bibliography, and coverage/open-item appendices.
- No experimental values, implementation completion, deployment, or application screenshots were fabricated.

## Sample-report comparison

- ParkEase informed SRS depth, data design, architecture, sequences, and risk coverage.
- JobLens informed thematic research depth, study summary, data-splitting discussion, and evaluation discipline.
- GeoSync informed network provenance, routing interfaces, fallback behavior, and map constraints.
- The final organization follows the current Deliverable 2 plan where older sample chapter numbering differs.

## Requirements coverage

| Requirement | Evidence in report |
| --- | --- |
| Front matter and FAST presentation | `main.tex` |
| Introduction and project vision | Chapters 1--2 |
| At least 15 research studies | Chapter 3 reviews 18 peer-reviewed studies; 23 sources are cited overall |
| Requirements/features/quality attributes | Chapter 4, FR-01--FR-20 and NFR-01--NFR-12 |
| Use cases | Eight full use-case tables and an original diagram |
| Proposed GUI | Five wireframes explicitly labelled proposed/schematic |
| Database design | ER model and data dictionary |
| Risks and traceability | Risk register and requirements traceability matrix |
| Methodology | Two input modes, perception, baselines, RL, routing, corridor, protocols, metrics, validity |
| High-/low-level design | Architecture, domain model, three sequences, state model, contracts, concurrency, fallbacks |
| Reproducibility | Immutable run manifest, seeds, versions, checksums, held-out evaluation protocol |

## Validation completed

- Successful `pdflatex -> bibtex -> pdflatex -> pdflatex` build.
- Final output: 72 A4 pages.
- All 23 cited bibliography entries resolve; no missing-citation markers or undefined references remain.
- Significant figure/table overflow corrected; remaining overfull boxes are below 2 pt and visually immaterial.
- Representative title, prose, long-table, methodology figure, design table, and bibliography pages rendered and inspected.
- PDF text checked for unresolved `TODO`, `undefined`, and `[?]` markers.

## Unresolved facts requiring team confirmation

1. Exact selected Lahore network, bounding box, signal count, and OpenStreetMap snapshot.
2. Final video sources, permissions, annotation volume, detector checkpoint, and tracker.
3. Final RL algorithm, action structure, training budget, and hyperparameters.
4. Final persistence engine, demonstration hardware, and measured latency/freshness thresholds.
5. Actual UI screenshots after implementation.
6. Whether a faculty-specific certificate/approval sheet is required in addition to the supplied template.
7. Confirmation that `F26-104` is the official group/project identifier; it is inferred from the approved proposal filename.

