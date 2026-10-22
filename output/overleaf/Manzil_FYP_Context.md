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
