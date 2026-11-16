"""FR-19 export: run configuration + metrics in a documented machine-readable format.

Two formats (described in ``manzil/store/README.md``):

- **JSON** (``manzil.export`` version 1): one document with the export time, the store schema
  version, the comparability warnings of the selection (FR-18), and per run its key, status,
  termination, full configuration, versions, metrics (value, unit, metric version, interval)
  and missions (route versions, priority events).
- **CSV**: one row per run: identity columns, then one column per metric named
  ``<metric>[<unit>]``. Empty cell = missing value (never 0).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from manzil.store.analytics import comparability
from manzil.store.repository import ExperimentRepository
from manzil.store.schema import SCHEMA_VERSION

EXPORT_FORMAT = "manzil.export"
EXPORT_VERSION = 1
CSV_ID_COLUMNS = ("run_key", "study", "source", "status", "termination", "scenario",
                  "network_id", "profile", "seed", "controller", "label", "arm", "warmup_s",
                  "measure_s", "metric_version", "config_digest", "git_commit")  # fmt: skip


def build_export(repo: ExperimentRepository, run_keys: list[str], group_by="arm") -> dict:
    runs = []
    for k in run_keys:
        r = repo.get_run(k)
        if r is None:
            raise KeyError(f"unknown run {k!r}")
        runs.append(r)
    return {
        "format": EXPORT_FORMAT,
        "format_version": EXPORT_VERSION,
        "store_schema_version": SCHEMA_VERSION,
        "exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_count": len(runs),
        "comparability_warnings": comparability(runs, group_by) if runs else [],
        "runs": [
            {
                "run_key": r["run_key"], "run_id": r["run_id"], "study": r["study"],
                "source": r["source"], "status": r["status"], "termination": r["termination"],
                "created_at": r["created_at"],
                "versions": {"git_commit": r["git_commit"], "git_dirty": r["git_dirty"],
                             "sumo": r["sumo_version"]},
                "config_digest": r["config_digest"],
                "config": r["config"],
                "metrics": r["metrics"],
                "other_results": r["extra"],
                "missions": r["missions"],
                "files": r["artifacts"],
            }
            for r in runs
        ],
    }  # fmt: skip


def to_csv(repo: ExperimentRepository, run_keys: list[str]) -> str:
    index = {r["run_key"]: r for r in repo.list_runs()}
    missing = [k for k in run_keys if k not in index]
    if missing:
        raise KeyError(f"unknown runs: {missing[:5]}")
    values = repo.metrics(run_keys)
    cols: dict[str, str] = {}
    for k in run_keys:
        for m, v in values[k].items():
            cols.setdefault(m, v["unit"])
    names = sorted(cols)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([*CSV_ID_COLUMNS, *(f"{m}[{cols[m]}]" for m in names)])
    for k in run_keys:
        r = index[k]
        row = ["" if r.get(c) is None else r.get(c) for c in CSV_ID_COLUMNS]
        for m in names:
            v = values[k].get(m, {}).get("value")
            row.append("" if v is None else repr(v) if isinstance(v, float) else v)
        w.writerow(row)
    return buf.getvalue()


def write_export(repo: ExperimentRepository, run_keys: list[str], out: Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        out.write_text(to_csv(repo, run_keys), encoding="utf-8")
    else:
        doc = build_export(repo, run_keys)
        out.write_text(json.dumps(doc, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return out
