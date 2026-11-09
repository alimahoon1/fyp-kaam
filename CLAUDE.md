# Manzil FYP — instructions for Claude

**Manzil: Intelligent Traffic & Emergency Routing.** FYP group F26-104, FAST-NUCES Lahore. Supervisor: Miss Umm-e-Ammarah.
Team: Mohammad Ibrahim Salman (23L-0723), Muhammad Ali Mahoon (23L-0531), Muzammil Ahmed Bhatti (23L-0688).

Several team members work on this repo from **different machines, each with their own Claude session**. The repo is the only shared memory, so everything that matters has to be written here and pushed.

## Read first, every session

1. `PLAN.md`: phases, tasks, who is working on what, and status.
2. `Manzil_FYP_Context.md`, **sections 49 and 50**: the condensed spec (proposal + Deliverable 2), the gap analysis, the Deliverable III requirements, and every planning decision the team has made. Earlier sections are history and brainstorming. Where they conflict, sections 49–50 and the PDFs win.
3. Source-of-truth documents: `F26-104_Project-Proposal.pdf` and `F26-104_Deliverable-2_Report.pdf`. Do not contradict them without recording the deviation and the reason.

## Working rules

- **Start of session:** run `git pull` before changing anything.
- **Claim a task:** in `PLAN.md`, set the task to `in progress (Name)` and push that change before starting long work, so two people don't take the same task.
- **End of session (or after any meaningful step):** update `PLAN.md` status, add any new decision or result to `Manzil_FYP_Context.md` (section 50 or later), then **commit and push automatically**. The team has authorised this, so there is no need to ask. Stage specific paths rather than `git add -A`, unless every change has been reviewed.
- Pull or rebase before pushing. Never force-push `main`.
- Only commit work that is real and verified. Never present planned, mocked or simulated work as implemented, and never invent results. D2 and the evaluators require a clear line between real, simulated, mocked, and planned.
- Large artifacts (datasets, videos, model weights over ~50 MB) do not go into git. Store them on Kaggle or in another external location, and record the link and checksum in the repo.
- Secrets (the Kaggle `kaggle.json` and any API keys) never go into the repo or into chat.
- The user prefers simple explanations, and questions asked one at a time.

## Environment notes

- Ibrahim's laptop: i7-8650U, 16 GB RAM, **no NVIDIA GPU**. GPU training runs on **Kaggle** through the Kaggle CLI (`kaggle kernels push/status/output`).
- Each machine needs SUMO installed with `SUMO_HOME` set. Check `PLAN.md` for setup status.

## Repository map

- `prototype/`: earlier non-SUMO prototype (FastAPI + React). See `README.md` and `docs/DEVIATIONS.md`.
- `Manzil_D2_Report/` + `FYPFast/`: LaTeX source of the reports (FAST template). Deliverable III builds on this.
- `presentation_output/`: final D2 slides.
- `FYP Sample Reports/`: reference reports from earlier batches.
