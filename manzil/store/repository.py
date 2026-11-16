"""Repository interface of the experiment store and its SQLite implementation (W5).

D2 proposes a relational database *behind a repository interface*, so the dashboard and the
export command depend only on ``ExperimentRepository``; ``SqliteRepository`` (Python's built-in
``sqlite3``, one file, no server) is the implementation used in FYP-II. A PostgreSQL version
would implement the same methods.

The records are plain dataclasses built by ``manzil.store.importer`` from run folders, so the
store never holds anything that is not in a run folder or a committed result file.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from manzil.store.schema import DDL, SCHEMA_VERSION


@dataclass
class MetricValue:
    name: str
    value: float | None
    unit: str
    metric_version: int | None = None
    interval_start_s: float | None = None
    interval_end_s: float | None = None


@dataclass
class RouteVersionRecord:
    version: int
    edge_ids: list[str]
    trigger: str
    cost_s: float | None = None
    snapshot_step: int | None = None
    compute_ms: float | None = None


@dataclass
class PriorityEventRecord:
    intersection_id: str
    state: str
    time_s: float | None = None
    step: int | None = None
    route_version: int | None = None
    reason: str | None = None


@dataclass
class MissionRecord:
    index: int
    vehicle_id: str
    origin: str | None
    destination: str | None
    status: str | None
    corridor: bool | None
    routing: str | None
    metrics: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    route_versions: list[RouteVersionRecord] = field(default_factory=list)
    priority_events: list[PriorityEventRecord] = field(default_factory=list)


@dataclass
class RunRecord:
    run_key: str
    run_id: str
    study: str
    source: str  # "batch" | "live"
    status: str  # "completed" | "stopped" | "failed"
    termination: str
    config: dict
    content_sha256: str
    scenario: str | None = None
    network_id: str | None = None
    demand_generator: str | None = None
    profile: str | None = None
    seed: int | None = None
    controller: str | None = None
    label: str | None = None
    arm: str | None = None
    warmup_s: float | None = None
    measure_s: float | None = None
    metric_version: int | None = None
    config_digest: str | None = None
    created_at: str | None = None
    git_commit: str | None = None
    git_dirty: bool | None = None
    sumo_version: str | None = None
    wall_time_s: float | None = None
    metrics: list[MetricValue] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    missions: list[MissionRecord] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)  # {type, uri, sha256, provenance}


@dataclass
class ObservationRecord:
    entity_id: str
    observed_at_s: float
    name: str
    value: float | None
    unit: str
    reference: float | None = None
    source_mode: str = "video"


@dataclass
class VideoJobRecord:
    job_id: str
    dataset: str
    clip: str
    model_version: str
    status: str
    label_status: str
    model_sha256: str | None = None
    clip_checksum: str | None = None
    tracker: str | None = None
    frames: int | None = None
    seconds: float | None = None
    fps: float | None = None
    produced_by: str | None = None
    summary: dict = field(default_factory=dict)
    observations: list[ObservationRecord] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)


class ExperimentRepository(Protocol):
    """What the dashboard API and the export command need from the store."""

    def save_run(self, run: RunRecord) -> str: ...  # "added" | "updated" | "unchanged"
    def list_runs(self, **filters: Any) -> list[dict]: ...
    def get_run(self, run_key: str) -> dict | None: ...
    def metrics(self, run_keys: list[str]) -> dict[str, dict[str, dict]]: ...
    def missions(self, run_key: str) -> list[dict]: ...
    def save_video_job(self, job: VideoJobRecord) -> str: ...
    def list_video_jobs(self) -> list[dict]: ...
    def get_video_job(self, job_id: str) -> dict | None: ...
    def observations(self, job_id: str, name: str | None = None) -> list[dict]: ...
    def summary(self) -> dict: ...


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, allow_nan=False, default=str)


class SqliteRepository:
    """``ExperimentRepository`` on one SQLite file (``":memory:"`` for tests)."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # The API serves requests from several threads; one connection guarded by a lock.
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock, self._db:
            self._db.execute("PRAGMA foreign_keys = ON")
            self._db.executescript(DDL)
            row = self._db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row is None:
                self._db.execute("INSERT INTO meta VALUES ('schema_version', ?)",
                                 (str(SCHEMA_VERSION),))  # fmt: skip
            elif int(row[0]) != SCHEMA_VERSION:
                raise RuntimeError(
                    f"store {self.path} has schema {row[0]}, this code expects {SCHEMA_VERSION};"
                    " delete the file and import again"
                )

    def close(self) -> None:
        self._db.close()

    # ----- runs ------------------------------------------------------------------------------
    def save_run(self, run: RunRecord) -> str:
        for m in run.missions:
            versions = [rv.version for rv in m.route_versions]
            if versions != sorted(set(versions)) or (versions and versions[0] < 1):
                raise ValueError(f"{run.run_key}: route versions not increasing: {versions}")
        with self._lock, self._db:
            old = self._db.execute(
                "SELECT content_sha256 FROM run WHERE run_key=?", (run.run_key,)
            ).fetchone()
            if old is not None and old[0] == run.content_sha256:
                return "unchanged"
            if old is not None:  # completed configs are immutable: replace the whole record
                self._db.execute("DELETE FROM run WHERE run_key=?", (run.run_key,))
            scenario_id = None
            if run.scenario and run.profile:
                scenario_id = f"{run.scenario}/{run.profile}"
                self._db.execute(
                    "INSERT OR IGNORE INTO scenario VALUES (?,?,?,?,?)",
                    (scenario_id, run.scenario, run.profile, run.network_id,
                     run.demand_generator),
                )  # fmt: skip
            self._db.execute(
                """INSERT INTO run (run_key, run_id, study, source, scenario_id, scenario,
                   network_id, profile, seed, controller, label, arm, warmup_s, measure_s,
                   metric_version, config_digest, status, termination, created_at, git_commit,
                   git_dirty, sumo_version, wall_time_s, has_mission, config_json, extra_json,
                   content_sha256, imported_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run.run_key, run.run_id, run.study, run.source, scenario_id, run.scenario,
                    run.network_id, run.profile, run.seed, run.controller, run.label, run.arm,
                    run.warmup_s, run.measure_s, run.metric_version, run.config_digest,
                    run.status, run.termination, run.created_at, run.git_commit,
                    None if run.git_dirty is None else int(run.git_dirty), run.sumo_version,
                    run.wall_time_s, int(bool(run.missions)), _dumps(run.config),
                    _dumps(run.extra), run.content_sha256, _now(),
                ),
            )  # fmt: skip
            self._db.executemany(
                "INSERT INTO metric_sample VALUES (?,?,?,?,?,?,?)",
                [
                    (run.run_key, m.name, m.metric_version, m.value, m.unit,
                     m.interval_start_s, m.interval_end_s)
                    for m in run.metrics
                ],
            )  # fmt: skip
            for m in run.missions:
                mid = f"{run.run_key}#{m.index}"
                self._db.execute(
                    "INSERT INTO mission VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (mid, run.run_key, m.vehicle_id, m.origin, m.destination, m.status,
                     None if m.corridor is None else int(m.corridor), m.routing,
                     _dumps(m.metrics), _dumps(m.config)),
                )  # fmt: skip
                self._db.executemany(
                    "INSERT INTO route_version VALUES (?,?,?,?,?,?,?)",
                    [
                        (mid, rv.version, _dumps(rv.edge_ids), rv.cost_s, rv.trigger,
                         rv.snapshot_step, rv.compute_ms)
                        for rv in m.route_versions
                    ],
                )  # fmt: skip
                self._db.executemany(
                    "INSERT INTO priority_event (mission_id, route_version, intersection_id,"
                    " state, time_s, step, reason) VALUES (?,?,?,?,?,?,?)",
                    [
                        (mid, e.route_version, e.intersection_id, e.state, e.time_s, e.step,
                         e.reason)
                        for e in m.priority_events
                    ],
                )  # fmt: skip
            self._db.executemany(
                "INSERT INTO artifact (run_key, job_id, type, uri, sha256, provenance)"
                " VALUES (?,NULL,?,?,?,?)",
                [(run.run_key, a["type"], a["uri"], a.get("sha256"), a["provenance"])
                 for a in run.artifacts],
            )  # fmt: skip
            return "updated" if old is not None else "added"

    _RUN_COLS = (
        "run_key, run_id, study, source, scenario, network_id, profile, seed, controller, label,"
        " arm, warmup_s, measure_s, metric_version, config_digest, status, termination, created_at,"
        " git_commit, git_dirty, sumo_version, wall_time_s, has_mission"
    )
    _FILTERS = (
        "study",
        "source",
        "controller",
        "profile",
        "status",
        "label",
        "arm",
        "scenario",
        "seed",
    )

    def list_runs(self, **filters: Any) -> list[dict]:
        where, args = [], []
        for k, v in filters.items():
            if v is None or v == "":
                continue
            if k not in self._FILTERS:
                raise ValueError(f"unknown filter {k!r}")
            where.append(f"{k} = ?")
            args.append(v)
        sql = f"SELECT {self._RUN_COLS} FROM run"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY study, run_key"
        with self._lock:
            return [_row(r) for r in self._db.execute(sql, args)]

    def get_run(self, run_key: str) -> dict | None:
        with self._lock:
            r = self._db.execute(
                f"SELECT {self._RUN_COLS}, config_json, extra_json, content_sha256, imported_at"
                " FROM run WHERE run_key=?",
                (run_key,),
            ).fetchone()
            if r is None:
                return None
            out = _row(r)
            out["config"] = json.loads(out.pop("config_json"))
            out["extra"] = json.loads(out.pop("extra_json"))
            out["metrics"] = self.metrics([run_key]).get(run_key, {})
            out["missions"] = self.missions(run_key)
            out["artifacts"] = [
                _row(a)
                for a in self._db.execute(
                    "SELECT type, uri, sha256, provenance FROM artifact WHERE run_key=?",
                    (run_key,),
                )
            ]
            return out

    def metrics(self, run_keys: list[str]) -> dict[str, dict[str, dict]]:
        out: dict[str, dict[str, dict]] = {k: {} for k in run_keys}
        with self._lock:
            for i in range(0, len(run_keys), 500):
                chunk = run_keys[i : i + 500]
                q = ",".join("?" * len(chunk))
                for r in self._db.execute(
                    "SELECT run_key, metric_name, metric_version, value, unit, interval_start_s,"
                    f" interval_end_s FROM metric_sample WHERE run_key IN ({q})",
                    chunk,
                ):
                    out[r["run_key"]][r["metric_name"]] = {
                        "value": r["value"],
                        "unit": r["unit"],
                        "metric_version": r["metric_version"],
                        "interval_s": [r["interval_start_s"], r["interval_end_s"]],
                    }
        return out

    def missions(self, run_key: str) -> list[dict]:
        with self._lock:
            out = []
            for m in self._db.execute(
                "SELECT * FROM mission WHERE run_key=? ORDER BY mission_id", (run_key,)
            ):
                d = _row(m)
                d["metrics"] = json.loads(d.pop("metrics_json"))
                d["config"] = json.loads(d.pop("config_json"))
                d["route_versions"] = [
                    {**_row(rv), "edge_list": json.loads(rv["edge_list"])}
                    for rv in self._db.execute(
                        "SELECT version, edge_list, cost_s, trigger, snapshot_step, compute_ms"
                        " FROM route_version WHERE mission_id=? ORDER BY version",
                        (d["mission_id"],),
                    )
                ]
                d["priority_events"] = [
                    _row(e)
                    for e in self._db.execute(
                        "SELECT route_version, intersection_id, state, time_s, step, reason"
                        " FROM priority_event WHERE mission_id=? ORDER BY id",
                        (d["mission_id"],),
                    )
                ]
                out.append(d)
            return out

    # ----- perception ------------------------------------------------------------------------
    def save_video_job(self, job: VideoJobRecord) -> str:
        with self._lock, self._db:
            old = self._db.execute(
                "SELECT summary_json FROM video_job WHERE job_id=?", (job.job_id,)
            ).fetchone()
            if old is not None and old[0] == _dumps(job.summary):
                return "unchanged"
            if old is not None:
                self._db.execute("DELETE FROM video_job WHERE job_id=?", (job.job_id,))
            self._db.execute(
                "INSERT INTO video_job VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job.job_id, job.dataset, job.clip, job.clip_checksum, job.model_version,
                 job.model_sha256, job.tracker, job.status, job.frames, job.seconds, job.fps,
                 job.produced_by, job.label_status, _dumps(job.summary), _now()),
            )  # fmt: skip
            self._db.executemany(
                "INSERT INTO observation (job_id, run_key, source_mode, entity_id,"
                " observed_at_s, name, value, reference, unit) VALUES (?,NULL,?,?,?,?,?,?,?)",
                [
                    (job.job_id, o.source_mode, o.entity_id, o.observed_at_s, o.name, o.value,
                     o.reference, o.unit)
                    for o in job.observations
                ],
            )  # fmt: skip
            self._db.executemany(
                "INSERT INTO artifact (run_key, job_id, type, uri, sha256, provenance)"
                " VALUES (NULL,?,?,?,?,?)",
                [(job.job_id, a["type"], a["uri"], a.get("sha256"), a["provenance"])
                 for a in job.artifacts],
            )  # fmt: skip
            return "updated" if old is not None else "added"

    _JOB_COLS = (
        "job_id, dataset, clip, clip_checksum, model_version, model_sha256, tracker, status,"
        " frames, seconds, fps, produced_by, label_status, imported_at"
    )

    def list_video_jobs(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                f"SELECT {self._JOB_COLS}, summary_json FROM video_job ORDER BY job_id"
            )
            out = []
            for r in rows:
                d = _row(r)
                d["summary"] = json.loads(d.pop("summary_json"))
                out.append(d)
            return out

    def get_video_job(self, job_id: str) -> dict | None:
        with self._lock:
            r = self._db.execute(
                f"SELECT {self._JOB_COLS}, summary_json FROM video_job WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if r is None:
                return None
            d = _row(r)
            d["summary"] = json.loads(d.pop("summary_json"))
            d["artifacts"] = [
                _row(a)
                for a in self._db.execute(
                    "SELECT type, uri, sha256, provenance FROM artifact WHERE job_id=?",
                    (job_id,),
                )
            ]
            d["observation_names"] = [
                {"name": n, "unit": u, "count": c}
                for n, u, c in self._db.execute(
                    "SELECT name, unit, COUNT(*) FROM observation WHERE job_id=?"
                    " GROUP BY name, unit ORDER BY name",
                    (job_id,),
                )
            ]
            return d

    def observations(self, job_id: str, name: str | None = None) -> list[dict]:
        sql = ("SELECT source_mode, entity_id, observed_at_s, name, value, reference, unit"
               " FROM observation WHERE job_id=?")  # fmt: skip
        args: list = [job_id]
        if name:
            sql += " AND name=?"
            args.append(name)
        sql += " ORDER BY name, observed_at_s"
        with self._lock:
            return [_row(r) for r in self._db.execute(sql, args)]

    # ----- overview --------------------------------------------------------------------------
    def summary(self) -> dict:
        with self._lock:
            one = lambda sql: self._db.execute(sql).fetchone()[0]  # noqa: E731
            studies = [
                _row(r)
                for r in self._db.execute(
                    "SELECT study, source, COUNT(*) AS runs,"
                    " SUM(status='completed') AS completed,"
                    " SUM(status<>'completed') AS not_completed,"
                    " GROUP_CONCAT(DISTINCT controller) AS controllers,"
                    " GROUP_CONCAT(DISTINCT profile) AS profiles,"
                    " GROUP_CONCAT(DISTINCT label) AS labels"
                    " FROM run GROUP BY study, source ORDER BY study"
                )
            ]
            return {
                "path": self.path,
                "schema_version": SCHEMA_VERSION,
                "runs": one("SELECT COUNT(*) FROM run"),
                "metric_samples": one("SELECT COUNT(*) FROM metric_sample"),
                "missions": one("SELECT COUNT(*) FROM mission"),
                "route_versions": one("SELECT COUNT(*) FROM route_version"),
                "priority_events": one("SELECT COUNT(*) FROM priority_event"),
                "video_jobs": one("SELECT COUNT(*) FROM video_job"),
                "observations": one("SELECT COUNT(*) FROM observation"),
                "artifacts": one("SELECT COUNT(*) FROM artifact"),
                "studies": studies,
            }


def _row(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in r.keys()}
