# Prompts for running the FYP-II workstreams in parallel

Two ways to run the work. Both follow `docs/workstreams/README.md` (ownership, branches, merge order).

- **Option A, one coordinator session that spawns agents.** One Claude Code session reads the plan and starts one sub-agent per workstream, each in its own git worktree. Good for a burst of work you can watch in one place. Everything stops if that one session stops.
- **Option B, one cloud session per workstream (recommended for long work).** Start a separate claude.ai/code session for each workstream with the per-workstream prompt below. Each runs on its own branch and merges its own PR after rebasing and passing the full tests. Sessions keep running independently and you can follow each from the phone.

Start **W3, W4 and W5 immediately** (no dependencies), **W2** as soon as you can (independent but long), **W1** once the Lahore area is decided, and **W6** only after W1 and W2 are merged.

---

## Option A: coordinator prompt

```
You are the coordinator for Manzil FYP-II (repo fyp-kaam). Read CLAUDE.md, PLAN.md (Phase 7),
docs/workstreams/README.md and Manzil_FYP_Context.md sections 49-50 first, and git pull.

1. In PLAN.md Phase 7, mark W2, W3, W4 and W5 as "in progress (coordinator agents)" and push.
   W1 waits for Ibrahim's choice of Lahore area and hospital: ask him that one question now.
   W6 waits for W1 and W2.
2. Spawn one sub-agent per started workstream with the Agent tool, each with isolation
   "worktree" and its own branch claude/w<n>-<name>. Give each the matching per-workstream
   prompt from docs/workstreams/PROMPTS.md (Option B section) unchanged. Run them in parallel.
3. While they run, do not edit any file a workstream owns. You alone edit the shared files
   (PLAN.md, Manzil_FYP_Context.md, CLAUDE.md, README.md, pyproject.toml, scripts/cloud_setup.sh,
   .gitignore, Manzil_D2_Report/).
4. When an agent finishes: check its docs/workstreams/W<n>.md, review its diff (it must touch
   only owned paths), rebase its branch on main, run ruff and the full pytest, then merge it.
   Merge one branch at a time and run the full pytest on main after each merge. Then copy its
   "For the coordinator" lines into PLAN.md (task row, Session log line), a new numbered
   subsection in context section 50, README/pyproject if needed, and push.
5. If a merge conflicts outside shared files, stop and report which ownership rule was broken.
6. When W1 and W2 are merged, start W6 the same way.
7. End with a short plain-language summary per workstream: what is real and verified, test
   results, merged or not, and every open question for Ibrahim (one at a time).
```

---

## Option B: per-workstream prompts

Use this header, then append the workstream block.

```
You are working on workstream W<n> of Manzil FYP-II (repo fyp-kaam). Read CLAUDE.md,
docs/workstreams/README.md, PLAN.md (Phase 7) and Manzil_FYP_Context.md sections 49-50 first,
git pull, and work on branch claude/w<n>-<name>. Edit ONLY the paths W<n> owns in
docs/workstreams/README.md. Do not edit PLAN.md, the context file, CLAUDE.md, README.md,
pyproject.toml or the report; put everything for them into docs/workstreams/W<n>.md under
"For the coordinator". Only real, verified results. Push small commits. When done: rebase on
origin/main, ruff and the full pytest must pass, then merge your PR into main (standing
instruction) and confirm main has it; if merging fails, leave the PR open and say why.
Ask Ibrahim only blocking questions, one at a time. End with a plain-language summary.
```

### W1 Lahore road network
```
Goal: a validated SUMO network of a Lahore area with 10-20 signalised junctions that contains
a hospital, built from OpenStreetMap (attribution per OSM licence). If Ibrahim has not chosen
the area yet, propose 2-3 candidate areas (bounding box, hospital, number of signals, why) and
ask him to choose. Record bounding box, extraction date, source checksum and the netconvert
command. Clean lanes, turns, traffic-light programs and joined signals (network.py currently
raises NotImplementedError for joined TLS; implement it). Validate with the existing network
reader, conflict rule, safety monitor and a route check from every entry to the hospital.
Add a seeded demand generator setup for the new network (in scenarios/lahore/). Done when: the
network loads headless, all existing controllers run on it with 0 safety violations, tests
pass, and results/fyp2/lahore_network/README.md documents it with a map figure.
```

### W2 Lahore video, labels, rickshaw and van classes
```
Goal: a small, legally usable Lahore traffic-video set, labels for car, bus, truck,
motorcycle, rickshaw and van, a detector fine-tuned for those classes, and count error on
Lahore clips. Follow the W2 rules in docs/workstreams/README.md exactly (licences, SOURCES.md,
download inside Kaggle, private Kaggle dataset, privacy, "model-assisted, Claude-reviewed"
labels, a team-checked test subset). Search the web for suitable clips; if fewer than about
10 usable clips exist, report that and ask Ibrahim whether the team will film. Pre-label on
Kaggle GPU, review frames yourself, fine-tune on Kaggle, and evaluate detection and counting
as in results/vision/. Done when: SOURCES.md is complete, labels and weights are on Kaggle
with sha256 recorded, results/fyp2/vision_lahore/README.md reports real numbers with their
label status, and tests for any new code pass.
```

### W3 Full evaluation protocol and DQN robustness
```
Goal: the full protocol of report section 5.8 on the synthetic grid, ready to rerun on Lahore:
10 matched evaluation seeds, held-out demand patterns not used in training (e.g. new uneven
directions and time-varying demand), DQN trained with 3 training seeds to measure training
variance, and a fairness variant (reward term or tighter max-red) compared with the current
policy. Keep the existing results and models unchanged; write new ones next to them. Rerun the
corridor v2 experiment on NEW seeds (not 0-4) to confirm the development-stage estimate.
Done when: results/fyp2/protocol/README.md has tables with CIs and seeds-better counts, the
protocol runner works for any network, and tests pass.
```

### W4 Corridor completion
```
Goal: finish Algorithm 2 as designed in report section 5.6: the downstream-capacity check
before activation, a bounded compensation plan during recovery, and ordinary vehicles giving
way with SUMO's sublane model (the blue-light device without it caused gridlocks; context
50.15). The ambulance must still never cross a red light and the safety monitor must report
0 violations. Compare each addition against corridor v2 on fixed-time and DQN background
control, medium and heavy demand, on seeds that are not 0-4; keep only what helps without
measurable ordinary-traffic cost. Done when: results/fyp2/corridor/README.md has the
comparison, decisions are recorded in W4.md, and tests pass.
```

### W5 Dashboard v2 and database
```
Goal: the five screens of report section 4.8 (G01 configuration, G02 overview, G03 perception
detail, G04 emergency dispatch, G05 comparative analytics) in the existing React app, a
SQLite database behind a repository interface in manzil/store/ that imports existing run
folders, pause and resume (FR-02), visible stale, invalid, disconnected and fallback states
(FR-16), and an export command (FR-19). Nothing on screen may be mocked; G03 shows prepared
perception results with their provenance. Done when: API tests for the new endpoints pass,
screenshots of each screen are in results/fyp2/dashboard/ with a README, and the old dashboard
workflow still works.
```

### W6 Video-to-SUMO study (after W1 and W2 are merged)
```
Goal: feed counts and queue estimates from Lahore video into a matching simulated approach on
the Lahore network and measure how observation error changes controller decisions and
outcomes compared with exact SUMO state. Done when: results/fyp2/video_sim/README.md reports
real numbers and the limits of the camera-to-lane mapping, and tests pass.
```
