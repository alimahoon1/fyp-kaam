# Manzil: Intelligent Traffic & Emergency Routing

Final Year Project F26-104, FAST-NUCES Lahore, supervised by Miss Umm-e-Ammarah.

Manzil is a SUMO-based research prototype. It covers:
- vision-based traffic observation (YOLO + tracking on recorded video);
- comparative signal control (fixed-time, rule-adaptive, and DQN);
- congestion-aware ambulance routing with a moving green corridor;
- a React/FastAPI dashboard for running and comparing experiments.

## Where things are

| Path | Contents |
|---|---|
| `PLAN.md` | Phases, tasks, and status |
| `CLAUDE.md` | Working rules for everyone (and their Claude sessions) |
| `Manzil_FYP_Context.md` | Full project context; sections 49–50 hold the condensed spec and planning decisions |
| `F26-104_Project-Proposal.pdf`, `F26-104_Deliverable-2_Report.pdf` | Approved proposal and Deliverable 2 report |
| `Manzil_D2_Report/`, `FYPFast/` | LaTeX source of the reports |
| `archive/prototype_v0/` | Earlier non-SUMO prototype, kept for reference only; not part of the current system |
| `manzil/` | The new Python package (being built from scratch around SUMO) |
| `manzil/scenarios/` | Grid builder (`grid.py`), seeded demand profiles (`demand.py`), gridlock check (`check.py`) |
| `scenarios/grid3x3/` | Synthetic 3×3 SUMO network and its README (profiles, calibration, results) |
| `results/` | Small result summaries kept in git |
| `tests/` | Automated tests (`pytest`) |
| `scripts/cloud_setup.sh` | Setup script for Linux and Claude Code cloud sessions |

## Setup

SUMO is installed from PyPI (`eclipse-sumo`, pinned to 1.28.0 in `pyproject.toml`), so every machine gets the same version from one command. There is no need for the separate SUMO Windows installer.

### Windows (team laptops)

Requires Python 3.10 or newer (`py -0` lists installed versions). In the repo folder:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

Then set `SUMO_HOME` once (replace the path with your own repo location) and reopen the terminal:

```powershell
.venv\Scripts\python -c "import sumo; print(sumo.SUMO_HOME)"
setx SUMO_HOME "<path printed above>"
```

The Manzil code finds SUMO even without `SUMO_HOME`, but SUMO's own tools expect it. `sumo-gui` is at `.venv\Scripts\sumo-gui.exe`.

### Linux, macOS and Claude Code cloud sessions

```bash
bash scripts/cloud_setup.sh
```

In a claude.ai/code environment, use `cd fyp-kaam && bash scripts/cloud_setup.sh` as the setup script (it runs from the folder above the repo) and allow network access to package registries. Cloud sessions run SUMO headless (no `sumo-gui`).

### Checks

- `pytest` passes (includes `tests/test_setup.py`, which runs `sumo` and `netgenerate`)
- `ruff check manzil tests` and `ruff format --check manzil tests` pass
