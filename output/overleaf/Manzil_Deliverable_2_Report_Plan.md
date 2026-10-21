# Manzil: Deliverable 2 Report Implementation Plan

Status: Planning only. Report drafting, figure creation, and report compilation require the user's explicit "proceed" instruction.

Prepared: 5 October 2026. Due date shown in the supplied notice: Wednesday, 7 October 2026; submission time not specified.

## 1. Basis and governing decisions

The report will cover Chapters 1 through 6 for an R&D project, with the required preliminary pages and bibliography. It will explain the proposed research and system design, not present unperformed experiments as completed work.

Use the following source priority:

1. The supplied Deliverable 2 notice controls the chapters due.
2. `F26-104.pdf`, the final proposal, controls the approved project identity and scope.
3. `Manzil_FYP_Context.md` supplies supplementary context where it does not conflict with the final proposal.
4. `FYPFast/main.tex` and `FastFyp.cls` control report structure, required sections, and institutional presentation.
5. The sample reports inform depth, organization, tables, and diagrams; their older conventions do not override the current template.

The template calls SRS optional for research projects, but the deadline notice requires Chapters 1-6. Therefore, retain Chapter 4, Software Requirement Specifications, and Chapter 5, Proposed Approach and Methodology. Do not copy the chapter numbering of research-only samples that move methodology to Chapter 4.

Do not add the template's later Implementation/Test Cases, User Manual, Experimental Results, or final Conclusions chapters to this submission unless the supervisor provides a different D2 requirement. Each included chapter will still have its own closing summary.

## 2. Material reviewed and how it will influence the report

All 12 sample PDFs were screened. Seven research-oriented or combined research-and-development reports were read in full, including their later chapters to understand how methodology connects to evaluation. Representative visual pages were also inspected.

Classification is based on report content and structure, not an official project-type register. JobLens explicitly describes itself as research-based; ImageSense explicitly describes itself as development-based.

| Sample | Useful pattern to adapt for Manzil |
| --- | --- |
| ParkEase: Smart Parking System | Closest domain analogue: camera perception, routing, dashboard, module-level methodology, layered architecture, ER model, and sequence diagrams. Its Chapters 5-6, printed pp. 36-49, are particularly useful. Do not import its ANPR/crime-detection features. |
| JobLens: NLP Enabled Deep Learning Approach for Accurate Resume Ranking | Extensive scholarly review, separate dataset discussion, annotation/preprocessing detail, baseline comparison, and module-specific metrics. Adapt its research depth, not its chapter numbering. |
| Detection & Identification of Novel Attacks in Phishing using AI Algorithms | Clear distinction between reference model and proposed approach; procedural model explanation and comparative experimentation. Useful for explaining Manzil's baselines and contribution. |
| GeoSync | Thematic literature organization, map/data provenance, subsystem decomposition, sequence diagrams, and explicit failure/fallback behavior. Useful for network modeling and routing-service interfaces. |
| SynapSure: Mapping Brain Health | Combined methodology, requirements, interface, database, and design coverage. Useful as a coverage check, but Manzil needs a more precise experimental method and genuine UML class diagram. |
| FictionGenie | Detailed literature critiques, interface mockups, and use-case-linked sequences. Keep relevant interaction design; avoid unnecessary account-management pages and generic boilerplate. |
| Recruit Ease | Layered architecture expanded into backend/data-service views, detailed use-case flows, data dictionary, and iterative experiment discussion. Useful for tracing requirements into design. |

The other samples use development-oriented structures: Bidding Bazaar, Build Hub, EduVerse, RahZil, and ImageSense. They will not determine Manzil's R&D chapter structure.

Important improvements over some samples:

- Meet the current template's minimum of 15 relevant research studies, even where an older sample reviews fewer.
- Follow the current use-case table instructions: captions and one generic Use Cases section, without a separate subsection for every table.
- Maintain consistent scope, dataset descriptions, component names, and proposed/completed status throughout.
- Do not copy unsupported superiority claims, unrealistic availability promises, stale chapter outlines, or mismatched references.
- Use readable multi-page tables with repeated headers and proper UML notation. A processing flowchart is not a class diagram.
- Use original prose and original project diagrams; samples are structural references, not text to reproduce.

## 3. Project framing to preserve

Manzil is a simulation-based R&D prototype for intelligent traffic control and emergency routing, supported by a traffic-video perception component and a monitoring dashboard.

The report must distinguish two data paths:

- Video perception: recorded traffic footage, vehicle detection and tracking, and observable counts/density/queue indicators.
- Controlled experimentation: SUMO/TraCI network state used for signal-control and ambulance-routing experiments.

These can share a defined traffic-state interface, but the report must not claim that arbitrary camera footage directly reconstructs the selected road network. Camera-to-lane mapping and calibrated measurements require explicit assumptions.

Preserve the proposed progression from fixed-time control to rule-based adaptive control and then RL-based control. Cover congestion-aware routing, dynamic rerouting, a moving green corridor, safe signal transitions, and restoration of normal operation after passage. Ambulance behavior in experiments must not bypass signals in a way that makes corridor control irrelevant.

The contribution should be framed as the design and evaluation of an integrated approach, with specific questions about its effectiveness and tradeoffs. Do not claim that using YOLO, RL, or A* alone constitutes a new algorithm, or that the combined approach is unprecedented without literature evidence.

Keep forecasting, live government CCTV integration, real-world signal actuation, citywide deployment, number-plate recognition, enforcement, visual accident classification, and a mobile app outside the core scope. Treat a single active ambulance as the core experimental case unless the team confirms otherwise.

Use React and FastAPI as specified in the final proposal. PostgreSQL, the tracking implementation, RL algorithm, precise map size, hardware budgets, and similar details must be marked as proposed choices until confirmed.

## 4. Planned report contents

### Preliminary pages

- Institutional cover with the exact approved title, group ID, names, roll numbers, supervisor, and fixed submission date.
- Anti-plagiarism and author declarations following the template; leave signatures for the actual authors.
- One-paragraph abstract: 50-125 words, approximately 3-5 sentences. For this stage, describe the problem, proposed approach, and evaluation intent without fabricated findings.
- Executive summary: 1-2 pages covering motivation, scope, research approach, expected contribution, limitations, and current stage.
- Automatically generated table of contents, list of figures, and list of tables.

### Chapter 1: Introduction

Plan approximately 2-3 pages.

1. Introduce urban congestion and emergency-response delay without unsupported local statistics.
2. Explain the report's purpose and intended audience.
3. Define relevant terms and acronyms, including CV, RL, SUMO, TraCI, queue length, signal preemption, and green corridor.
4. End with a concise project summary and an accurate outline of the six submitted chapters.

### Chapter 2: Project Vision

Plan approximately 4-5 pages.

1. Problem-domain overview, concise problem statement, and problem elaboration.
2. Research questions and measurable objectives linking perception, normal traffic control, emergency routing, and corridor operation.
3. Explicit in-scope/out-of-scope table; distinguish prototype users from potential real-world beneficiaries.
4. SDG alignment, principally sustainable cities and communities, with relevant health implications discussed cautiously and sourced during drafting.
5. Constraints: data availability, camera viewpoint/occlusion, simulation realism, computational resources, and semester timeframe.
6. Brief practical value/business-opportunity section without invented partnerships or revenue claims.
7. Stakeholder table: research team/operator, supervisor/evaluators, and prospective traffic/emergency-service stakeholders.

### Chapter 3: Literature Review / Related Work

Plan approximately 12-16 pages; substance takes priority over the estimate.

Build a verified set of at least 15 relevant research studies, with a working target of 18-20 if appropriate evidence is available. The proposal bibliography is a starting point, not a substitute for reading and verifying the sources.

Organize the review thematically:

1. Vision-based vehicle detection, tracking, and traffic-state estimation.
2. Fixed-time and non-learning adaptive traffic-signal control.
3. RL-based signal control, including multi-intersection coordination.
4. Congestion-aware emergency routing and dynamic rerouting.
5. Emergency signal priority/preemption, corridor coordination, and simulation-based evaluation.

For each reviewed study, provide the template's summary, critical analysis, and relevance to Manzil. Record the method, data/environment, measured results with their context, limitations, and implications for a specific design decision. Keep official software documentation and existing applications separate from the research-study count.

Include research comparison tables with the required Author, Method, Results, and Limitations fields; add year, evaluation setting, and relevance where readable. Do not compare reported numerical scores across incompatible datasets as if they were a common benchmark.

Conclude with a synthesis: what the literature establishes, what remains uncertain, and exactly what Manzil proposes to investigate. Avoid an unsupported blanket claim that no integrated solutions exist.

### Chapter 4: Software Requirement Specifications

Plan approximately 10-14 pages.

1. Feature list and numbered functional requirements grouped by perception, simulation, control, routing/corridor, dashboard, and experiment logging.
2. Quality attributes and measurable non-functional requirements. Label untested latency/throughput thresholds as design targets, not achieved performance.
3. Assumptions and hardware/software requirements, separating development/training needs from demonstration needs.
4. Use-case diagram and approximately 8-10 substantive use-case tables: configure a scenario; run/control a simulation; process video; inspect traffic state; select a controller; dispatch an ambulance with origin/destination; monitor its route/corridor; handle a changed/blocked route; compare runs; export records. Consolidate overlapping cases where sensible.
5. Include invalid inputs, no route, stale observations, simulation disconnect, and failed processing in alternative flows. Do not invent login/registration modules merely because samples contain them.
6. Approximately 4-5 clearly labeled proposed GUI wireframes: traffic overview, perception/intersection detail, emergency dispatch and route view, experiment configuration, and comparative analytics.
7. ER diagram and data dictionary for justified persistent records, such as scenarios, runs/configurations, aggregated observations, controller decisions, emergency missions, route revisions, and metrics. Distinguish database records from live in-memory graph/simulation state and video files.
8. Risk register with likelihood, impact, mitigation, and fallback.
9. Traceability table linking requirements to use cases, design modules, and planned verification.

### Chapter 5: Proposed Approach and Methodology

Plan approximately 8-11 pages. This is the main R&D chapter and must not be reduced to a technology list or an Agile-process description.

1. Overall research workflow and the two input/data modes.
2. Network and data preparation: map provenance, network extraction/cleanup, lane/turn/signal assumptions, scenario demand generation, and video selection/annotation.
3. Perception pipeline: pretrained detector, tracking, region/lane assignment, count aggregation, observable queue/wait proxies, and confidence/occlusion limitations.
4. Baseline controllers: specify fixed timing and a reproducible rule-based adaptive policy.
5. Proposed RL formulation: state, actions, reward components, decision interval, training episodes, coordination model, and safety constraints. Select and justify a feasible algorithm after source review and team confirmation; avoid casually committing to several algorithms.
6. Graph routing: define nodes/edges, valid vehicle movements, dynamic edge costs, update frequency, and routing algorithm. Define cost units/normalization and avoid double-counting delay. Explain any A* heuristic's suitability for the chosen cost.
7. Rerouting: define triggers, benefit threshold/hysteresis, feasible remaining route from the current position, and treatment of closures/no-route cases.
8. Moving green corridor: define activation/look-ahead, clearance before conflicting phases, passage detection, priority arbitration, bounded disruption, and restoration. These are simulation policies, not certified real-world traffic-controller specifications.
9. Procedural pseudocode for the control loop, routing/rerouting, and corridor lifecycle; no application source-code listings.
10. Experimental protocol, metrics, reproducibility, and threats to validity as described below.

### Chapter 6: High-Level and Low-Level Design

Plan approximately 9-12 pages.

1. System overview, assumptions/dependencies, constraints, design goals, and development approach.
2. Mandatory high-level architecture, separating React dashboard, FastAPI services, perception worker, SUMO/TraCI adapter, controller, routing/corridor coordination, and persistence.
3. Component responsibilities, inputs/outputs, shared traffic-state representation, and rationale for decomposition.
4. Architectural decisions with meaningful alternatives and tradeoffs, not generic claims that every tool is the best.
5. Domain/class diagram using appropriate UML relationships; ER diagram remains in Chapter 4 and is referenced rather than duplicated.
6. Sequence diagrams for a normal control update, ambulance dispatch/corridor activation, and rerouting/restoration.
7. Corridor state-transition diagram covering idle, requested, safe transition, active priority, passage, recovery, and cancellation/failure.
8. Interface/data-contract table covering timestamps, units, identifiers, source mode, validity/freshness, and event ordering.
9. Concurrency and ownership: one controlled owner of simulation stepping and signal actuation; background perception must not block the API; dashboard updates must not compete with control decisions.
10. Error handling, fallback controller, logging, reproducibility configuration, test strategy, coding policies, and maintainability.

Working length estimate: roughly 55-75 pages including front matter and references. This is not an institutional requirement or a quota; revise after confirming any page limit and compiling the first draft.

## 5. Planned experimental framework

These are protocols to document in D2, not claims that experiments have already been performed.

| Research question | Planned comparison | Main evidence |
| --- | --- | --- |
| How reliably can the perception module estimate observable traffic conditions? | Detector/tracker output against annotated held-out video segments | Detection precision/recall or mAP where suitable; count MAE; tracking/queue measures only where ground truth exists; processing throughput |
| Does the proposed signal controller improve normal traffic operation? | Fixed-time vs rule-adaptive vs selected RL controller under matched scenarios | Mean waiting/travel time, queue length, throughput, and per-approach fairness/starvation checks |
| What does dynamic routing contribute to emergency travel? | A clearly defined static/reference route vs congestion-aware routing, holding the signal policy fixed | Ambulance travel time, stops, delay, route revisions, and route-computation time |
| What additional benefit and disruption come from the moving corridor? | Emergency routing without corridor vs the same routing with corridor | Ambulance travel time/stops; normal-traffic delay/queues; recovery time and safe-transition checks |

Define light, medium, and heavy demand; relevant closure/congestion scenarios; origin/destination selection; run duration and warm-up; and model/version/configuration recording. Use repeated matched random seeds, and report averages plus variability rather than selecting only favorable runs. Fix the comparison protocol before observing test outcomes.

Separate training/tuning from final evaluation. Split video data by source/sequence where necessary to avoid near-identical frames leaking across sets. Hold out appropriate demand/scenario combinations for RL evaluation. Record limitations of synthetic demand, map fidelity, perception errors, and transfer from simulation to a real city.

A shared interface alone does not demonstrate perception-to-control robustness. Include a controlled noise/ablation study only if feasible and explicitly agreed; otherwise acknowledge that the two components are evaluated separately.

## 6. Original figures and tables to prepare after approval

Prioritize figures that explain behavior rather than decorate pages:

- Project context/scope and use-case diagram.
- ER diagram and readable data dictionary.
- Proposed GUI wireframes with navigation explanations.
- Two-mode methodology/data-flow diagram and perception pipeline.
- Controller/routing/corridor pseudocode, with a flowchart only where it adds clarity.
- High-level architecture and one detailed coordination view if needed.
- UML domain/class diagram.
- Three important interaction sequences and corridor lifecycle/state diagram.
- Literature comparison, requirements traceability, design decisions, risks, and experimental matrix tables.

Use editable vector sources or LaTeX-native diagrams where practical. Keep terminology, colors, arrows, actors, and identifiers consistent across chapters. Label all unimplemented interfaces as proposed wireframes; do not manufacture application screenshots or result plots.

## 7. Execution sequence after "proceed"

### Phase A: Confirm facts and create a report requirements checklist

Confirm the team's actual implementation progress, final report metadata, selected network/data, available hardware, and any supervisor-specific instructions. Record unresolved choices transparently. Map every proposal commitment and template requirement to its report location.

### Phase B: Prepare an isolated LaTeX report workspace

Preserve the supplied `FYPFast` folder unchanged. Create a separate `Manzil_D2_Report/` working directory using its class, logos, and layout. Split chapters into editable `.tex` files, maintain a dedicated bibliography and figure-source folder, and compile a minimal six-chapter skeleton first.

Keep the template's A4 presentation, margins, typography, preliminary/body page numbering, headings, captions, and automatic references. Replace all example content, placeholder references, incorrect figure labels, and dynamic dates. Do not fill in signatures.

### Phase C: Verify literature and settle research/design choices

Read primary research sources and official technical documentation; validate author/title/year/DOI details and any quoted numerical findings. Build the literature evidence table before writing its synthesis. Use this evidence to justify the chosen controller, routing, perception, and evaluation designs. No literature research or model claims should rest solely on another student's report.

### Phase D: Draft in dependency order

Draft Project Vision, Literature Review, and Methodology first. Then finalize SRS and Design against those decisions. Write Introduction and the preliminary summaries last so they accurately describe the resulting six chapters. Maintain a decision log and distinguish approved facts, proposed choices, confirmed implementation, and measured evidence.

### Phase E: Add original visual material and traceability

Create diagrams/wireframes from the same component definitions used in the text. Check requirement-to-use-case-to-module-to-verification coverage. Ensure Chapter 4 describes what the system must do, Chapter 5 how the research will investigate it, and Chapter 6 how components will realize the design.

### Phase F: Content, citation, and visual quality checks

- Verify six-chapter scope and every mandatory template section.
- Verify at least 15 genuinely relevant research studies and complete citations.
- Check every numerical claim, equation, variable, unit, dataset statement, and claimed contribution.
- Eliminate contradictions between normal control and emergency overrides, or between video and simulation modes.
- Check that planned targets are not described as measurements and no unverified implementation/results are asserted.
- Check names, roll numbers, title, supervisor, dates, acronym definitions, cross-references, and chapter outlines.
- Compile LaTeX/BibTeX to resolve all references; remove undefined citations, missing assets, and layout overflows.
- Render and visually inspect the final PDF, including all tables, figures, page breaks, headers, and page numbers. Fix clipping, crowded diagrams, tiny labels, and broken table continuations.
- Leave no template instructions, dummy values, invented signatures, or unresolved placeholders in the submission version.

### Phase G: Handoff

Deliver the compiled D2 PDF, editable LaTeX project, bibliography, editable figure sources, and a self-contained Overleaf-ready archive. Place the final PDF under `output/pdf/`; keep temporary build/render files separate. Include a short checklist of any factual items the team still needs to verify before submission.

## 8. Deadline-oriented schedule

Subject to when approval is given:

- 5 October: confirm scope/status, prepare the six-chapter structure, verify the literature shortlist, and settle the methodological outline.
- 6 October: draft the chapters, create the essential figures/tables, and compile a complete first PDF for team review.
- 7 October: incorporate corrections, run consistency/citation checks, inspect the rendered PDF, and package the submission with a buffer before the actual deadline.

If approval arrives later, prioritize complete mandatory coverage, a defensible methodology, verified references, and readable diagrams over extra pages or decorative mockups. This schedule covers preparing the report, not implementing the entire Manzil system or running a full research study before D2.

## 9. Information needed when drafting starts

These do not block the plan, but must not be silently invented in the report:

1. What has actually been implemented or experimentally tested so far?
2. Has the supervisor fixed an RL algorithm, tracking method, network area/size, or dataset?
3. What development/training hardware is available?
4. Are there additional rubrics, page limits, declaration/date requirements, or an exact submission time?
5. Are any claims or design decisions in the final proposal superseded by explicit supervisor feedback?

Until confirmed, describe these as proposed choices or open decisions in working notes. Resolve material choices before issuing the final submission PDF.

## 10. Approval boundary

This file is the implementation plan only. Reading and review are complete. No Manzil report chapters, final diagrams, results, or project implementation have been created as part of this planning task. Execution begins only after the user says "proceed".
