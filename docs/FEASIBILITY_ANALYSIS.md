# Manzil Prototype Feasibility Analysis

## Source of truth

The immutable proposal and Deliverable-2 report define the prototype scope. The prototype must demonstrate traffic observation, comparable signal controllers, dynamic emergency routing, a moving green corridor, dashboard monitoring, and reproducible experiment records. Existing proposal/report files are not modified.

## Proposed, feasible now, and prototype alternative

| Area | Proposal | Feasible in this repository now | Prototype decision |
| --- | --- | --- | --- |
| Traffic simulation | SUMO controlled through TraCI | SUMO is not installed and no network files exist | Use a deterministic in-process traffic simulator behind a `SimulationAdapter`; preserve a future `SumoAdapter` boundary. |
| Road network | Cleaned Lahore/OSM extract with 10-20 signalized intersections | No selected bounding box or validated network exists | Use a documented six-intersection synthetic corridor with alternate routes. Never label it as Lahore. |
| Computer vision | YOLO plus multi-object tracking on licensed traffic video | No video, annotations, checkpoint, or model dependency exists | Provide a perception contract and labelled mock-observation stream. A real worker can replace it later. |
| Adaptive control | Fixed, rule-adaptive, and RL comparison | Fixed and pressure-inspired control are practical; no RL training artifacts exist | Implement fixed and pressure-inspired controllers plus a clearly labelled tabular-Q prototype policy. Do not claim DQN results. |
| Emergency routing | Dynamic Dijkstra/A* with time-based costs | Feasible on the synthetic graph | Implement Dijkstra, cost snapshots, closures, hysteresis, route versions, and no-route handling. |
| Green corridor | Bounded moving priority with safe transitions and recovery | Feasible in the lightweight simulator | Implement requested, transition, active, passage, recovery, and cancelled states with one active mission. |
| Backend/dashboard | FastAPI, React, live state and analytics | Feasible with local Node/Python tooling | Implement FastAPI REST/WebSocket services and a React dashboard. |
| Persistence | Structured experiment records, proposed PostgreSQL | PostgreSQL is not configured | Use JSON run manifests/exports and an in-memory run store behind repository semantics. |
| Evaluation | Repeated, matched SUMO experiments with held-out scenarios | Full academic evaluation requires validated SUMO demand and trained models | Provide deterministic controller comparison runs and exportable evidence, clearly marked prototype-only. |

## Main risks and controls

1. **Simulation fidelity:** the fallback simulator cannot support field or SUMO performance claims. The UI and exports identify `prototype-sim` as the source.
2. **RL misrepresentation:** the tabular-Q policy demonstrates the controller interface only. It is never called a trained DQN.
3. **Perception realism:** mock observations prove the data path and dashboard behavior, not detector accuracy.
4. **Unsafe signal transitions:** all normal and emergency requests pass through one safety filter with minimum-green and clearance states.
5. **Route oscillation:** revisions require infeasibility or a persistent improvement above a threshold and use route versioning.
6. **Hidden failures:** stale data, closed roads, no-route states, fallbacks, and simulation termination remain visible.
7. **Non-reproducible comparisons:** every run records seed, scenario, controller, source mode, duration, and terminal reason.

## Acceptance boundary

This prototype is successful when a reviewer can run it locally, switch controllers, observe traffic state, dispatch an ambulance, see a time-based route and moving corridor, introduce a road closure, observe a justified reroute, compare controller runs, and export a manifest. It is not evidence of real-road safety, clinical impact, YOLO accuracy, DQN superiority, or SUMO performance.
