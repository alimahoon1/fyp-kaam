# Manzil — Work Plan

Status values: `todo` · `in progress (Name)` · `done` · `blocked (reason)`.
Update this file whenever a task changes status, then commit and push (see `CLAUDE.md`).

## Current stage

**Planning for Deliverable III** (FYP-1). We are going through the planning questions one at a time. The answers are recorded in `Manzil_FYP_Context.md` section 50.2. The phases and tasks below are filled in once the questions are done.

## Deliverable III requirements (from the university)

- Chapters 1–6 updated, with supervisor feedback incorporated
- Chapter 7: Implementation and Test Cases
- Chapter 9: Experimental Results and Discussion
- Chapter 10: Conclusion and Future Work, including a mandatory FYP-2 plan

## Decisions so far

| # | Decision |
|---|---|
| 1 | No fixed date to plan around. Target is real coding + real model training + visible output for evaluators. |
| 2 | Train both models: YOLO vision as a parallel track starting now; DQN signal control after SUMO + baselines. |
| 3 | GPU training on Kaggle, driven through the Kaggle API/CLI. |
| 4 | Ibrahim + Claude do most of the work; teammates also use Claude from this same repo plan. |
| 5 | `CLAUDE.md` + `PLAN.md` coordinate all sessions; Claude commits and pushes automatically after each work session. |
| 6 | D2 feedback was positive; main demand is working code at the next evaluation. Chapters 1–6 only need a light update to match the real implementation. |
| 7 | Start fresh around SUMO. The old prototype is archived in `archive/prototype_v0/` and not built on. |
| 8 | Network: synthetic 3×3 SUMO grid first, then a Lahore OSM area (10–20 signals + hospital). All code must read the network from the SUMO files (network-agnostic). **Lahore area/hospital: open, to decide later.** |
| 9 | Video: train on UA-DETRAC; test also on 2–3 own Lahore clips. Labelling is AI pre-labelled + human-corrected; test labels must be human-verified; local clips can use manual line-crossing counts. |
| 10 | YOLO classes for FYP-1: car, bus, truck, motorcycle. Rickshaw is added in FYP-2 with labelled Lahore footage. |

## Phases and tasks

_To be written after the planning questions are finished._
