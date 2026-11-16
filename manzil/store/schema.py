"""SQLite schema of the experiment store (W5; D2 Section 4.9 ER model and data dictionary).

The tables follow the D2 data dictionary: Scenario, Run, MetricSample, Mission, RouteVersion,
PriorityEvent, VideoJob, Observation and Artifact. ControlDecision rows are not stored yet: the
batch runs keep ``applied_controls.csv`` only locally (it is not committed), so there is nothing
real to import; the live dashboard shows requested-vs-applied controls from the running safety
filter instead (G03).

Integrity rules from the dictionary that the schema enforces:

- a run's configuration is stored once (``config_json``) and never updated in place; a
  re-import replaces the whole run only when its content checksum changed;
- an Observation and an Artifact have exactly one owner (a run or a video job);
- route versions start at 1 and are unique per mission (the importer checks they increase);
- every metric sample carries its metric name, metric version and unit.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario (
    scenario_id      TEXT PRIMARY KEY,           -- "<scenario>/<profile>"
    scenario         TEXT NOT NULL,
    profile          TEXT NOT NULL,
    network_id       TEXT,                        -- "<file>#<sha256 prefix>"
    demand_generator TEXT
);

CREATE TABLE IF NOT EXISTS run (
    run_key         TEXT PRIMARY KEY,            -- run folder, relative to the repository
    run_id          TEXT NOT NULL,               -- id written by the runner (not unique)
    study           TEXT NOT NULL,               -- folder that holds the runs/ folder
    source          TEXT NOT NULL,               -- "batch" or "live"
    scenario_id     TEXT REFERENCES scenario(scenario_id),
    scenario        TEXT,
    network_id      TEXT,
    profile         TEXT,
    seed            INTEGER,
    controller      TEXT,
    label           TEXT,
    arm             TEXT,                        -- experiment arm: label, else controller[:plan]
    warmup_s        REAL,
    measure_s       REAL,
    metric_version  INTEGER,
    config_digest   TEXT,
    status          TEXT NOT NULL CHECK (status IN ('completed', 'stopped', 'failed')),
    termination     TEXT NOT NULL,               -- terminal reason is required (dictionary)
    created_at      TEXT,
    git_commit      TEXT,
    git_dirty       INTEGER,
    sumo_version    TEXT,
    wall_time_s     REAL,
    has_mission     INTEGER NOT NULL DEFAULT 0,
    config_json     TEXT NOT NULL,
    extra_json      TEXT NOT NULL DEFAULT '{}', -- non-numeric metrics (dicts, lists)
    content_sha256  TEXT NOT NULL,
    imported_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS run_study ON run(study);

CREATE TABLE IF NOT EXISTS metric_sample (
    run_key          TEXT NOT NULL REFERENCES run(run_key) ON DELETE CASCADE,
    metric_name      TEXT NOT NULL,
    metric_version   INTEGER,
    value            REAL,                       -- NULL = missing (never turned into 0)
    unit             TEXT NOT NULL,
    interval_start_s REAL,
    interval_end_s   REAL,
    PRIMARY KEY (run_key, metric_name)
);

CREATE TABLE IF NOT EXISTS mission (
    mission_id   TEXT PRIMARY KEY,               -- "<run_key>#<n>"
    run_key      TEXT NOT NULL REFERENCES run(run_key) ON DELETE CASCADE,
    vehicle_id   TEXT NOT NULL,
    origin       TEXT,
    destination  TEXT,
    status       TEXT,
    corridor     INTEGER,
    routing      TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    config_json  TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS route_version (
    mission_id    TEXT NOT NULL REFERENCES mission(mission_id) ON DELETE CASCADE,
    version       INTEGER NOT NULL CHECK (version >= 1),
    edge_list     TEXT NOT NULL,                 -- JSON list of edge ids
    cost_s        REAL,
    trigger       TEXT NOT NULL,
    snapshot_step INTEGER,
    compute_ms    REAL,
    PRIMARY KEY (mission_id, version)
);

CREATE TABLE IF NOT EXISTS priority_event (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id      TEXT NOT NULL REFERENCES mission(mission_id) ON DELETE CASCADE,
    route_version   INTEGER,
    intersection_id TEXT NOT NULL,
    state           TEXT NOT NULL,
    time_s          REAL,
    step            INTEGER,
    reason          TEXT
);

CREATE TABLE IF NOT EXISTS video_job (
    job_id        TEXT PRIMARY KEY,
    dataset       TEXT NOT NULL,                 -- e.g. "UA-DETRAC test"
    clip          TEXT NOT NULL,
    clip_checksum TEXT,                          -- NULL when the clip is not held by the team
    model_version TEXT NOT NULL,
    model_sha256  TEXT,
    tracker       TEXT,
    status        TEXT NOT NULL,
    frames        INTEGER,
    seconds       REAL,
    fps           REAL,
    produced_by   TEXT,                          -- kernel / script that produced the results
    label_status  TEXT NOT NULL,                 -- how the ground truth was made
    summary_json  TEXT NOT NULL DEFAULT '{}',
    imported_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observation (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT REFERENCES video_job(job_id) ON DELETE CASCADE,
    run_key      TEXT REFERENCES run(run_key) ON DELETE CASCADE,
    source_mode  TEXT NOT NULL,                  -- "video" or "sumo"
    entity_id    TEXT NOT NULL,
    observed_at_s REAL NOT NULL,
    name         TEXT NOT NULL,
    value        REAL,
    reference    REAL,                           -- ground-truth value when there is one
    unit         TEXT NOT NULL,
    CHECK ((job_id IS NULL) <> (run_key IS NULL))
);
CREATE INDEX IF NOT EXISTS observation_job ON observation(job_id, name, observed_at_s);

CREATE TABLE IF NOT EXISTS artifact (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_key    TEXT REFERENCES run(run_key) ON DELETE CASCADE,
    job_id     TEXT REFERENCES video_job(job_id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    uri        TEXT NOT NULL,                    -- path relative to the repository, or URL
    sha256     TEXT,
    provenance TEXT NOT NULL,
    CHECK ((job_id IS NULL) <> (run_key IS NULL))
);
"""
