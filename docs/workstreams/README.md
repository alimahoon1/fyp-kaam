# FYP-II parallel workstreams

FYP-II work is split into independent **workstreams** (W1–W6) so several Claude agents or cloud sessions can work at the same time without merge conflicts. PLAN.md (Phase 7) lists their status. This file is the contract every workstream follows.

## The three rules that prevent conflicts

1. **File ownership.** A workstream edits only the paths it owns (table below). Need a change in someone else's path? Write the request in your own notes file under "Requests to other workstreams" and work around it; do not edit the file.
2. **Shared files belong to the coordinator only:** `PLAN.md`, `Manzil_FYP_Context.md`, `CLAUDE.md`, root `README.md`, `pyproject.toml`, `scripts/cloud_setup.sh`, `Manzil_D2_Report/`, `.gitignore`. Workers put everything the coordinator must copy into those files (status, decisions, results, new dependencies) into their own `docs/workstreams/W<n>.md`.
3. **New files over edits.** Tests go in new files (`tests/test_w<n>_*.py`); results go in `results/fyp2/<workstream>/`; new code goes in new modules where possible.

## Ownership

| ID | Workstream | Owns (may edit) | Depends on |
|---|---|---|---|
| W1 | Lahore road network | `scenarios/lahore/`, `manzil/scenarios/osm.py` (new), `manzil/sim/network.py`, `tests/test_w1_*.py`, `results/fyp2/lahore_network/`, `docs/workstreams/W1.md` | area + hospital decision (Ibrahim) |
| W2 | Lahore video, labels, rickshaw/van classes | `kaggle/lahore_*/`, `data/lahore_video/` (manifests only, no video), `manzil/perception/`, `tests/test_w2_*.py`, `results/fyp2/vision_lahore/`, `docs/workstreams/W2.md` | — |
| W3 | Full evaluation protocol + DQN robustness (on the grid first) | `manzil/experiments/protocol*.py` (new), `manzil/control/dqn.py`, `manzil/control/rl_env.py`, `manzil/scenarios/demand.py`, `models/dqn/`, `tests/test_w3_*.py`, `results/fyp2/protocol/`, `docs/workstreams/W3.md` | — |
| W4 | Corridor completion (downstream check, recovery compensation, sublane give-way) | `manzil/corridor/`, `manzil/control/safety.py`, `manzil/sim/adapter.py`, `manzil/experiments/emergency*.py`, `tests/test_w4_*.py`, `results/fyp2/corridor/`, `docs/workstreams/W4.md` | — |
| W5 | Dashboard v2 (G01–G05) + database + FR-02 pause, FR-16 warnings, FR-19 export | `dashboard/`, `manzil/api/`, `manzil/store/` (new), `tests/test_w5_*.py`, `results/fyp2/dashboard/`, `docs/workstreams/W5.md` | — |
| W6 | Video-to-SUMO study (second wave) | `manzil/experiments/video_sim*.py` (new), `tests/test_w6_*.py`, `results/fyp2/video_sim/`, `docs/workstreams/W6.md` | W1 + W2 merged |

Existing tests stay owned by the workstream that owns the code they test; any workstream may *run* all tests.

## Branches and merging

- One branch per workstream: `claude/w<n>-<short-name>` (or a git worktree created by the coordinator).
- Before asking to merge: `git fetch && git rebase origin/main`, then `ruff check .` and the **full** `pytest` must pass.
- Merge **one branch at a time** into `main`; after each merge, run the full `pytest` on `main` before merging the next. The coordinator (or, for separate cloud sessions, each session itself under the standing merge rule) merges.
- A conflict can then only appear in a shared file, which only the coordinator edits.
- Never force-push `main`.

## Notes file (`docs/workstreams/W<n>.md`)

Every workstream keeps exactly this structure, updated with each push:

```
# W<n> <name>
Status: todo | in progress (who, where) | blocked (why) | done
## Done so far        (what is real and verified, with file paths and real numbers)
## Decisions          (and deviations from the report's design, with reasons)
## For the coordinator (lines to copy into PLAN.md, context §50, README, pyproject)
## Requests to other workstreams
## Open questions for Ibrahim (one at a time)
```

## Honesty rules that apply to every workstream

- Only real, verified results; label anything simulated, synthetic, model-labelled or planned as such.
- Large files (videos, datasets, weights over ~50 MB) never go into git: Kaggle (private) + link + sha256 in the notes.
- No secrets in the repo or in logs.

## Rules specific to W2 (video and labels)

- **Sources:** only clips whose licence allows reuse for research (Creative Commons with attribution, Pexels or Pixabay licence, Wikimedia Commons) or footage the team filmed itself. For every clip record URL, uploader, licence, download date, duration, resolution, location and sha256 in `data/lahore_video/SOURCES.md`. Download inside a Kaggle kernel (it has internet) so the video never passes through the laptop or the cloud session, and store the clips as a **private** Kaggle dataset. Do not use clips whose licence forbids reuse or download. If too few suitable clips exist, say so and ask the team to film (PLAN open item).
- **Privacy:** do not put frames with readable number plates or recognisable faces into the repo or report without blurring.
- **Labelling:** pre-label on Kaggle with the fine-tuned YOLO11s plus a stronger or open-vocabulary detector for rickshaws and vans; Claude then reviews rendered frames (accept, reject, fix class, add clearly missing boxes) and writes the corrected labels. Record every label set as **"model-assisted, Claude-reviewed"**. Keep a test subset (e.g. 100–150 frames from clips not used for training) that a **team member checks** before it is used as ground truth; until then, test numbers on it are reported as preliminary.
