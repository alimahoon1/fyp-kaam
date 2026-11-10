# MANZIL FYP — CHAT HANDOFF CONTEXT

Use this file as the starting context for a new ChatGPT conversation.  
The project has already been discussed in depth, and the decisions below should be treated as the current baseline unless the user explicitly changes them.

---

# 1. USER / FYP TEAM

## Project Name
**Manzil**

## Proposed Formal Title
**Manzil: An Intelligent Traffic Management and Emergency Routing System**

Alternative shorter title used on the proposal cover:
**Manzil: Intelligent Traffic & Emergency Routing**

## Project Advisor
**Miss Umm-e-Ammarah**

## Group Members
1. **Mohammad Ibrahim Salman** — 23L-0723  
2. **Muhammad Ali Mahoon** — 23L-0531  
3. **Muzammil Ahmed Bhatti** — 23L-0688  

## University
**National University of Computer and Emerging Sciences (FAST-NUCES), Lahore**  
Department of Computer Science

---

# 2. CORE FYP IDEA

Manzil is an **AI-powered intelligent traffic management system** designed to:

- Analyze traffic conditions using computer vision.
- Detect and classify vehicles.
- Estimate traffic density, queue length, and waiting time.
- Dynamically control traffic signals instead of relying only on fixed timers.
- Simulate a multi-intersection city traffic network.
- Detect/prioritize emergency vehicles such as ambulances.
- Find an **optimal emergency route from Point A to Point B** based on real-time traffic conditions.
- Dynamically reroute an ambulance if congestion or road incidents appear ahead.
- Create a **moving Green Corridor** by opening/updating traffic signals along the ambulance route.
- Compare traditional fixed-time traffic control against rule-based adaptive control and reinforcement-learning control.
- Present everything in a visual dashboard and SUMO simulation.

The concept should be treated as a serious **BSCS FYP / smart-city research prototype**, not simply "traffic detection with YOLO".

---

# 3. MOST IMPORTANT FYP SCENARIO

The centerpiece demo should be an ambulance travelling across a simulated city.

Example:

**Point A → Hospital B**

The ambulance should NOT simply follow the shortest route.

Instead, the system should evaluate multiple possible routes using:

- Expected travel time
- Current congestion
- Vehicle density
- Queue length
- Average road speed
- Estimated traffic-light delay
- Number/state of signals
- Simulated road blockage / incident / closure
- Road availability
- Potential effect of signal priority

Then Manzil should select the best route.

Example:

- Route 1: 4.8 km, severe congestion, ETA 10 min
- Route 2: 5.5 km, low congestion, ETA 6 min → **selected**
- Route 3: 5.0 km, simulated incident, ETA 12 min

The route planner should support **dynamic rerouting**.

If the ambulance is already travelling and congestion suddenly appears on its current path:

1. Detect the changed road cost.
2. Recompute the remaining path.
3. Update the ambulance route.
4. Update the Green Corridor to the new path.

This should be visibly demonstrated inside SUMO.

---

# 4. GREEN CORRIDOR DESIGN

The Green Corridor is not supposed to mean "turn every signal green at the same time."

Instead, it should move with the ambulance.

Example:

Ambulance route:

A → I3 → I7 → I11 → Hospital

When ambulance approaches I3:

- Safely finish conflicting phase.
- Clear the intersection.
- Give ambulance approach green.
- Ambulance passes.
- I3 returns to adaptive/normal traffic control.

Then the same occurs at I7, I11, etc.

This is a **moving emergency priority corridor**.

The ambulance itself should ideally still respect traffic signals.  
Do NOT rely only on SUMO's built-in behavior where an emergency vehicle ignores red lights, because then the examiner may ask what the project's own signal controller contributed.

---

# 5. TRAFFIC CONTROL APPROACH

The project should compare three levels of traffic control.

## Baseline 1 — Fixed-Time Signals
Example:

- North/South: 30 s
- East/West: 30 s

Used as the traditional baseline.

## Baseline 2 — Rule-Based Adaptive Controller

Use traffic conditions such as:

- Vehicle count
- Lane density
- Queue length
- Waiting time
- Vehicle type weighting
- Fairness / starvation prevention

Example priority formula:

Priority Score =
- 40% traffic density
- 30% waiting time
- 20% queue length
- 10% vehicle weight

Exact coefficients can be tuned later.

Signal green time could be bounded, e.g.:

- Minimum green: ~10 s
- Maximum green: ~60 s

Important:
A lane with constant high traffic must not permanently starve another lane.  
Waiting time / fairness must be part of the controller.

## Advanced Controller — Reinforcement Learning

RL is included as a **core research component**, but implementation should happen after the fixed and rule-based controllers work.

Possible RL state:

- Queue length in each direction
- Waiting time
- Vehicle count/density
- Current signal phase
- Possibly emergency priority state

Possible actions:

- Select next phase
- Extend current phase
- Switch between North-South and East-West
- Multi-intersection coordinated actions in later stage

Possible reward:

- Negative total waiting time
- Negative total queue length
- Negative congestion
- Possibly throughput reward
- Emergency-vehicle priority bonuses/penalties

The intended academic comparison:

**Fixed-Time vs Rule-Based Adaptive vs RL-Based Signal Control**

---

# 6. ROUTING ALGORITHM

The road network should be represented as a graph:

- Intersections = nodes
- Roads = edges

Routing should use:

- **A\*** and/or
- **Dijkstra**

However, road cost must be **dynamic**, not just physical distance.

Conceptual edge cost:

Road Cost =
Expected Travel Time
+ Congestion Penalty
+ Queue Penalty
+ Signal Delay
+ Incident / Closure Penalty

A slightly longer road may therefore become the optimal route.

A key research angle is:

## Joint Emergency Routing + Traffic Signal Optimization

The emergency route planner can consider that Manzil controls the signals.

So one route may look slow under normal traffic, but after signal priority it may become better than another route.

This makes the system more interesting than ordinary GPS shortest-path routing.

---

# 7. SIMULATION

## Main Simulator
**SUMO — Simulation of Urban MObility**

SUMO should be a central part of the FYP.

Why:

- Simulates individual vehicles.
- Simulates lanes, intersections, traffic lights and routes.
- Can run hundreds/thousands of vehicles.
- Supports traffic demand and congestion scenarios.
- Supports vehicle routing / rerouting.
- Can be controlled using Python.
- Has a GUI so the ambulance and traffic can be shown live during the FYP defense.

## SUMO Control
Use **TraCI** (Traffic Control Interface).

TraCI will allow Python code to:

- Read traffic state.
- Get vehicle information.
- Change signal phases.
- Change signal duration.
- Change/reroute a vehicle's route.
- Trigger emergency priority.
- Monitor ambulance progress.

## Road Network
Preferred proposal assumption:

Use a **selected real urban/Lahore road network**, imported from OpenStreetMap into SUMO.

Do NOT attempt to simulate all of Lahore.

Suggested manageable scope:

**approximately 10–20 signalized intersections**

If OpenStreetMap data for a specific intersection is incomplete, required lanes/signals can be cleaned manually using SUMO NetEdit.

A custom smart-city grid can be used as fallback, but the preferred presentation is a recognizable real urban map.

---

# 8. TRAFFIC SCENARIOS TO SIMULATE

Create repeatable simulation scenarios:

## Scenario A — Normal traffic
Balanced traffic across roads.

## Scenario B — Uneven traffic
One approach significantly busier than others.

## Scenario C — Rush hour / congestion
Hundreds of vehicles, queues across multiple intersections.

## Scenario D — Road obstruction / incident
A lane or road is partially/fully blocked.

This is enough to trigger congestion and emergency rerouting.

Do not make "visual accident detection" a mandatory core feature.

## Scenario E — Ambulance Emergency
Spawn an ambulance at Point A with destination B.

Measure:

- Route selected
- Number of signals crossed
- Number of stops
- Travel time
- Effect of Green Corridor
- Effect on normal traffic

## Scenario F — Dynamic rerouting
Generate new congestion while the ambulance is travelling and show the route changing in real time.

---

# 9. COMPUTER VISION MODULE

The simulator is not supposed to make the vision system pointless.

The project should have two related modes:

## Mode 1 — Real Traffic Perception
Input:

Recorded/live traffic video
→ YOLO
→ Tracking
→ Traffic metrics
→ Dashboard / traffic state

This proves the system can understand real traffic.

## Mode 2 — Smart-City Simulation
SUMO
→ traffic state
→ Manzil traffic controller
→ signal control / routing / analytics

This proves the management algorithms.

The conceptual real deployment would be:

CCTV
→ Computer Vision
→ Traffic State
→ Manzil
→ Real traffic controllers

For the FYP, real hardware/government signal control is replaced safely with SUMO.

---

# 10. COMPUTER VISION TECHNOLOGY

## Vehicle Detection
Use a **YOLO-based detector**.

Do NOT train YOLO completely from scratch.

Start with a pretrained model, then fine-tune if necessary.

Potential classes:

- Car
- Motorcycle
- Bus
- Truck
- Van
- Rickshaw
- Ambulance
- Pedestrian

## Tracking
Use **ByteTrack** or a similar tracker.

Tracking is important so the same car is not counted repeatedly on every video frame.

Tracking supports:

- Unique vehicle IDs
- Flow
- Waiting time
- Queue estimates
- Speed estimates
- Vehicle counting

Possible flow:

Camera frame
→ YOLO detections
→ ByteTrack
→ tracked IDs
→ lane assignment
→ counts / speed / queue / waiting time

---

# 11. DATASETS DISCUSSED / RECOMMENDED

No final dataset implementation has been completed yet.

Recommended public datasets:

## BDD100K
Useful for:
- General road-scene understanding
- Cars
- Vehicles
- Tracking/detection
- Diverse driving/weather conditions

Known characteristic:
- 100,000 driving videos

## UA-DETRAC
Especially useful because it is closer to **traffic-surveillance camera viewpoints**.

Useful for:
- Vehicle detection
- Vehicle tracking
- Traffic scenes
- Surveillance-style cameras

Known characteristic:
- 100 traffic video sequences
- More than 140,000 annotated frames

## AI City Challenge datasets
Useful as an additional source for:
- Intelligent transportation
- Vehicle/person detection
- Traffic-scene research

## Possible Local Supplement
If public data does not sufficiently represent:

- Pakistani rickshaws
- Local ambulance appearance
- Local traffic conditions

Then collect/annotate a **small supplementary local dataset** from legal/reusable sources or team-recorded footage.

Do not promise a huge custom dataset.

---

# 12. TRAFFIC METRICS

Traffic-state estimation may include:

- Vehicle count
- Vehicle type
- Traffic density
- Average speed
- Queue length
- Waiting time
- Road occupancy
- Congestion level

Example output:

Intersection I-04  
Northbound

- Vehicles: 42
- Avg speed: 4.8 km/h
- Queue: 76 m
- Avg wait: 61 s
- Congestion: Severe

---

# 13. VEHICLE-TYPE WEIGHTING

The system may distinguish road load based on vehicle type.

Example conceptual weights:

- Motorcycle = 0.5
- Car = 1.0
- Rickshaw = 1.0
- Van = 1.5
- Bus = 2.5
- Truck = 3.0

These are initial conceptual values, not final research constants.

This prevents "20 motorcycles" and "20 buses" from being treated as equivalent traffic loads.

---

# 14. EMERGENCY VEHICLE DETECTION

The system should support recognizing an ambulance.

Conceptual pipeline:

Frame
→ YOLO
→ ambulance detected
→ tracker assigns ID
→ lane/road identified
→ emergency mode triggered

Example dashboard event:

Emergency Vehicle: EV-008  
Type: Ambulance  
Road: Canal East  
Lane: 2  
Confidence: 96.7%

In the simulator, the emergency vehicle can also be explicitly spawned as an ambulance for controlled experiments.

---

# 15. DASHBOARD

A central web dashboard is part of the project.

Proposed stack:
- React or Next.js frontend
- FastAPI backend
- PostgreSQL database
- WebSockets for live updates if needed

Dashboard should show:

- City/intersection map
- Congestion heatmap
- Current traffic signal states
- Camera/video feed (or processed feed)
- Traffic metrics
- Ambulance location
- Ambulance destination
- Selected route
- Alternative routes / ETAs
- Green Corridor intersections
- Emergency alerts
- Dynamic reroute alert
- Performance analytics

Example:

Emergency Route Active

Vehicle: EV-01  
Destination: Hospital B  
ETA: 5m 42s  
Current route: I3 → I7 → I11 → Hospital  
Time saved: 3m 14s

Colors can show:

- Green = low congestion
- Yellow = moderate
- Orange = high
- Red = severe

During final defense:

**Left side:** Web dashboard  
**Right side:** SUMO live simulation

This allows the examiner to see both the system's decision and the actual simulated traffic response.

---

# 16. BACKEND ARCHITECTURE

Conceptual architecture:

React / Next.js Dashboard  
↑ WebSocket / REST  
FastAPI Backend  
├── Traffic AI Engine  
├── Emergency Routing Engine  
├── Signal Controller  
├── RL Controller  
├── PostgreSQL  
└── SUMO / TraCI Interface  

Computer Vision Pipeline  
↑  
Video / CCTV

The backend receives traffic measurements, chooses actions, controls SUMO, records events, and pushes live dashboard updates.

---

# 17. DATABASE — INITIAL SIMPLE DESIGN

Possible tables:

## intersections
- id
- name
- latitude
- longitude

## traffic_readings
- intersection_id
- timestamp
- vehicle_count
- queue_length
- average_speed
- waiting_time
- congestion_level

## signal_events
- intersection_id
- old_state
- new_state
- duration
- reason

## emergency_events
- vehicle_id
- detected_at
- route
- destination
- travel_time

This is an initial design and may evolve.

---

# 18. EVALUATION

The FYP must not be judged only visually.

The most important academic part is running **the same traffic scenario under different controllers**.

Compare:

1. Fixed-time signal controller
2. Rule-based adaptive controller
3. RL controller

Metrics:

- Average waiting time
- Average queue length
- Maximum queue length
- Vehicle throughput
- Congestion duration
- Total delay
- Network travel time

Emergency metrics:

- Ambulance travel time
- Number of red-light stops
- Number of intersections crossed
- Route changes
- Emergency ETA
- Time saved through routing
- Time saved through Green Corridor
- Delay imposed on non-emergency traffic

Example experiment format:

Fixed:
- Waiting: 82 s
- Avg queue: 21 vehicles
- Throughput: 820 veh/hr

Adaptive:
- Waiting: 57 s
- Avg queue: 14
- Throughput: 990 veh/hr

RL:
- Waiting: 46 s
- Avg queue: 11
- Throughput: 1080 veh/hr

These numbers are examples only.  
Do NOT use them as actual results before experiments are performed.

---

# 19. EMERGENCY EVALUATION

Run exactly the same ambulance route / traffic scenario under several modes:

## Mode 1 — Normal signals
Ambulance receives no special routing or signal priority.

## Mode 2 — Optimal route only
Dynamic route selection but normal signals.

## Mode 3 — Optimal route + Green Corridor
Dynamic route plus emergency signal priority.

Example output for final demo:

Without Manzil:
9m 22s

Routing only:
7m 08s

Routing + Green Corridor:
5m 41s

Again, these are sample presentation values only, not actual results.

---

# 20. PROPOSED TECH STACK

Current proposed stack:

## Computer Vision
- Python
- YOLO
- OpenCV
- ByteTrack
- PyTorch

## Simulation
- SUMO
- TraCI
- OpenStreetMap
- SUMO NetEdit when required

## Routing
- A*
- Dijkstra

## Reinforcement Learning
- Python
- Stable-Baselines3 and/or SUMO-RL-compatible environment
- PyTorch

## Backend
- FastAPI

## Frontend
- React or Next.js
- Map visualization using Leaflet / Mapbox if needed
- Charts using Recharts / Chart.js

## Database
- PostgreSQL

## Deployment / Development
- Docker

---

# 21. CURRENT SCOPE — INCLUDED

The formal proposal currently includes:

- AI/computer-vision traffic detection
- Vehicle detection/classification
- Multi-object tracking
- Vehicle density estimation
- Queue estimation
- Waiting-time estimation
- Adaptive traffic signals
- Fixed-time baseline
- Reinforcement-learning signal control
- Multi-intersection SUMO simulation
- Selected real urban/Lahore map
- Point A → Point B ambulance routing
- Dynamic route cost
- A*/Dijkstra routing
- Dynamic rerouting
- Green Corridor
- Dashboard/live map
- Historical/performance analytics
- Comparison of traffic-control strategies
- Evaluation of impact on ordinary traffic

---

# 22. CURRENT SCOPE — EXCLUDED / FUTURE

Do NOT make the current FYP unnecessarily huge.

The proposal explicitly keeps these out of the current scope or treats them as optional future extensions:

- Full Lahore deployment
- Connection to real government traffic signals
- Safety-certified emergency-response deployment
- Real roadside IoT / V2X infrastructure
- Number-plate recognition
- Automatic challans
- Facial recognition
- Policing/enforcement
- Full visual accident classification
- Weather-aware traffic control
- Traffic forecasting / prediction for the next 15–30 minutes
- Native mobile apps
- Multiple simultaneous ambulance missions as a core requirement

Important:
The user specifically said **traffic forecasting should NOT be part of the current project for now**.

Incidents / road closures needed for experiments can be simulated rather than detected visually.

---

# 23. IMPLEMENTATION ORDER

Recommended build sequence:

## Phase 1
Single SUMO intersection with fixed traffic lights.

## Phase 2
Rule-based adaptive traffic signal controller.

## Phase 3
Multiple intersections.

## Phase 4
Emergency vehicle spawn + fixed origin/destination.

## Phase 5
Dynamic A*/Dijkstra route planner.

## Phase 6
Green Corridor.

## Phase 7
Dynamic rerouting after simulated congestion/incident.

## Phase 8
Computer vision pipeline:
YOLO + ByteTrack + traffic metrics.

## Phase 9
Backend + dashboard integration.

## Phase 10
Evaluation:
Fixed vs adaptive.

## Phase 11
Reinforcement learning.

## Phase 12
Fixed vs adaptive vs RL experiments.

Optional enhancements should only be added after the core system works.

---

# 24. HOW TO PRESENT THE FYP

Recommended live defense flow:

1. Show a real traffic video.
2. Show YOLO + tracking detecting vehicles.
3. Show traffic metrics.
4. Open SUMO with multi-intersection network.
5. Run fixed-time control.
6. Create heavy congestion on one road.
7. Enable Manzil adaptive mode.
8. Show signal timing automatically change.
9. Click **Dispatch Ambulance**.
10. Select Point A and Hospital B.
11. Show 2–3 candidate routes and ETAs.
12. Show Manzil choose the optimal route.
13. Show the ambulance moving in SUMO.
14. Show signals opening ahead of the ambulance.
15. Trigger congestion/road closure on its current path.
16. Show Manzil recompute the route.
17. Show ambulance physically turn onto the new route.
18. Show Green Corridor shift to the new route.
19. Ambulance reaches hospital.
20. Show analytics:
    - travel time
    - stops
    - waiting-time improvement
    - queue improvement
    - throughput
    - impact on normal traffic

This is intended to be one of the strongest parts of the FYP.

---

# 25. RESEARCH / LITERATURE POSITIONING

Do NOT claim that emergency routing, adaptive traffic lights, or RL signal control are entirely new ideas.

The contribution should be framed as:

> A complete integrated academic prototype combining traffic perception, adaptive/RL signal control, dynamic emergency routing, moving green-corridor coordination, simulation, and dashboard-based monitoring in a realistic urban setting.

Relevant prior work / resources previously identified:

- SUMO
- SUMO TraCI
- SUMO OpenStreetMap import
- YOLO
- ByteTrack
- BDD100K
- UA-DETRAC
- Deep Q-Learning for traffic lights
- PressLight
- Emergency vehicle route optimization / signal pre-emption literature
- EMVLight
- SUMO-RL

The proposal created in the earlier chat contains 14 references.

---

# 26. FORMAL RESEARCH QUESTIONS

The proposal currently frames the project around questions similar to:

1. Can adaptive traffic control reduce average delay and queue length compared with fixed-time signals?
2. Can an RL controller improve network performance over a rule-based adaptive controller under changing traffic demand?
3. Can joint dynamic emergency routing and signal priority reduce ambulance travel time and stops without causing unacceptable delay to normal traffic?
4. Can a camera-based detection/tracking pipeline provide traffic-state measurements suitable for the traffic controller?

---

# 27. HONEST CURRENT PROJECT STATUS

Do NOT claim implementation has already been completed unless the user later says so.

As of the proposal-generation conversation:

Completed:
- Core idea finalized.
- Main feature set finalized.
- Technical architecture discussed.
- SUMO/TraCI selected.
- CV approach selected.
- Public datasets identified.
- Dynamic route cost factors defined.
- Green Corridor behavior defined.
- Evaluation approach defined.
- Technology stack shortlisted.
- Formal FYP proposal generated.

Not yet confirmed as completed:
- SUMO implementation
- Lahore network import
- YOLO fine-tuning
- ByteTrack integration
- Database/backend
- Dashboard
- RL training
- Final experiments
- Quantitative results

When writing future reports, say these are planned unless the user provides progress updates.

---

# 28. PROPOSAL ALREADY GENERATED

A full proposal document was created using the provided FAST FYP proposal template.

Filename:

**Manzil_FYP_Project_Proposal.docx**

It was approximately 9 pages and contained:

- Cover page
- Abstract
- 1. Introduction
- 2. Goals and Objectives
- 3. Scope of the Project
- 4. Initial Study and Work Done So Far
- References

The document used:
- Project: Manzil
- Advisor: Miss Umm-e-Ammarah
- Three team members listed above
- FAST-NUCES Lahore format

If the user uploads or provides this proposal in a new chat, treat it as the current formal proposal baseline.

---

# 29. ABSTRACT — CURRENT POSITIONING

The proposal abstract describes Manzil as an AI-driven traffic-management and emergency-routing system combining:

- computer vision
- adaptive traffic signals
- dynamic emergency routing
- reinforcement learning
- SUMO
- TraCI
- OpenStreetMap
- dashboard visualization
- public traffic datasets
- quantitative evaluation

The abstract emphasizes:

- route cost based on traffic conditions, not just distance
- rerouting when congestion/incidents change
- moving Green Corridor
- fixed vs adaptive vs RL comparison
- impact on ordinary traffic

---

# 30. CORE PROJECT STATEMENT

A concise one-sentence description that should be reusable:

> **Manzil is an intelligent urban traffic-management system that uses computer vision and adaptive/reinforcement-learning traffic control to optimize city traffic while dynamically selecting and clearing the fastest route for emergency vehicles through coordinated signal priority.**

Shorter:

> **Manzil intelligently manages traffic and creates the fastest dynamic route and Green Corridor for emergency vehicles.**

---

# 31. IMPORTANT DESIGN PRINCIPLES

When continuing the project, preserve these principles:

1. **Do not over-scope.**
2. **Simulation is valid and central to the research.**
3. **Computer vision proves perception; SUMO proves traffic-control behavior.**
4. **Routing and traffic signals should be connected, not separate demos.**
5. **The emergency route should be dynamic.**
6. **The Green Corridor should move with the ambulance.**
7. **Always compare against baselines.**
8. **Report effect on normal traffic, not only ambulance improvement.**
9. **Do not fabricate results.**
10. **Build simple controllers before RL.**
11. **Use a manageable real urban network rather than all of Lahore.**
12. **Keep the dashboard professional and demo-oriented.**

---

# 32. GOOD NEXT STEPS FOR A NEW CHAT

If this context is pasted into a new conversation, good next tasks include:

### Architecture
"Make the complete implementation-level architecture for Manzil."

### FYP Timeline
"Split Manzil into FYP-1 and FYP-2 milestones week by week."

### SUMO Prototype
"Start implementing Manzil. Give me the exact files and code for a 4-way SUMO intersection."

### Lahore Map
"Show me how to import a selected Lahore road network into SUMO."

### Ambulance Demo
"Implement Point A → Point B ambulance routing and Green Corridor in SUMO."

### Computer Vision
"Design the YOLO + ByteTrack traffic-detection pipeline."

### RL
"Design the RL state, action space and reward function for Manzil."

### Dashboard
"Design the Manzil dashboard screens and backend APIs."

### Dataset
"Finalize which datasets to use and exactly what each dataset is used for."

### Documentation
"Create the SRS / SDS / architecture document for Manzil."

### Proposal Revision
"Update the Manzil FYP proposal based on our latest implementation progress."

---

# 33. USER PREFERENCE FOR RESPONSES

The user generally prefers:

- Direct explanations
- Practical implementation detail
- Concrete examples
- Architecture diagrams in text where useful
- Small pieces of code with filenames for implementation tasks
- Clear distinction between what is real, simulated, planned, and already done
- FYP ideas that are complex enough to be academically defensible but still practical
- Avoiding unnecessarily theoretical or overly verbose answers unless requested

---

# 34. IMPORTANT NOTE TO THE NEXT CHATGPT INSTANCE

Do not restart the ideation from zero.

The project **Manzil** has already been selected and substantially scoped.

Unless the user explicitly asks to rethink the project, continue from the current baseline:

**Computer Vision + Adaptive Traffic Control + RL + SUMO + Dynamic Emergency Routing + Moving Green Corridor + Dashboard + Quantitative Evaluation.**

The next logical stage is implementation planning and execution.

---

# 35. DELIVERABLE 2 REPORT STATUS (6 OCTOBER 2026)

## Completed artifacts

- A complete Deliverable 2 LaTeX workspace has been created in `Manzil_D2_Report/` without modifying the original `FYPFast/` template or sample PDFs.
- The compiled handoff PDF is `Manzil_Deliverable_2_Report.pdf` at repository root; the build copy is `Manzil_D2_Report/build/main.pdf`.
- The report contains FAST front matter, Chapters 1--6, and the bibliography. Internal coverage and open-item appendices were removed from the submission document; unresolved work remains in this context file.
- After the October 10 corrective review and the subsequent SRS/design alignment, the compiled report is 81 portrait A4 pages, including the intentional blank title-page verso created by the FAST book layout.
- The LaTeX build completed with all citations and cross-references resolved.
- Source organization and reproduction instructions are documented in `Manzil_D2_Report/README.md`; detailed checks are in `Manzil_D2_Report/REVIEW_NOTES.md`.

## Report decisions now established

- The title follows the approved proposal: **Manzil: Intelligent Traffic & Emergency Routing**.
- `F26-104` is inferred from the approved proposal filename but is not printed on the report title page because it remains unconfirmed.
- The report preserves the two evidence paths: recorded-video perception and SUMO-controlled experiments.
- The report describes implementation and results only as proposed work because no source code, trained models, experiment logs, or measured results were present.
- The core emergency evaluation uses one active ambulance and separates the contributions of dynamic routing and corridor control.
- The selected design uses one owner of SUMO stepping and signal actuation. Controllers return requests that pass through a safety filter.
- Dynamic route costs are expressed in seconds and must avoid double-counting queue delay already present in measured link travel time.
- Dijkstra is the reference routing algorithm. A* is permitted only with an admissible free-flow travel-time lower bound.
- The moving corridor uses requested, safe-transition, active-priority, passage, recovery, and cancellation/failure states.
- PostgreSQL, ByteTrack, the exact network size, thresholds, and hardware remain proposed until implementation evidence confirms them. A parameter-sharing discrete-action Deep Q-Network is now the initial RL experiment design, subject to the stated baseline and held-out evaluation rules.

## Literature and sample-report basis

- Principal sample references: ParkEase for SRS/architecture, JobLens for research depth, and GeoSync for map/routing/fallback presentation.
- Chapter 3 critically reviews 18 peer-reviewed studies across detection, tracking, datasets, adaptive/RL signal control, simulation, graph routing, and emergency preemption.
- The complete report cites 23 verified research or official sources. Citation metadata was checked against DOI/publisher/proceedings or official documentation records.

## Visual and specification coverage

- Original figures include project context, use cases, five proposed GUI wireframes, ER model, research workflow, perception pipeline, high-level architecture, domain/class model, three sequences, and corridor state transitions.
- Current UI figures are wireframes, not screenshots. Replace them only after real interfaces exist.
- Requirements include FR-01--FR-20, NFR-01--NFR-12, eight substantive use cases, a data dictionary, and a risk register. The standalone requirements-traceability section was removed at the supervisor's direction.
- Methodology includes fixed/rule/RL controller definitions, routing and corridor pseudocode, experimental matrix, metric definitions, reproducibility controls, and validity threats.

## Unresolved items

1. Confirm that `F26-104` is the official project/group identifier.
2. Confirm the exact Lahore network, bounding box, map snapshot, and signalized-intersection count.
3. Confirm video sources, permissions, annotation plan, detector checkpoint, and tracker configuration.
4. Confirm the proposed parameter-sharing discrete-action Deep Q-Network after baseline profiling, and record its architecture, training budget, and hyperparameters.
5. Confirm the database engine, development/demonstration hardware, and measurable control/freshness targets.
6. Insert real UI screenshots only after implementation; do not fabricate them.
7. Confirm whether a separate faculty certificate/approval page is required beyond the supplied FAST template.

---

# 36. DELIVERABLE 2 STRICT FINAL-REVIEW RULES AND STATUS (8 OCTOBER 2026)

## Permanent report-writing rules

- Use portrait A4 throughout. Wide material must be wrapped, simplified, or divided; do not rotate a report page.
- Normal explanatory paragraphs should develop one coherent idea in approximately 150--200 words. Retain shorter text only for genuine structural introductions to figures, tables, lists, equations, or algorithms, and do not pad prose.
- Number every normal chapter heading and subheading. Starred headings are limited to front matter handled by the FAST convention.
- Keep the Abstract within approximately half a page. The Executive Summary is required by the Deliverable 2 plan and must address nontechnical stakeholders rather than repeat the Abstract.
- Do not use manual bold, italics, or underline to emphasize ordinary body prose. Table headers, diagram labels, headings, and template-controlled formatting are exempt.
- Use bullets only where they clarify a real set of items, and write complete statements rather than label-colon notes.
- Use one caption per figure or table and no subcaptions. Preserve aspect ratio and avoid forcing both width and height.
- Reference and explain every figure and table in the surrounding text. Captions remain concise and do not replace discussion.
- Preserve the distinction among implemented, designed, planned, and evaluated work. Do not invent screenshots, measurements, results, datasets, thresholds, hardware, or administrative facts.

## Sample-report findings

- ParkEase, JobLens, and GeoSync are the principal visual and structural references.
- ParkEase and GeoSync provide the closest title-page convention: NU and FAST logos at the top, centred university name, central university crest, project title, student rows with roll numbers and BS(CS), supervisor, Final Year Project label, and fixed submission date.
- The reference reports use portrait A4 pages, numbered body headings, restrained captions, conventional margins, and dense but readable text. The Deliverable 2 plan overrides sample weaknesses or later-phase chapter structures.

## Corrections completed in the strict review

- Rebuilt the title page to match the FAST sample hierarchy and removed the extra Deliverable label, department line, and unconfirmed `F26-104` identifier.
- Forced the Table of Contents to begin on its own page, corrected List of Figures/List of Tables contents entries, and condensed the List of Tables to one portrait page.
- Removed the `pdflscape` dependency and landscape environment. The 18-study summary uses one continuing portrait longtable with author/year, setting, reported evidence, and project implications.
- Reworked body prose across all six chapters, including a paragraph-length audit and section-level rereading. Short retained passages are structural exceptions recorded in review notes.
- Removed body emphasis and label-colon feature bullets; confirmed that normal content headings are numbered and that no subcaption package or construct is present.
- Rechecked every generated diagram against the stated architecture, route-version ownership, safe signal transitions, and moving-corridor lifecycle. The architecture now shows the safety filter, sequence diagrams persist through the experiment service, the corridor distinguishes pre-ownership invalidation from guarded recovery, and the ER model separates video jobs from simulation runs.
- Added or strengthened body discussion for every figure and table, including wireframes, algorithms, equations, use cases, contracts, risks, and traceability.
- Shortened the Abstract and rewrote the Executive Summary for stakeholder and decision-maker concerns.
- Rendered and inspected every PDF page. Removed forced floats, corrected sparse list and chapter-transition pages, eliminated all overfull boxes, enlarged technical diagrams, and retained portrait layout throughout.
- Revalidated all DOI-bearing bibliography entries through DOI publisher redirects or Crossref. All 23 bibliography entries are cited; citations and cross-references resolve.

## Final evidence status

- The report remains a proposed Deliverable 2 design and evaluation plan because no implementation repository, trained model, experiment logs, measured metrics, or application screenshots were supplied.
- The final build and packaging locations are recorded in `Manzil_D2_Report/REVIEW_NOTES.md` and `Manzil_D2_Report/README.md`.
- Remaining factual confirmations are the exact network and map snapshot, video and annotation sources, selected tracker and final RL configuration, database and hardware, actual screenshots, faculty certificate requirement, official status of `F26-104`, and confirmation of the printed BS(CS) degree labels.

---

# 37. OCTOBER 10 CORRECTIVE REVIEW

- The additional F26-098-1 report was inspected as a formatting reference. Its Chapter 1 and Chapter 3 terminology sections use inline definition lists rather than tables, so Manzil sections 1.3 and 3.1 now follow the same presentation without copying project content.
- The intentional blank verso after the title page was restored to match the supplied FAST template and F26-098-1 preliminary-page sequence.
- The routing cost now distinguishes running time from signal and queue delay and replaces those components when a measured total link time is used, preventing double counting.
- Image occupancy uses the union of overlapping tracked boxes within the region, keeping the proxy in the interval from zero to one.
- The routing algorithm validates a candidate before acceptance, returns the current route explicitly when the threshold is not met, and publishes a new version only for an accepted route.
- The initial simulation protocol specifies a 900-second warm-up, a 3,600-second measurement interval, and ten matched seeds. A pilot may increase but not reduce the predeclared repetitions.
- Ambulance travel time is primary; excess delay uses the free-flow time of the same realized edge sequence, while routing benefit is evaluated through matched policy comparisons.
- GUI figures are explicitly schematic and contain no invented live measurements or comparative results.
- The final submission excludes internal coverage and unresolved-item appendices. These notes remain the authoritative record of unresolved implementation and administrative facts.

---

# 38. MAIN.PDF STRUCTURAL ALIGNMENT (10 OCTOBER 2026)

- The supplied sample `FYP Sample Reports/.../main.pdf` was reopened and used as the direct structural reference for Chapters 1--3.
- Chapter 1 now contains exactly four numbered sections: 1.1 Purpose of this Document, 1.2 Intended Audience, 1.3 Definitions, Acronyms, and Abbreviations, and 1.4 Conclusion. The former Project Status and Report Organization headings were removed; the necessary evidence boundary remains in the conclusion.
- Chapter 2 no longer contains the former Research Questions or Success Criteria sections. It now follows the sample sequence and ends with Section 2.10 Conclusion. RQ labels and dangling research-question references were removed from methodology and design material while preserving the controlled comparisons as evaluation objectives.
- Chapter 3 now follows the sample hierarchy: 3.1 Definitions, 3.2 Detailed Literature Review, 3.3 Literature Review Summary Table, and 3.4 Conclusion. Four Manzil-specific themes each contain numbered Research Overview, Critical Assessment, and Relevance to Manzil subheadings.
- The literature evidence remains technically specific to Manzil and retains all 18 verified studies. It is consolidated into one multi-page portrait longtable rather than using landscape pages or unreadably small text.
- A final paragraph audit found all normal prose within the established range. Retained shorter passages introduce lists or grouped requirements and are structural exceptions rather than body-paragraph substitutes.
- The build reviewed at this stage contained 79 A4 portrait pages. Later SRS and Chapter 6 revisions are recorded in Section 39.

---

# 39. SRS AND DESIGN ALIGNMENT (10 OCTOBER 2026)

- Section 4.7 is titled `Graphical User Interface`. Its five figures remain explicitly identified as proposed wireframes because no implemented interface screenshots were supplied. Each wireframe presents a distinct operator task and is referenced and explained in the surrounding prose.
- The former Section 4.10, Requirements Traceability, and its matrix were removed. Chapter 4 now ends with Risk Analysis and Conclusion; no prose retains a dangling reference to the deleted matrix.
- All eight use cases were reformatted to follow the supplied FAST sample: Name, Actors, Summary, Pre-Conditions, Post-Conditions, Special Requirements, Basic Flow with Actor Action and System Response, and Alternative Flow. The tables remain portrait, use one caption each, and cover failure behavior without inventing implementation results.
- The ER model was redrawn as a readable ownership and cardinality diagram. It separates simulation-run observations from video-job observations, links decisions and metrics to their experiment run, and preserves the mission-to-route-version-to-priority-event chain. The figure is anchored beside its explanation and no longer floats to a mostly empty page.
- Chapter 6 now has exactly eight main sections: System Overview, Design Considerations, System Architecture, Architectural Strategies, Domain Model/Class Diagram, Sequence Diagrams, Policies and Tactics, and Conclusion. Existing detailed material was retained under meaningful numbered subsections rather than deleted.
- Final validation confirmed an 81-page A4 portrait PDF, no landscape or rotated pages, no unnumbered body headings, no subcaptions, and no unresolved citations, cross-references, duplicate labels, overfull boxes, or LaTeX errors. Remaining underfull notices arise from narrow table cells and do not cross the page margins.
- The report date is now 10 October 2026 on both the title page and anti-plagiarism declaration. The three supplied handwritten signatures were background-extracted as transparent PNG assets and mapped, in supplied order, to Muhammad Ali Mahoon, Muzammil Ahmed Bhatti, and Mohammad Ibrahim Salman. The declaration was then reformatted to the supplied reference: centered heading, publication title and declaration text, left-aligned date, right-aligned stacked Name/Signature pairs, divider, and a short Authors' Declaration. The compiled page was visually inspected.

---

# 40. MAIN.PDF SECTION 4 AND CHAPTER 6 REVIEW (21 OCTOBER 2026)

- The supplied `FYP Sample Reports/.../main.pdf` was reopened at its SRS, graphical-interface, database, risk, and high/low-level design pages. Its Section 4 order, screen-inventory presentation, navigation flow, grouped ER views, data dictionary, and detailed Chapter 6 hierarchy were used as presentation references without copying project content or unsupported implementation claims.
- Chapter 4 now follows the sample-compatible order: List of Features; Functional Requirements; Quality Attributes; Non-Functional Requirements; Assumptions; Use Cases; Hardware and Software Requirements; Graphical User Interface; Database Design; Risk Analysis; and Conclusion.
- Section 4.8 now contains a five-screen inventory, a primary navigation-flow diagram, and five individually numbered proposed wireframes for experiment configuration, traffic overview, perception detail, emergency dispatch, and comparative analytics. They remain explicitly proposed screens because no implemented application screenshots were supplied.
- Section 4.9 now contains one complete ER overview, an enlarged experiment-evidence relationship diagram, an enlarged emergency mission and route-version relationship diagram, and the data dictionary. The diagrams preserve exclusive observation ownership, immutable route versions, and route-bound priority events.
- Chapter 6 retains exactly eight main headings. It now includes the requested project-specific subsection hierarchy for system interactions, design assumptions and constraints, architecture decomposition, technology and storage strategies, the domain model, three sequences, and implementation policies and tactics.
- Newly added Chapter 6 explanatory paragraphs were expanded with project-specific ownership, provenance, failure, synchronization, and reproducibility detail to respect the established paragraph-development guideline without inventing implementation results.
- Final validation produced 96 A4 portrait pages. Visual checks covered the title page, declaration, contents, Section 4 screen inventory and navigation, all wireframes, ER views, database discussion, Chapter 6 headings, architecture and domain diagrams, policy pages, conclusion, and bibliography. No landscape page, overfull box, unresolved citation, unresolved reference, duplicate label, subcaption, or unnumbered body heading remains. Narrow-table underfull notices remain non-overflowing template diagnostics.

---

# 41. MAIN.PDF SECTION 4.9 ER-DIAGRAM ALIGNMENT (21 OCTOBER 2026)

- The complete Section 4.9 of the supplied `main.pdf` was inspected again, including its conceptual overview, enlarged ER regions, cardinality conventions, primary-key treatment, captions, surrounding explanation, and transition into the data dictionary.
- Manzil Section 4.9 now follows that presentation pattern with a complete grouped conceptual model and three enlarged, individually numbered views: experiment configuration and evidence, observation and control evidence, and emergency routing and priority.
- The ER figures use blue entity rectangles, green attribute ovals, amber relationship diamonds, underlined primary keys, marked foreign keys, named relationships, and explicit cardinalities. The notation is reproduced for consistency, while the entities and relationships remain specific to Manzil.
- The observation model preserves exclusive run or video-job ownership; the control-decision model records the observation context used by a controller; and the emergency model preserves the immutable mission-to-route-version-to-priority-event chain. These are proposed logical structures and do not imply that a production database has been populated.
- Multiple visual passes corrected overview congestion, attribute collisions, relationship routing, and rotated cardinality text. The final figures remain readable in portrait A4, use one caption each, are referenced and explained in body prose, and lead into the existing data dictionary.
- The validated report now contains 97 A4 portrait pages. The final build has no fatal LaTeX error, unresolved citation or reference, duplicate label, overfull box, landscape page, or subcaption.

---

# 42. DELIVERABLE 2 PRESENTATION (21 OCTOBER 2026)

- A 15-slide presentation was created from the verified report and project context. It covers the problem statement and elaboration, project scope and exclusions, achieved and future goals, summarized R&D evidence, related systems, architecture, decision workflow, methodology, requirements, constraints, limitations, proposed interface, evaluation plan, development roadmap, and closing contribution.
- The presentation distinguishes completed Deliverable 2 work from future implementation and experimental goals. It does not claim a completed system, accuracy, traffic improvement, or deployment readiness.
- FAST and National University branding are used on the title slide. The report's high-level architecture, research workflow, and proposed wireframes are reused as source visuals, while workflow and roadmap relationships remain editable PowerPoint objects.
- Academic sources used in the literature and related-systems slides are recorded in speaker notes. The deck uses one editable native comparison table and contains no fabricated quantitative results.
- The final presentation contains 15 widescreen slides using Segoe UI. Package integrity, expected dimensions, slide count, fonts, bullet geometry, heading fit, and the native-table requirement passed validation with no findings. Every slide was rendered and visually inspected, and workflow arrows and report-image crops were corrected in subsequent passes.
- Final file: `presentation_output/Manzil_Presentation.pptx`. SHA-256: `9FD70EA37F0F363069DC234A2622B9828CB144E8F164DE5012926D4A8594750C`.

---

# 43. PRESENTATION REDESIGN (23 OCTOBER 2026)

- The 15-slide deck was rebuilt as a 12-slide presentation using the supplied `template_for_presentation.pptx` as visual direction. The revised style uses its warm ivory background, restrained blush and taupe accents, thin coral rules, large headings, and increased whitespace without copying the complete template.
- Text density was reduced across the deck while retaining the required problem statement, scope boundaries, achieved and future goals, R&D summary, related applications, requirements, constraints, limitations, methodology, and evaluation content.
- Slide 5 now presents goals as a dependency-based milestone chart. Completed Deliverable 2 research, requirements, architecture, and UI design are visually separated from network preparation, baseline implementation, integration, and evaluation.
- Slide 7 now uses concise checkbox statements for core requirements, constraints, and limitations. A visible fallback rule explains that invalid data, routes, models, or timing must stop the run or trigger a declared baseline.
- The former architecture, decision-workflow, and methodology-image sequence was removed. Slide 8 replaces it with one high-level application-flow diagram covering observation, traffic-state construction, decision, safety validation, SUMO application, and evidence recording.
- Slide 9 uses a newly generated mobile-application concept showing traffic overview, active ambulance mission, route, signal priority, and corridor status. The slide and speaker notes identify it as a concept rather than an implemented screenshot.
- The rebuilt deck contains one editable native R&D comparison table, editable milestone and workflow graphics, and speaker-note citations. No fabricated performance measurements or completed-implementation claims were added.
- Package integrity, 16:9 dimensions, 12-slide count, Arial font policy, heading fit, bullet geometry, and native-table checks passed with no warnings. The final PPTX was rendered into 12 slide images; the montage and full-size inspection found no clipping, overlap, or overflow. `slides_test.py` also reported no overflow.
- Final revised file: `presentation_output/Manzil_Presentation_Updated.pptx`. SHA-256: `2DA19862466B2EEDF8A5196EE7E8372CA6E0AD5D0D86B54AA14AD1BC168DDAD8`.
- The previous `presentation_output/Manzil_Presentation.pptx` was open in another process and could not be overwritten. A backup of that original file is stored under `presentation_build/revision_v2/Manzil_Presentation_before_revision.pptx`; use the updated filename until the open presentation is closed.

---

# 44. TEMPLATE-BASED PRESENTATION REBUILD (23 OCTOBER 2026)

- The presentation was rebuilt again after visual comparison with the supplied `template_for_presentation.pptx`. This version imports and duplicates the template's actual slide layouts, retaining its abstract ivory, beige, and blush backgrounds, coral linework, and embedded Kulim Park and Manrope typography.
- The deck contains 12 newly authored slides: title, problem statement, connected problem, scope, achieved and future goals, Development and R&D, requirements/constraints/limitations, high-level application flow, graphical user interface, methodology, evaluation plan, and closing questions.
- Slide 7 no longer uses checkbox-like notes. It contains genuine native PowerPoint bullet lists with three concise statements under each of Requirements, Constraints, and Limitations. The statements are self-explanatory and the slide preserves substantial white space.
- The goals slide uses a four-stage milestone graphic that clearly separates completed Deliverable 2 design work from network/baseline work, integration, and evaluation. It does not imply completion of unverified implementation work.
- The whole-application flow is an editable diagram covering traffic input, state construction, decision, safety validation, control, and evidence. The former proposed-architecture and methodology images remain excluded.
- The GUI slide retains the generated mobile concept and explicitly labels it as a proposed concept rather than an implemented screenshot. No fabricated test result or performance claim was introduced.
- Package integrity, reference-font policy, slide dimensions, heading fit, bullet geometry, and first-party re-import passed with no findings or warnings. All 12 slides were rendered again from the finalized PPTX and visually checked.
- Final template-based file: `presentation_output/Manzil_Presentation_Template_Design.pptx`. SHA-256: `1E7F5D93EB728FC9C2E776B0625A37F51632CC097F6ED2D61AC8C562CF647474`.

---

# 45. PRESENTATION READABILITY AND TRAFFIC VISUALS (23 OCTOBER 2026)

- A second template-based revision increases the smaller subtitle, body, bullet, diagram-label, milestone-label, evaluation, and footer text while preserving the existing slide boundaries and minimalist spacing.
- Slide 5 now includes a transparent warm-palette illustration of two cars opening a lane for an ambulance. Slide 10 includes a transparent top-down signalized intersection with cars and an ambulance. Both visuals were generated specifically for the deck and their origin is disclosed in speaker notes.
- The new illustration assets are stored as `presentation_build/assets/traffic_ambulance_corridor.png` and `presentation_build/assets/traffic_signal_intersection.png`.
- All 12 finalized slides were rendered again. Full-size inspection covered the text-heavy scope, R&D, requirements, application-flow, GUI, methodology, and evaluation slides. No new clipping, overflow, connector obstruction, or unreadable wrapping was found.
- Package integrity, slide dimensions, reference-font policy, heading fit, bullet geometry, and first-party re-import passed with no findings or warnings.
- Updated file: `presentation_output/Manzil_Presentation_Template_Design_v2.pptx`. SHA-256: `2450463DABFC2C265D0AEB809BDC6AF0773AB4B26FA8696FF401945C8B83DE98`.

---

# 46. PRESENTATION FINAL VISUAL REFINEMENT (23 OCTOBER 2026)

- A third template-based revision adds a standalone transparent traffic signal and compact-car illustration to the open center of the problem-statement slide. It reinforces the traffic context without obstructing either text column.
- The remaining small labels were enlarged, including the related-applications label, GUI concept disclosure, GUI implementation note, and closing team-member line.
- The new asset is stored as `presentation_build/assets/traffic_signal_car.png`; its AI-generated origin is disclosed in the problem slide's speaker notes.
- All 12 finalized slides were rendered and inspected again. The traffic signal, ambulance corridor, and intersection figures remain proportionate to the template and do not overlap text, connectors, or slide boundaries.
- Package integrity, reference-font policy, slide dimensions, heading fit, bullet geometry, and first-party re-import passed without findings or warnings.
- Final refined file: `presentation_output/Manzil_Presentation_Template_Design_v3.pptx`. SHA-256: `C3C0B5BB99C7AF81C5697D70C993BB979BA0755303DE628E3046ADCEE6FF3F98`.

---

# 47. INTEGRATED ARCHITECTURE AND APPLICATION FLOW (23 OCTOBER 2026)

- The original 15-slide presentation was reopened and Slides 8, 9, and 10 were visually reviewed. Their useful content comprised the component architecture and ownership rules, the six-stage decision loop, and the staged research/evaluation workflow.
- Slide 8 of the template-based deck now consolidates those three views into one editable high-level diagram. The diagram is arranged in three visual lanes: declared inputs; the live decision and control loop; and the application, evidence, and validation path.
- The integrated view identifies the SUMO network, recorded-video input, emergency mission, traffic-state builder, normal controller, dynamic route, safety and corridor manager, TraCI execution boundary, operator/mobile interface, run-evidence store, and matched evaluation.
- Direction markers show how normal traffic control and ambulance routing converge at the safety boundary before actuation. The supporting note explains that only the TraCI execution component advances simulation time, while the interface observes the loop and the evidence store retains states, actions, routes, and failures for evaluation.
- Text size and routing were refined after the first render because lane backgrounds suppressed connector visibility. The final version uses explicit directional markers that do not cross node labels and remains legible in the complete slide montage.
- Package integrity, 16:9 dimensions, reference-font policy, heading fit, bullet geometry, and first-party re-import passed with no findings or warnings. All 12 slides were rendered again and the revised architecture slide was inspected at full size.
- Final integrated file: `presentation_output/Manzil_Presentation_Integrated_Architecture_v4_Final.pptx`. SHA-256: `E1B522D59142305432A39A2F9DAC4414D1E338F119722289A352C25BB3BC9202`.

---

# 48. SINGLE CLEAR MANZIL WORKFLOW (23 OCTOBER 2026)

- Slide 8 was simplified after feedback that the lane-based version appeared to contain three separate diagrams. The replacement is one uninterrupted left-to-right control loop with six numbered stages.
- The diagram now communicates the complete project with short labels only: observe traffic through recorded video and SUMO, build the current traffic state, select the controller and ambulance route, validate a safe green corridor, apply the signal action through TraCI, and display and evaluate the result.
- Component ownership remains visible through one short technical label beneath each stage. An intersection illustration connects the emergency mission with ordinary-traffic recovery, while a single feedback statement explains that each SUMO step creates the next observation.
- The traffic-intersection illustration was removed from the methodology slide so it appears only once in the deck. The revised workflow was rendered at full size and checked for legibility, overlap, clipping, and directional clarity.
- Package integrity, slide dimensions, reference fonts, heading fit, bullet geometry, and first-party re-import passed without findings or warnings.
- Final file: `presentation_output/Manzil_Presentation_Clear_Workflow_v5.pptx`. SHA-256: `5153964BE70F79762BC753392EEDB2170A473EE328D5E37CF4FC0DEA6B4E32E7`.

---

# 49. AUTHORITATIVE SPEC DIGEST, CURRENT STATE, AND GAP ANALYSIS (9 NOVEMBER 2026)

This section was produced by re-reading `F26-104_Project-Proposal.pdf` (4 pages) and `F26-104_Deliverable-2_Report.pdf` (98 pages, dated 10 October 2026) in full. Treat it as the condensed specification for implementation. The PDFs remain the authority if anything here conflicts.

## 49.1 Identity

- Group ID **F26-104** is now treated as confirmed (deliverable files are named `F26-104_*`).
- Title: **Manzil: Intelligent Traffic & Emergency Routing**. Supervisor: Miss Umm-e-Ammarah. FAST-NUCES Lahore, BS(CS).
- Members: Muhammad Ali Mahoon (23L-0531), Muzammil Ahmed Bhatti (23L-0688), Mohammad Ibrahim Salman (23L-0723).

## 49.2 Proposal commitments (what the panel approved)

- AI-assisted traffic management and emergency routing, **developed and evaluated in a SUMO simulation** with a web dashboard.
- Objectives: (1) web dashboard; evaluate waiting time, queue length, throughput, ambulance travel time. (2) Safe moving green corridor along the ambulance route. (3) Optimal ambulance route from dynamic traffic, queue, and signal-delay information, with rerouting. (4) Multi-intersection SUMO network with **fixed-time, adaptive, and RL** control. (5) Detect and classify vehicles from traffic video; estimate density, queues, waiting time.
- Scope: a real-world road area imported or reconstructed in SUMO (OSM); normal, congested, and emergency scenarios; YOLO + multi-object tracking on **recorded** video; weighted road-graph routing; FastAPI backend; React dashboard; SUMO + TraCI.
- Excluded: real government signals, city-wide deployment, live government CCTV, traffic forecasting.
- Planned datasets: BDD100K, UA-DETRAC. Pretrained YOLO + tracker, not trained from scratch. RL references: DQN (Liang), PressLight, SUMO-RL.

## 49.3 Deliverable 2 commitments (the detailed spec)

**Core framing.** A research prototype, not a product. Two separate evidence paths share one *traffic-state contract*: (a) recorded video -> detection/tracking -> observations, evaluated against annotations; (b) SUMO -> exact simulated state -> controller, routing, and corridor experiments. They are evaluated separately; there is no claim that video drives the SUMO network unless a later, explicit integration study is done. One active ambulance only.

**Objectives O1-O8.** O1 versioned traffic-state representation; O2 pretrained detector + MOT on held-out, source-separated video; O3 manageable multi-intersection SUMO network + repeatable demand; O4 fixed + rule-adaptive, then one RL controller; O5 time-based dynamic routing with bounded rerouting; O6 safe moving priority + restoration; O7 React dashboard + FastAPI; O8 reproducible, auditable run records.

**Functional requirements (Table 4.1).**
FR-01 validate scenario config (network, controller, seed, duration, demand) before start. FR-02 start/pause/resume/stop one SUMO run. FR-03 simulation adapter is sole owner of SUMO stepping and actuation. FR-04 perception worker processes recorded video into timestamped detections, tracks, metadata, status. FR-05 observation service aggregates into road/lane/approach intervals without mixing sources. FR-06 operator selects fixed / rule-adaptive / RL before a run. FR-07 every signal action records intersection, requested and applied phase, effective step, controller, reason. FR-08 enforce minimum green + yellow/all-red clearance. FR-09 validate ambulance origin/destination; clear no-route response. FR-10 valid remaining path with nonnegative time-based costs + recorded cost snapshot. FR-11 reroute after closure, invalidated edge, or sustained improvement above threshold. FR-12 priority only for a bounded look-ahead set of intersections. FR-13 detect passage/cancellation; restore safe normal control. FR-14 route revision cancels obsolete priority before activating new. FR-15 dashboard shows source mode, sim status, controller, signals, traffic indicators, ambulance position, route, corridor state. FR-16 stale/invalid/disconnected/fallback shown visibly. FR-17 record config, seed, versions, periodic metrics, route revisions, signal events, failures, termination reason. FR-18 comparison aligns runs and warns on incompatible network/demand/duration/warm-up/metric versions. FR-19 export config + metrics in a documented machine-readable format. FR-20 RL loss/invalid action -> fall back to safe baseline and record it.

**Non-functional (Table 4.2).** NFR-01 reproducibility; 02 safety in simulation (no incompatible greens); 03 auditability (requested vs applied); 04 freshness (producedAt + effective step, stale thresholds); 05 responsiveness (deadline set after profiling); 06 isolation (video/dashboard never step SUMO); 07 usability (core demo from one config screen); 08 portability (versioned environments, Docker later); 09 maintainability (typed versioned contracts, one controller interface); 10 data integrity (immutable completed config); 11 privacy (licensed/authorized video only); 12 availability (fail visibly to a safe stopped/baseline state).

**Use cases.** UC-01 configure scenario; UC-02 run/control simulation; UC-03 process traffic video; UC-04 inspect traffic state; UC-05 dispatch ambulance; UC-06 monitor route and corridor; UC-07 handle blockage/route change; UC-08 compare and export runs. Single actor: research operator. Evaluators are read-only.

**GUI (wireframes only so far).** G01 Experiment Configuration, G02 Traffic Overview, G03 Perception & Intersection Detail, G04 Emergency Dispatch & Route, G05 Comparative Analytics. Colour is never the only signal; units, source, and freshness are always visible.

**Data model (ER + dictionary).** Scenario 1:N ExperimentRun; Run 1:N MetricSample, Artifact, ControlDecision, EmergencyMission; VideoJob 1:N Observation; each Observation is owned by exactly one of Run or VideoJob; Observation informs ControlDecision; Mission 1:N RouteVersion (monotonic); RouteVersion 1:N PriorityEvent. PostgreSQL proposed behind a repository interface; file-backed storage allowed during integration.

**Risk register highlights.** Map import lacks valid signals -> synthetic grid fallback. Local video lacks labels/permission -> public data only. RL fails -> report a negative result. Reroute oscillation -> threshold/persistence/cooldown. Insufficient compute -> recorded inference, compact scenarios.

**Methodology (Chapter 5).**
- Network: Lahore OSM extract, about 10-20 signalized intersections (planning range, not fixed); record bbox, date, checksum, conversion command; NetEdit cleanup; synthetic-grid fallback labelled as synthetic.
- Demand: light, medium, heavy + uneven-approach (starvation) case; seeds; warm-up; incidents = edge closure / lane-capacity reduction / obstruction at a fixed time; dev / tuning / held-out scenario split.
- Perception: pretrained YOLO -> ByteTrack (lead) / DeepSORT (comparison) -> bottom-centre point into lane polygons -> line-crossing counts -> interval aggregation: counts, image occupancy (Eq 5.1), queue proxy (slow/stationary tracks in an upstream region), speed proxy (pixels unless calibrated). Metrics: precision/recall or mAP, count MAE (Eq 5.5), queue-proxy error, throughput (fps).
- Fixed-time: declared cycle; green/yellow/all-red/offsets versioned; credible, not deliberately weak.
- Rule-adaptive: pressure score S_p = sum(q_l - q_m) + beta * w_l (Eq 5.2); min green, max green, max-red promotion, shared clearance.
- RL: **parameter-sharing discrete-action DQN**; state = normalized in/out queues, waiting, occupancy, current phase, elapsed time, action mask; action = legal phase or bounded extension; reward r = -a*P - b*W - c*X(starvation) - d*C(switches) (Eq 5.3); safety layer authoritative; emergency status excluded from the RL state.
- Routing: legal-movement graph from SUMO; cost in seconds c_e = T_run + D_signal + D_queue + M_closure (Eq 5.4), no double counting; Dijkstra is the reference, A* only with an admissible free-flow heuristic. Algorithm 1 = stale-cost rejection, NO_ROUTE, threshold theta + persistence window + cooldown, atomic version bump + cancellation of obsolete priority.
- Corridor: Algorithm 2 + Fig 6.6 states IDLE -> REQUESTED -> SAFE_TRANSITION -> ACTIVE_PRIORITY -> PASSAGE -> RECOVERY -> IDLE, plus CANCEL/FAILURE; look-ahead activation using ETA, queue clearance, downstream capacity; max priority duration; timeout.
- Integrated loop: Algorithm 3. A single owner steps SUMO once, then snapshot -> routing -> corridor -> controller -> safety filter -> TraCI apply -> record -> publish dashboard view.
- Protocol: **900 s warm-up + 3,600 s measurement; 10 matched seeds per controller x scenario**; paired differences, SD, CIs; failed runs retained.
- Experiments (Table 5.1): perception vs annotations; fixed vs rule vs RL; static vs dynamic route (signal policy fixed); same routing without vs with corridor; robustness across demand, incidents, seeds, optional observation noise.
- Metrics: mean travel time, waiting time, queue mean/max per approach, throughput, phase changes, max-red/fairness; ambulance travel time, excess delay, stops, route revisions, computation time; ordinary-traffic delay during the mission + recovery interval; recovery time; safety-invariant violations.

**Design (Chapter 6).** Components: React dashboard, FastAPI boundary, Experiment service, Control orchestrator, SUMO/TraCI adapter (sole step/actuation owner), Traffic-state service, Perception worker, Controller registry, Safety filter, Routing service, Corridor coordinator, Experiment store. Contracts (Table 6.3): TrafficSnapshot, ApproachState, SignalState (owner NORMAL|CORRIDOR), ControlRequest, AppliedControl, RoutePlan, PriorityRequest, MetricSample. Failure table 6.4. Testing: unit, invariant/property, small-SUMO integration, scenario replay, headless SUMO smoke test in CI. Modules may begin in one Python process.

## 49.4 What exists in the repository today

- `prototype/` (commit `cc5d81e`): FastAPI backend (`engine.py`, about 370 lines) + React/Vite dashboard (`App.tsx`, about 150 lines). It is a **deterministic Python queue simulator, not SUMO**: six-intersection synthetic network; fixed, pressure-adaptive, and tabular-Q "prototype" controllers; Dijkstra routing with closures and route versions; simplified corridor; mock perception; in-memory state; JSON export; 8 backend tests. Documented in `README.md`, `context.md`, and `docs/*`.
- Final D2 presentation: `presentation_output/Manzil_Presentation_Clear_Workflow_v5.pptx`.

## 49.5 Development machine facts (checked 9 Nov 2026, Ibrahim's laptop)

- Intel i7-8650U (4C/8T, 2018 laptop), 15.9 GB RAM, **Intel UHD 620 only, no NVIDIA/CUDA GPU**.
- Python 3.10.11 and 3.13, Node 22.14, PostgreSQL 17, Docker, WSL, Graphviz, MiKTeX present.
- **SUMO not installed; `SUMO_HOME` unset; `uv` not installed.**
- Implication: YOLO fine-tuning and DQN training at scale need Colab/Kaggle or a teammate's GPU. CPU is fine for SUMO runs on a small network, YOLO inference on recorded clips (slow but offline), and small DQN training.

## 49.6 Gap analysis: spec vs current state

| Area | D2 commitment | Current state | Gap |
| --- | --- | --- | --- |
| Simulator | SUMO + TraCI, single adapter | Custom queue simulator | Install SUMO; write `SumoAdapter`; keep the fallback only for tests |
| Network | Lahore OSM, 10-20 signals, synthetic fallback | 6-node synthetic | Choose area; netconvert; NetEdit cleanup; validate TLS programs |
| Demand/incidents | light/med/heavy/uneven, seeds, closures | Seeded synthetic demand | SUMO route files per profile; closures via TraCI |
| Fixed / adaptive | Credible fixed plan; pressure Eq 5.2 | Implemented on fallback sim | Port to the TraCI phase model with real lane queues |
| RL | Parameter-sharing DQN | Tabular-Q placeholder | Gym/SUMO-RL env, training, checkpoints, held-out evaluation |
| Routing | Eq 5.4 time costs, Alg 1 | Dijkstra on toy graph | Build graph from SUMO net incl. connections; live costs from TraCI |
| Corridor | Alg 2 / Fig 6.6, ambulance obeys signals | Simplified states | Real TLS overrides via TraCI with yellow/all-red and passage detection |
| Perception | YOLO + ByteTrack, counts/queue proxy, MAE | Mock stream | Pick clips + annotate; offline worker; evaluation script |
| Persistence | PostgreSQL behind repository | In memory + JSON | Repository + migrations (Postgres 17 available locally) |
| Dashboard | G01-G05 | One combined page | Split into the five screens; live map from SUMO geometry |
| Evaluation | 10 seeds x (900 + 3600 s), ablations | One-click single-seed compare | Batch runner, analysis notebooks, plots |

## 49.7 Open questions raised with the user on 9 Nov 2026

Next deliverable/deadline and what the panel expects; keep-and-evolve vs rebuild the prototype; Lahore area choice; video source; GPU access; RL ambition; emergency-vehicle detection from video (in the older brainstorm, not in D2); team split; database now or later. Record the answers in section 50.

---

# 50. DELIVERABLE III REQUIREMENTS AND PLANNING ANSWERS (9 NOVEMBER 2026)

## 50.1 University instructions for Deliverable III (R&D projects, FYP-1)

1. Update the chapters from previous deliverables (Chapters 1-6) with the supervisor's feedback incorporated.
2. **Chapter 7 - Implementation and Test Cases:** implementation details of the software component developed or the subproblem solved.
3. **Chapter 9 - Experimental Results and Discussion:** results of the experiments actually conducted.
4. **Chapter 10 - Conclusion and Future Work:** for FYP-1, a plan of the work to be done in FYP-2 is mandatory.
5. Chapter 8 is not listed (in the FAST template it is the User Manual), so it appears not to be required for D3. Confirm with the user.

Implication: D3 needs **real, working SUMO-based implementation and genuine experimental results**, not just design. The FYP-1 scope must be chosen so that at least one subproblem is fully implemented, tested, and evaluated with real numbers. The remaining work becomes the FYP-2 plan in Chapter 10.

## 50.2 Answers from the user (asked one at a time)

**Q1 - Deadline / target.** No fixed date is being planned around. Work proceeds regardless of the due date. Target for the FYP-1 / Deliverable III milestone: a healthy amount of real coding **plus some actual model training**, with visible output that can be shown to evaluators. It is explicitly not the complete FYP. The work will be planned in phases, and a revised plan (including the FYP-2 plan for Chapter 10) will be proposed.

**Standing instruction:** keep the context files updated after every decision or work session (`Manzil_FYP_Context.md` is the master; `context.md` points to it). Commit context updates so they cannot be lost (on 9 Nov an outside process reverted this file to its committed version and deleted sections 49-50; they were restored from scratch copies).

**Q2 - Which model to train first.** **Option C: both, in parallel.** The vision model (pretrained YOLO fine-tuned on traffic video, with a tracker and counting) starts immediately as an independent track because it does not depend on SUMO. The signal-control RL model (parameter-sharing DQN in SUMO) follows the SUMO setup, fixed-time, and rule-adaptive controllers in the main track. Deliverable III should therefore contain trained-vision results and, if reached, first DQN training/evaluation results.

**Q3 - Compute.** Use **Kaggle** for GPU training, driven from the local machine through the **Kaggle API/CLI**. Workflow: notebooks/scripts live in the repo; `kaggle kernels push` with `kernel-metadata.json` (`enable_gpu: true`, `enable_internet: true`), then `kaggle kernels status` and `kaggle kernels output` to pull trained weights and metrics back; datasets are uploaded with `kaggle datasets create/version`. Setup needed: Kaggle account with phone verification (required for GPU and internet), an API token placed by the user in `C:\Users\X1 Carbon\.kaggle\kaggle.json` (never pasted into chat or committed), and `pip install kaggle`. Free GPU quota is about 30 h/week. The local laptop (no CUDA) is used for SUMO, DQN on a small network, and offline YOLO inference.

**Q4 - Team working model.** Ibrahim and Claude will do most of the work. Ali and Muzammil will also work through Claude, on their own devices, following the same plan. Consequence: the plan, task status, decisions, and context **must live in the Git repository** (committed and pushed to `alimahoon1/fyp-kaam`), be self-contained, and be readable by any fresh Claude session on any machine. No essential state may live only in one machine's local Claude memory. Task ownership is therefore per task, not per fixed track.

**Q5 - Sync setup.** Approved. `CLAUDE.md` (auto-loaded by Claude Code: project summary, read-first list, working rules) and `PLAN.md` (phases, tasks, status, owners) were created at the repo root. **Claude is authorised to commit and push automatically after each work session**, without asking each time.

**Q6 - D2 feedback.** Overall the feedback was positive. The only substantive point: **no coding had been done**, and the evaluators expect to see **working code and real implementation progress at the next evaluation**. There were no specific corrections to the content of Chapters 1-6. For D3, Chapters 1-6 therefore need a light update: reflect what is actually implemented, move statements like "no implementation exists yet" to the current status, and align the design chapters with the real code. The main D3 weight is Chapters 7, 9, and 10 backed by a live demo.

**Q7 - Existing prototype.** **Option B: start fresh.** The old prototype is not up to the mark and the new work must incorporate new concepts, so it is not considered further. It was moved to `archive/prototype_v0/` together with its README, docs, checklist, and old `context.md` (see `ARCHIVED.md` there). The root `README.md` was rewritten, and the root `context.md` is now a short pointer to this file. The new codebase is built from scratch around SUMO, following the D2 architecture.

**Q8 - Road network.** **Grid first, then Lahore.** Step 1 is a clean synthetic 3x3 SUMO grid (9 signalised junctions) used as a test track for controllers, routing, and the corridor. Step 2 is a real Lahore OSM extract (about 10-20 signals, with a hospital as destination B). The **specific Lahore area and hospital are not yet chosen**; this is an open task. Key design rule agreed with the user: **all code must be network-agnostic** and read junctions, traffic lights, phases, lanes, and connections from the SUMO `.net.xml`, so switching from the grid to Lahore needs no code rewrite, only map cleanup. The user's concern was that grid-then-Lahore might cause problems; it was explained that the core idea (ambulance A -> B with AI-controlled signals across the area) is unchanged, and that the whole city is out of scope per the proposal and D2.

**Q9 - Video data.** **Option C: both.** Train mainly on **UA-DETRAC** (pre-labelled, fixed traffic-camera view, available on Kaggle). Record **2-3 short Lahore clips** (stable phone, overpass/rooftop, 1-2 min each) and label a small held-out part only for **testing** domain transfer. Fallback if filming is not possible: UA-DETRAC only.
Labelling approach (agreed): **AI-assisted pre-labelling + human correction.** A strong pretrained detector (and an open-vocabulary detector such as YOLO-World or Grounding DINO for classes COCO lacks, like rickshaw) draws draft boxes; a team member reviews and corrects them in a labelling tool (CVAT or Label Studio, free). Sample about 1 frame per second rather than every frame. **Test-set labels must be human-verified**, otherwise the model is graded against its own output (circular evaluation). For count-error (MAE) evaluation, local clips only need **manual vehicle counts per time interval** crossing a line, which is much faster than drawing boxes.

**Q10 - Vehicle classes.** **Option C: start simple, add rickshaw later.** FYP-1 classes: **car, bus, truck, motorcycle** (all present in COCO-pretrained YOLO). UA-DETRAC mapping: car -> car, bus -> bus, van -> car, others -> truck (to be confirmed when the data is inspected). UA-DETRAC has no motorcycle labels, so fine-tuning must not make the model forget motorcycles. Mitigation: mix in a motorcycle-containing source (e.g. a BDD100K or COCO subset, or the labelled Lahore frames), or evaluate motorcycles separately. **Rickshaw (and optionally van) is added in FYP-2** once enough Lahore footage is labelled; this goes into the Chapter 10 FYP-2 plan.

**Q11 - Ambulance behaviour.** **Option A for FYP-1: the ambulance obeys traffic signals.** It is a normal SUMO vehicle type (vClass emergency allowed for lane permissions, but without SUMO's red-light-ignoring emergency behaviour or bluelight device). It gets through faster **only because the Manzil corridor changes signals ahead of it**, so the corridor's contribution is measurable (same trip and seed, corridor off vs on). Optional later (Option C): one extra reference run using SUMO's built-in red-light-ignoring mode as an upper bound.

**Q12 - FYP-1 vs FYP-2 scope.** **Option B: balanced.**
- **FYP-1 (Deliverable III):** 3x3 SUMO grid with light/medium/heavy(/uneven) demand; fixed-time + rule-adaptive (pressure) controllers; a first trained DQN; a three-way controller comparison; ambulance A -> B with time-based routing and closure-triggered rerouting; moving green corridor with off-vs-on comparison; YOLO fine-tuned on Kaggle with tracking and counting and accuracy numbers (plus 1-2 Lahore test clips if filmed); demo through SUMO-GUI plus a simple first dashboard (live map, signal states, ambulance status).
- **FYP-2:** Lahore OSM network; full five-screen dashboard (G01-G05) + database; the full D2 protocol (10 seeds, 900 + 3600 s, held-out scenarios); rickshaw class; video-to-SUMO integration study; polish and robustness.
The detailed phased plan is in `PLAN.md`.

## 50.3 Working setup and Phase 0 results (10 Nov 2026)

**Q13: how the work runs.** The user chose the hybrid model. Short setup tasks that need the laptop (SUMO on Windows, Kaggle token) are done locally. The long coding phases (1–5) run mostly as **Claude Code cloud sessions** (claude.ai/code), which push to GitHub while the laptop is off; Ibrahim follows them and answers questions from the Claude phone app. Rules for cloud sessions are in `CLAUDE.md` ("Cloud sessions").

**SUMO install decision.** SUMO comes from PyPI (`eclipse-sumo==1.28.0`, with `libsumo`, `traci`, `sumolib` at 1.28.0), not the Windows installer. That way every laptop and the cloud get the same version from `pip install -e ".[dev]"`. On Ibrahim's laptop it lives in the repo `.venv` (Python 3.10.11), and `SUMO_HOME` is set as a user environment variable pointing to `.venv\Lib\site-packages\sumo`.

**Verified on Ibrahim's laptop:**
- `sumo`, `sumo-gui` and `netgenerate` 1.28.0 are present.
- A throw-away smoke test passed: a `netgenerate` 3×3 grid with traffic lights, plus `randomTrips`, ran 400 steps via libsumo and reported 9 traffic lights.
- `pytest`: 4 passed (`tests/test_setup.py`); ruff is clean.

**Not yet verified:** `scripts/cloud_setup.sh` has not been run on Linux. The first cloud session checks it.

**Note:** the GitHub remote is `alimahoon1/fyp-kaam` (Ali's account). To install the Claude GitHub app for cloud sessions, the repo owner may need to approve it.

## 50.4 First cloud session: setup check, grid network and demand (9 Nov 2026)

**Cloud setup.** Two problems were found and fixed. (1) The environment setup script runs from the folder above the repo, so `bash scripts/cloud_setup.sh` was not found. The environment's script is now `if [ -d fyp-kaam ]; then (cd fyp-kaam && bash scripts/cloud_setup.sh); fi`. (2) In the cloud image, `pip install --upgrade pip` fails because Debian manages pip, so `scripts/cloud_setup.sh` now treats that step as optional. After the fixes the script ran end to end on Linux (Python 3.13), and `pytest` passed. One pip download at container start was very slow (about 80 KB/s); a later retry ran at normal speed.

**Task 1.1, network.** `manzil/scenarios/grid.py` wraps `netgenerate`: 3×3 grid, 200 m blocks, 200 m attached fringe roads, 2 lanes per direction, 50 km/h, the nine inner junctions set as traffic lights, no U-turns. The result has 9 four-arm signalised junctions and 12 dead-end fringe nodes. The file keeps SUMO's default static program (42 s green, 3 s yellow, 90 s cycle); Manzil controllers replace it at run time. `network.json` records the command, the SUMO version and a `content_sha256` that ignores SUMO's "generated on" timestamp, so rebuilding unchanged gives the same checksum. It is labelled synthetic, as D2 requires.

**Task 1.2, demand.** Deviation from the plan wording: an own seeded generator is used instead of `randomTrips`. Reason: it controls the rate per entry road directly, which the uneven (starvation) profile needs, and it is easy to test. Entry and exit roads are found from the network (edges at dead-end nodes; north-south is decided from the edge direction), so it is network-agnostic. Arrivals are Poisson per entry road (numpy PCG64, seeded), destinations are uniform with no U-turn, and `duarouter` writes the routes. Rates per entry road: light 200, medium 400, heavy 600, uneven 800 north-south / 100 east-west veh/h. They were calibrated by a sweep with default signals (on seed 0, 750 veh/h already caused a jam teleport and 900 left vehicles unserved). Generated files are git-ignored and rebuilt from the seed.

**Result (real, default SUMO signals, not a controller result).** 3,600 s of demand + up to 1,800 s drain, seeds 0–4: all 20 runs were gridlock-free (0 teleports, 0 collisions, every vehicle arrived). Mean waiting time was 26.6 s light, 31.4 s medium, 62.6 s heavy, 45.6 s uneven. Full table: `scenarios/grid3x3/README.md`; raw: `results/phase1/demand_check.json`. Tests: 23 passed (`tests/test_grid.py`, `tests/test_demand.py`, `tests/test_setup.py`); ruff is clean.

**Not done yet:** looking at the grid in `sumo-gui` (cloud sessions are headless; it was checked with `sumolib` and headless `sumo` instead). Next task: 1.3 `SimulationAdapter`.

## 50.5 SimulationAdapter and network reader (tasks 1.3 and 1.4, 9 Nov 2026)

**Merge rule.** Ibrahim told the cloud session to merge its own PRs into `main` and keep working, sending summaries. PR #1 (tasks 1.1/1.2) and PR #2 (claim of 1.3–1.8) were merged this way.

**Network reader (`manzil/sim/network.py`).** For every traffic light it reads, from the `.net.xml` only: the controlled links (TLS link index, from/to lane, direction, junction request index), the approaches (incoming edges and their lanes), and the outgoing lanes. Green phases are the program phases that have green and no yellow; controllers choose among these, and the safety filter generates yellow and all-red. It also reads the junction `<request>` foe and response matrices. **Conflict rule:** two foe links may be green together only if one is a minor green `g` that must yield to the other (e.g. a permissive left facing oncoming traffic). This is the exact check used for the "no conflicting greens" invariant. SUMO's own grid phases pass it, while all-green and "permissive left promoted to `G`" fail. Joined traffic lights that span several junctions raise `NotImplementedError` for now; this may matter for Lahore.

**Adapter (`manzil/sim/adapter.py`).** The only module that imports `traci`/`libsumo` (a test enforces this, FR-03). It has two backends with one API: `libsumo` (default, fast, one instance per process) and `traci` (separate process, needed for `sumo-gui`). Each step it reads lane subscriptions (vehicles, halting, waiting time, mean speed, occupancy), signal states and arrival/departure counts into a `TrafficSnapshot` with per-approach `ApproachState` (empty approach speed = `None`, because missing is not zero). Signals are written only through `set_signal_state`. Both backends gave identical lane states in a test. Speed: about 1 ms per step on the grid with medium demand.

**Bug found and fixed.** Importing `libsumo` sets `SUMO_HOME` to the data-only `sumo_data` package, so SUMO tools were no longer found. `sumo_home()` now trusts `SUMO_HOME` only if it contains SUMO's `tools` folder. A regression test was added.

## 50.6 Safety filter, fixed-time controller, metrics and reproducibility (tasks 1.5–1.8, 9 Nov 2026)

**Safety filter (`manzil/control/safety.py`).** Controllers only request a green phase (`ControlRequest`, no side effects). The filter holds a switch until minimum green (10 s), then shows yellow (3 s), all-red (2 s) and the new green. Links that are green in both phases stay green. A request during a transition cannot change it, and unknown phases are rejected. Every switch or intervention becomes an `AppliedControl` record (requested vs applied phase, intervention type, step, reason). Requests that change nothing are only counted. Timing is shared by all controllers and lives in `scenarios/grid3x3/signals.json` (version 1). An independent `SafetyMonitor` checks every shown state: exact conflicting-green rule (from 50.5), declared greens only, yellow before red for at least 3 s, and minimum green. It runs in every experiment and reports `safety_violations`. A random controller (5,000 steps without SUMO, plus 600 steps in real SUMO) produced 0 violations, and the monitor catches deliberately unsafe sequences.

**Fixed-time controller (`manzil/control/fixed_time.py`).** Time-driven: it requests the phase whose window holds `(t + offset) mod cycle`, with cycle = sum of greens + phases × 5 s clearance. Offsets are supported (all 0 on the grid). Plans were tuned per profile on **dev seeds 100–101 only** (the evaluation seeds 0–4 stay untouched), because D2 requires a credible baseline with splits from the declared demand: light 20/20 s, medium 25/25 s, heavy 45/45 s, uneven 45/25 s (north-south/east-west). On uneven demand, giving east-west 20 s or less made everything worse (the internal east-west links carry turned traffic). The sweep table is in `scenarios/grid3x3/README.md`. In a test run every shown interval was exact (green 45/25 s, yellow 3 s, all-red 2 s).

**Runner and metrics (`manzil/experiments/`).** `RunConfig` is validated before start (FR-01). The loop follows Algorithm 3. Each run folder has `manifest.json` (config + digest, seed, Manzil/SUMO/Python versions, git commit + dirty flag, network checksum, demand manifest, controller plan, safety timing, SUMO arguments, termination reason, wall time), plus `metrics.json`, `timeseries.csv` (60 s), `signal_events.csv`, `applied_controls.csv` and the raw SUMO outputs. Metric version 1 definitions are in the `metrics.py` docstring. Travel and waiting time cover vehicles that departed in the window and finished; vehicles still driving at the end are counted separately as `unfinished_veh`, so congestion cannot hide.

**Reproducibility (1.8).** The same config gives identical `metrics.json` (test). libsumo and traci also give identical metrics, and a full-length heavy rerun was identical.

**Result (real, single seed 0, 900 s warm-up + 3,600 s, fixed-time, tuned plans):** mean travel time 98.6 s light, 109.6 s medium, 172.5 s heavy, 120.2 s uneven. Mean waiting time 23.2 / 30.7 / 75.4 / 38.5 s. Max approach queue 6 / 16 / 37 / 24 vehicles. 0 teleports, 0 collisions, 0 safety violations. A run takes 3–9 s of wall time. File: `results/phase1/fixed_time_seed0.json` (recorded from an uncommitted working tree, so its git `dirty` flag is true). Tests: 65 passed.

## 50.7 Adaptive controller and first controller comparison (Phase 2, 10 Nov 2026)

**Adaptive controller (`manzil/control/adaptive.py`, D2 Eq 5.2).** Score S_p = Σ served incoming-lane queues − α Σ fed outgoing-lane queues + β × (largest accumulated waiting time among the served approaches). Each lane is counted once per phase. Deviation from a literal per-movement sum: an incoming lane that feeds two movements is not double counted. Exit lanes can be fed by both phases, so downstream queues lower both scores. Rules: no request during a transition or before the minimum green / controller minimum hold; max-red promotion; max green forces the best other phase; otherwise switch only if another phase beats the current one by more than the switch margin. Every request carries its scores (e.g. `pressure S=[12.0, 3.5]`), and switches appear in `applied_controls.csv`.

**Tuning (dev seeds 100–101 only, 60 settings).** One parameter set for all profiles: α 0.5, β 0.02, max green 40 s, max red 90 s, switch margin 3, minimum hold 15 s (`signals.json` v3). `min_hold_s` was added after sweep 1 showed too many switches in heavy demand. Full list: `results/phase2/adaptive_tuning_dev_seeds.csv`.

**Batch runner and comparison.** `batch.py` runs arms × profiles × seeds in parallel (spawned processes, because libsumo allows one per process) and refuses to compare runs with a different network, demand generator, protocol or metric version (FR-18). `compare.py` gives mean ± SD, paired differences against tuned fixed-time with 95 % t intervals, and the number of seeds that improved, plus plots. The `.gitignore` rule `runs/` became `/runs/`, so committed batch results keep each run's `manifest.json` and `metrics.json`; per-run CSVs are ignored.

**Result (real; seeds 0–4; 900 s warm-up + 3,600 s; synthetic 3×3 grid).** Three arms: fixed-time with a plan tuned for each profile, fixed-time with one 35/35 plan for every profile, and adaptive with one parameter set. Adaptive vs tuned fixed-time (paired mean difference, 95 % CI):
- Mean waiting time is lower on every profile, on 5/5 seeds each: light −0.4 s (−1.9 %), medium −6.4 s [−6.8, −6.0] (−21.1 %), heavy −8.1 s [−9.8, −6.3] (−10.6 %), uneven −2.4 s [−3.1, −1.8] (−6.5 %).
- Mean approach queue is lower on every profile (−2 % to −22 %). Max queue in heavy: 29.0 vs 36.8 vehicles (−21 %).
- Mean travel time is lower only on medium: −4.7 s [−5.1, −4.2] (−4.3 %). It is slightly higher on light (+0.6 s), heavy (+2.8 s [0.2, 5.5], +1.6 %) and uneven (+3.1 s [2.0, 4.1], +2.6 %).
- Throughput: no clear difference (all within ±0.2 %).
- Max red is 50 s for adaptive vs 30–55 s for fixed-time.

Against the single-plan fixed-time, adaptive is much better on uneven demand: travel time 121.6 vs 149.3 s, waiting time 34.9 vs 59.4 s.

**Reading.** Adaptive cuts stopped time and queues, but against a fixed-time plan already tuned for each profile it does not cut total travel time, except on medium. The likely reason is the extra switching: in heavy demand there were 1,535 phase changes vs 648, each with 5 s of yellow/all-red, which turns long stops into more stop-and-go. This explanation is plausible but not yet tested. When demand is not known in advance (one plan for all), adaptive clearly wins on uneven demand. This is a mixed, honest result for Chapter 9. It also gives the DQN (Phase 4) a clear target: keep the waiting/queue gains without the extra switching cost. Files: `results/phase2/comparison/summary.md`, `comparison.png`, `results.csv`.

## 50.8 Ambulance routing, rerouting and green corridor (Phase 3, 10 Nov 2026)

**Routing (`manzil/routing/graph.py`).** Graph nodes are SUMO edges; an arc exists only for a real lane connection usable by vClass `emergency`, so every route is drivable and no U-turns appear. Eq 5.4 cost in seconds = free-flow run time (at the reported speed limit when an incident lowered it) + halting vehicles × 2 s headway / lanes + a declared 10 s signal delay at signalised edges + infinity when closed. No measured link time is added on top (no double counting). Snapshots older than 5 steps, or with negative costs, are rejected. A* uses straight-line distance / max speed scaled by the smallest edge-length / node-distance ratio (0.896 on the grid), because SUMO edge lengths exclude junction interiors. That scaling keeps the heuristic admissible: it was checked on all 48 × 48 pairs, and A* = Dijkstra on 200 random cost sets.

**Algorithm 1 (`manzil/routing/mission.py`).** Refresh every 5 s from the ambulance's current edge. A crossed closure is accepted at once (trigger `closure`). Otherwise a candidate must save more than δ = 10 s for τ = 10 s with a 30 s cooldown (trigger `improvement`). Rejected candidates are logged. Route versions are immutable and numbered 1, 2, …; NO_ROUTE cancels the corridor. Static routing = one free-flow plan at dispatch. Values are initial settings, not tuned yet.

**Algorithm 2 (`manzil/corridor/coordinator.py`).** Look-ahead = the next 2 signalised junctions on the route. Activation when the free-flow ETA ≤ 15 s + queue clearance on the ambulance's approach. The corridor then *owns* the junction in the safety filter (new owner flag; normal requests wait and are counted) and requests the phase giving the movement a priority green. Minimum green, yellow and all-red still apply. Max priority is 60 s (then timeout and cancel). Passage = SUMO route index past the approach edge; ownership then returns to normal control immediately (legal through the filter). Recovery time = until the junction queue is back to its typical level (mean of the 120 s before activation); open recoveries at run end are counted as unfinished. A route revision cancels requests not on the new route (FR-14). Not implemented yet: the downstream-capacity check and a compensation plan in recovery.

**Adapter additions.** Per-edge state, tracked vehicles (ambulance), insertion of the ambulance type (vClass emergency, sigma 0, speed factor 1, no blue light), `set_route`, `close_edge` and `slow_edge`. Background vehicles are rerouted around a closure by SUMO's router. Closure runs use `--ignore-route-errors`, because otherwise SUMO refuses pre-routed vehicles at insertion; the adapter reroutes them on their first step. A waiting-to-enter ambulance (road id "") is handled, and its insertion wait counts in the response time.

**Results (real, seeds 0–4, fixed-time background signals; details in `results/phase3/README.md`).**
- Static vs dynamic routing with an obstruction on the static route: ambulance time 307.8 → 144.6 s (medium, −53 %, CI [−200, −126] s) and 588.2 → 298.0 s (heavy, −49 %), 5/5 seeds each, with no harm to ordinary traffic. The first attempt with a 900 s window left 4/5 heavy static trips unfinished. It was re-run with 1,800 s so that no failures were silently dropped.
- Corridor off vs on: 154.0 → 102.6 s (medium, −33 %) and 313.8 → 133.4 s (heavy, −57 %), 5/5 seeds; time stopped −92 % / −90 %. Cost to ordinary traffic: network queue in the mission window +3.5 % (medium, CI crosses 0) and +5.8 % (heavy, CI [+1.4, +15.6] vehicles); mean waiting +2.3 % / +3.9 %. Recovery 8.3 s / 12.0 s.
- 0 safety violations and 0 collisions in all 40 runs.

**Bugs found on the way.** (1) The router could not see an obstruction, because slow vehicles are not "halting"; it now uses reported speed limits. (2) SUMO's fatal error on closure-crossing pre-routed vehicles (fixed as above). (3) The ambulance waiting to enter a full road crashed the metrics. (4) A formatter-reflowed line made an edit silently miss, so batch arms ignored labels. A test now covers labels through the study runner.

Tests: 98 pass.

