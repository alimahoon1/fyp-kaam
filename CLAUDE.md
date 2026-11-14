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
- **End of session (or after any meaningful step):** update `PLAN.md` status, add any new decision or result to `Manzil_FYP_Context.md` (section 50 or later), then **commit and push automatically**.
- **Keep the notes complete (Ibrahim's standing instruction, 14 Nov 2026).** Every session, laptop or cloud, and every change, however small, must leave these up to date in the same push as the code: (1) the task row and "Current stage" in `PLAN.md`; (2) one new line in the **Session log** table in `PLAN.md`; (3) a numbered subsection in `Manzil_FYP_Context.md` §50 for any decision, deviation from D2, or result (with real numbers and file paths); (4) the `README.md` of any `results/` folder that changed, and `README.md` if setup or run steps changed. A new session must be able to continue from these files alone. The team has authorised this, so there is no need to ask. Stage specific paths rather than `git add -A`, unless every change has been reviewed.
- Pull or rebase before pushing. Never force-push `main`.
- Only commit work that is real and verified. Never present planned, mocked or simulated work as implemented, and never invent results. D2 and the evaluators require a clear line between real, simulated, mocked, and planned.
- Large artifacts (datasets, videos, model weights over ~50 MB) do not go into git. Store them on Kaggle or in another external location, and record the link and checksum in the repo.
- Secrets (the Kaggle `kaggle.json` and any API keys) never go into the repo or into chat.
- The user prefers simple explanations, and questions asked one at a time.

## Environment notes

- Ibrahim's laptop: i7-8650U, 16 GB RAM, **no NVIDIA GPU**. GPU training runs on **Kaggle** through the Kaggle CLI (`kaggle kernels push/status/output`).
- Kaggle CLI on Ibrahim's laptop: version 2.2.5 installed for Python 3.13 (not in `.venv`, which is Python 3.10); run it as `py -3.13 -m kaggle ...`. The token is a new-style API token in `C:\Users\X1 Carbon\.kaggle\access_token` (never in the repo).
- SUMO comes from PyPI (`eclipse-sumo`, pinned in `pyproject.toml`); setup steps are in `README.md`. On Windows, use the repo's `.venv` (`.venv\Scripts\python`).

## Cloud sessions (claude.ai/code)

Ibrahim runs long coding tasks as Claude Code cloud sessions and follows them from the phone app. If you are a cloud session:

- The environment setup script is `bash scripts/cloud_setup.sh`. SUMO runs headless there; never depend on `sumo-gui`.
- Work autonomously through the task you were given, following `PLAN.md`. Ask the user only when blocked on a decision that is genuinely theirs, and ask one short question.
- The same commit rules apply. If you can push to `main`, do so (pull/rebase first). If the session only allows a `claude/...` branch, push there and open a PR. When the work is finished and `pytest` passes, **merge your own PR into `main`** (Ibrahim's standing instruction, 12 Nov 2026), then confirm `main` has the merge. If merging fails (conflict, no permission), leave the PR open and say so clearly in the final summary.
- Every figure, plot, sample image or table you show Ibrahim must also be saved in the repo under `results/<phase>/` (PNG for figures, CSV/JSON for numbers) with a `README.md` saying what it shows and how it was produced. Nothing shown in chat may exist only in chat. Files over ~50 MB (e.g. long videos) go to Kaggle or another external store, with the link and checksum recorded in the README; keep a short clip or a few frames in git.
- End with a short plain-language summary: what was done, test results, and anything that needs Ibrahim.
- Kaggle: the cloud environment may provide `KAGGLE_API_TOKEN` (Kaggle's new-style API token; needs Kaggle CLI 2.x, installed by the setup script). Check with `kaggle kernels list --mine`. Never print, log or commit their values. Heavy work (dataset download, YOLO training) runs *inside* Kaggle kernels with GPU and internet; the cloud session only pushes kernel code and pulls back small outputs (metrics, plots, weights under ~50 MB). If the variables are missing or kaggle.com is blocked by the network settings, say so in the summary and leave Kaggle tasks for the laptop.

## Repository map

- `archive/prototype_v0/`: earlier non-SUMO prototype, **archived and not to be built on** (team decision, 9 Nov 2026). The new system is built from scratch around SUMO.
- `Manzil_D2_Report/` + `FYPFast/`: LaTeX source of the reports (FAST template). Deliverable III builds on this.
- `presentation_output/`: final D2 slides.
- `FYP Sample Reports/`: reference reports from earlier batches.
