# Experiment store (W5)

SQLite database behind a repository interface (`ExperimentRepository` in `repository.py`), as
D2 Section 4.9 proposes. It holds nothing that is not in a run folder or a committed result
file, so it can be deleted and rebuilt at any time.

- **File:** `runs/manzil.sqlite` (git-ignored). The dashboard API creates it and, if it is
  empty, imports `results/` and the perception results on start-up. Finished live runs
  (`runs/live/*`) are imported automatically when they end.
- **Tables** (`schema.py`, schema version 1): `scenario`, `run`, `metric_sample`, `mission`,
  `route_version`, `priority_event`, `video_job`, `observation`, `artifact`, `meta`. They follow
  the D2 data dictionary. Not stored yet: `ControlDecision` rows, because the batch runs keep
  `applied_controls.csv` only locally; the live dashboard shows requested vs applied controls
  from the running safety filter (G03).
- **Rules enforced:** a run's configuration is never edited in place (a changed folder replaces
  the whole record); terminal reason required; status is `completed`, `stopped` or `failed`
  (failed runs are kept); route versions start at 1 and increase; an observation or artifact has
  exactly one owner (run or video job); every metric sample has name, version and unit; a
  missing value stays `NULL`, never 0.

## Commands

```bash
python -m manzil.store import                    # results/, runs/live/, tracking results
python -m manzil.store summary
python -m manzil.store list --study results/phase4/comparison --profile heavy
python -m manzil.store export --study results/phase4/comparison --profile heavy --out x.json
python -m manzil.store export --run <run_key> --out x.csv
```

`--db <file>` selects another database file.

## Export format (FR-19)

**JSON** (`format: "manzil.export"`, `format_version: 1`):

| key | meaning |
|---|---|
| `exported_at_utc`, `store_schema_version`, `run_count` | export metadata |
| `comparability_warnings` | FR-18 check of the exported selection (`code`, `level`, `message`) |
| `runs[]` | one object per run |
| `runs[].run_key` | run folder relative to the repository (unique key) |
| `runs[].run_id`, `study`, `source` | runner id, folder holding `runs/`, `batch` or `live` |
| `runs[].status`, `termination` | `completed` / `stopped` / `failed`, and the terminal reason |
| `runs[].versions` | git commit, dirty flag, SUMO version |
| `runs[].config`, `config_digest` | the full run configuration as written by the runner |
| `runs[].metrics` | `{name: {value, unit, metric_version, interval_s: [start, end]}}` |
| `runs[].other_results` | non-numeric results (e.g. safety interventions per kind, closures) |
| `runs[].missions[]` | ambulance missions with `route_versions` and `priority_events` |
| `runs[].files[]` | source files with sha256 and provenance |

**CSV:** one row per run. Identity columns `run_key, study, source, status, termination,
scenario, network_id, profile, seed, controller, label, arm, warmup_s, measure_s,
metric_version, config_digest, git_commit`, then one column per metric named
`<metric>[<unit>]`. An empty cell is a missing value.

## Comparison (FR-18, `analytics.py`)

Runs are grouped (by experiment arm by default: the run label, else `controller[:plan]`, the
same names `manzil.experiments.batch` uses). Per metric and group: n, mean, sample SD and the
95 % t interval; paired differences against the reference group (fixed-time if present) on
runs matched by (profile, seed). Warnings: different scenario, network, warm-up, measurement
window or metric version (error); mixed demand profiles, unmatched seeds, excluded
(not completed) runs, runs without a metric version (warning). On the committed Phase 2 runs it
reproduces `results/phase2/comparison/summary.json` exactly (`tests/test_w5_store.py`).
