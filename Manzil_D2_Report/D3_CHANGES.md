# Changes to Chapters 1–6 for Deliverable III (task 6.1, 15 Nov 2026)

These changes were made to the D2 LaTeX source in this folder. The submitted D2 PDF is unchanged at `../F26-104_Deliverable-2_Report.pdf`; git history holds the D2 source. Build with `.\build.ps1` (or run the same pdflatex/bibtex steps from bash if PowerShell stops on the MiKTeX update notice). Result: 110 pages, with no overfull boxes and no undefined references or citations.

## A. D2 formatting feedback

1. **Unnumbered "Manzil implication" headings (pp. 29–33).**
   - Those lines were the bold column headers of the literature table (Table 3.1), repeated at the top of each page. Every continued page now starts with "Table 3.1: Summary of literature review (continued)", so the header is clearly part of the table.
   - The same continued caption was added to all other multi-page tables: Tables 4.1 (functional requirements), 4.2 (NFR), the data dictionary, the risk register, and Tables 6.1, 6.2 and 6.4 (components, decisions, contracts).
   - The risk register had no repeated header on its second page; it now has one.
2. **Headings with no text before the next subheading.** An introductory paragraph was added under all 14 such headings:
   - 3.2.1–3.2.4 (the four the evaluator named, and 3.2.4 with the same problem);
   - Chapter 1 (before 1.1), 4.9 Database Design, 5.2 Network and Scenario Preparation, 5.4 Normal Traffic Controllers, 5.8 Experimental Protocol;
   - 6.2 Design Considerations, 6.4 Architectural Strategies, 6.6 Sequence Diagrams, 6.7 Policies and Tactics, 6.7.5 Implementation Policies.
   
   A script check now finds no heading followed directly by another heading.
3. **Bold text inside paragraphs** (A*, API, CV …). The bold came from the labels of the two definition lists (Sections 1.3 and 3.1). Labels are now normal weight (`font=\normalfont`). No `\textbf` remains in body paragraphs; bold is used only in table header rows and diagram boxes.

## B. Content updated to match the FYP-I implementation

**Front matter (main.tex)**
- Abstract rewritten: what was built, plus the key real results (DQN −9 to −11 % travel time; dynamic routing about halves ambulance time; corridor −34 to −59 %; YOLO mAP50 0.799; count MAE 2.60).
- Executive Summary: second paragraph rewritten in plain language with the FYP-I results and the FYP-II plan.
- **Not changed:** the title-page and declaration date (still 10 October 2026). It needs the D3 submission date.

**Chapter 1**
- New chapter intro paragraph.
- 1.1 Purpose rewritten for Deliverable III: what was implemented; evidence is simulation and public video, not field.
- 1.3: added ByteTrack, Double DQN, FYP-I/FYP-II, UA-DETRAC, WAPE; TraCI now mentions libsumo.
- 1.4 Conclusion: evidence boundary updated. Results now exist; Lahore, the full dashboard and DB, local video and 10 seeds remain FYP-II.

**Chapter 2**
- New Table 2.1 "Status of the objectives at the end of FYP-I". O1, O2, O4, O5, O6 and O8 are implemented; O3 and O7 are partial. A paragraph above it explains the O2 extension (fine-tuning) and O3 (synthetic grid first).
- 2.5 Scope: added the FYP-I / FYP-II split.
- 2.7 Constraints: the open choices are now fixed facts:
  - ByteTrack and Double DQN;
  - file storage;
  - laptop without GPU, with Kaggle 2× T4;
  - 3×3 grid;
  - 10 s / 3 s / 2 s timing.
- 2.10 Conclusion: one sentence on objective status.

**Chapter 3**
- Intro paragraphs (A2) say what FYP-I adopted from each theme.
- The conclusion has one sentence pointing to Chapter 9.

**Chapter 4**
- Chapter intro: one sentence on the new status column.
- **Table 4.1** has a new "FYP-I status" column for FR-01…FR-20:
  - Implemented: 13 (FR-01, 03, 06–14, 17, 18);
  - Partial: FR-02 (no pause), FR-04 (offline Kaggle job), FR-05, FR-15 (simulation source only), FR-19 (files, no export command), FR-20 (holds current phase);
  - Planned: FR-16 (stale-data warnings).
  
  A paragraph after the table explains FR-08 (the 5 s corridor exception) and FR-20.
- 4.3.4 Performance: measured values replace "no benchmark exists":
  - about 1 ms per SUMO step;
  - < 0.1 ms per route;
  - 60 runs in about 100 s;
  - YOLO 6.8 ms per image on a T4;
  - tracking at 40–66 fps.
- 4.5 Assumptions:
  - WebSocket and SVG map are now used;
  - PostgreSQL and Docker are not used; DB moved to FYP-II.
- 4.7 Hardware and software: both tables rewritten with the real machines and pinned versions:
  - hardware: i7-8650U, 16 GB, no GPU; Kaggle 2× T4;
  - software: SUMO 1.28.0, Ultralytics 8.4.210, PyTorch 2.9.1, FastAPI 0.162.5, React 19, Kaggle CLI 2.2.5, pytest/Ruff.
- 4.8 GUI: new paragraph and **Figure 4.8, a real screenshot of the FYP-I dashboard** (from `results/phase5/04_corridor_active.png`). The wireframes stay as the FYP-II target.
- 4.9 Database Design: intro explains that the model is stored as versioned run files in FYP-I, with a DB in FYP-II.
- 4.10 Risks: paragraph on which risks happened and how they were handled:
  - synthetic grid;
  - no local video;
  - max-red guard;
  - misleading finished-trips metric.
- Conclusion: last sentence updated.

**Chapter 5**
- Intro points to the new deviations section.
- 5.2: paragraphs on the real grid (3×3, 200 m, 2 lanes, 50 km/h, 9 signals, checksum) and the demand generator (seeded Poisson; 200/400/600 and 800/100 veh/h).
- 5.3 Perception: paragraph on the real pipeline:
  - YOLO11s fine-tuned, 50 epochs;
  - class mapping and COCO motorcycles;
  - sequence split, 40 test sequences;
  - ByteTrack and a counting line at 60 %;
  - ground truth through the same counter;
  - stopped-vehicle queue proxy.
  
  Occupancy and speed proxies are not computed.
- 5.4.1 Fixed-time: per-profile plans tuned on dev seeds (20/20, 25/25, 45/45, 45/25 s) and the 35/35 single-plan arm.
- 5.4.2 Adaptive: the parameter values; each lane is counted once.
- 5.4.3 renamed "Reinforcement-Learning Formulation" (was "Proposed …"), with a paragraph on the real agent:
  - 26-value observation, 128-128 network, 5 s decisions;
  - reward weights;
  - seed split;
  - 200 episodes, episode 180 selected.
  
  It also states that the reward uses mean queue instead of the pressure term.
- 5.5 Routing: real graph and costs, the A* scaling of 0.896, and δ/τ/cooldown values.
- 5.6 Corridor:
  - real values: look-ahead 2, 15 s, 60 s;
  - downstream check and compensation not implemented;
  - Algorithm 2 line now says "corridor minimum green";
  - **new 5.6.1 "Corridor Version 2 and the Minimum-Green Exception"**: the stop-reason study, the reroute bug, which options were tested, kept and rejected, and why.
- 5.8: intro, the reduced protocol (5 seeds; emergency window 900/1,800 s), and the metric that includes unfinished vehicles.
- **New 5.9 "Deviations from the Deliverable 2 Method"**, Table 5.2 with 11 rows:
  - synthetic grid;
  - fine-tuned detector;
  - count ground truth;
  - Poisson demand;
  - reward term;
  - 5 s corridor min green;
  - max-red guard;
  - FR-20 fallback;
  - corridor downstream/compensation;
  - 5 seeds;
  - files instead of DB.
  
  It states honestly that the corridor change was chosen on the same seeds 0–4 used to report it.
- Conclusion: points to Table 5.2.

**Chapter 6**
- Intro points to the new mapping section.
- Captions: "Proposed high-level architecture" became "High-level architecture"; "Proposed domain model" became "Domain model".
- Persistence is now described as files in FYP-I and a DB in FYP-II, in the text and in the decision-table rows for persistence and perception.
- **New 6.3.6 "Implementation Mapping"**, Table 6.3: each design component and the module that implements it.
- 6.4.1 Technologies: the open choices are now confirmed.
- 6.4.6 Storage: describes the run-folder files.
- 6.5 Domain model: implemented class names (ControlRequest/AppliedControl, RoutePlan, CorridorCoordinator, MissionDriver).
- 6.7.1 Corridor states: SAFE TRANSITION uses a 5 s minimum for corridor requests.
- Table 6.5 Failure handling: the "RL service unavailable" row now describes the real behaviour.
- 6.7.6 Testing: 147 tests in 17 files, with examples.
- 6.7.7/6.7.8: there is no hosted CI yet; lint and the full test suite run before every merge.
- 6.7.9 Source code: the real folder layout.

## C. Still open (needs the team)

- D3 submission date for the title page and declaration.
- Chapters 7, 9 and 10 are not written yet (tasks 6.2–6.4).
- The report folder is still named `Manzil_D2_Report`; rename it when D3 is finalised if wanted.
