// Shapes of the FastAPI responses (manzil/api/app.py and manzil/api/live.py).

export type Point = [number, number];

export interface Lane {
  id: string;
  width: number;
  shape: Point[];
}

export interface Edge {
  id: string;
  from: string;
  to: string;
  lanes: Lane[];
}

export interface Junction {
  id: string;
  x: number;
  y: number;
  type: string;
  shape: Point[];
}

export interface TlsLink {
  index: number;
  from_lane: string;
  to_lane: string;
  dir: string;
}

export interface Tls {
  id: string;
  junction: string;
  links: TlsLink[];
  green_phases: string[];
}

export interface Network {
  scenario: string;
  network_id: string;
  bounds: [number, number, number, number];
  edges: Edge[];
  junctions: Junction[];
  tls: Tls[];
  entry_edges: string[];
  exit_edges: string[];
}

export interface ControllerOption {
  id: string;
  label: string;
  available: boolean;
  note: string;
}

export interface Options {
  controllers: ControllerOption[];
  profiles: { id: string; description: string }[];
  defaults: {
    controller: string;
    profile: string;
    seed: number;
    duration_s: number;
    speed: number;
    origin: string;
    destination: string;
    corridor: boolean;
  };
}

export interface SignalInfo {
  state: string;
  phase: number | null;
  owner: "NORMAL" | "CORRIDOR";
  in_transition: boolean;
  elapsed_s: number;
}

export interface CorridorEvent {
  time_s: number;
  tls: string;
  state: string;
  route_version?: number;
  reason?: string;
  recovery_s?: number;
}

export interface Ambulance {
  vehicle_id: string;
  status: "PENDING" | "ACTIVE" | "ARRIVED" | "NO_ROUTE";
  origin: string;
  destination: string;
  corridor_enabled: boolean;
  dispatch_s: number | null;
  arrival_s: number | null;
  position: [number, number, number] | null;
  speed_mps: number | null;
  edge: string | null;
  route: string[];
  route_version: number;
  route_triggers: string[];
  route_versions: { version: number; edge_ids: string[]; cost_s: number | null; trigger: string; snapshot_step: number }[];
  routing_log: { time_s: number; event: string; route_version?: number; saving_s?: number | null; reason?: string }[];
  stops: number;
  corridor: Record<string, string>;
  corridor_events: CorridorEvent[];
  metrics: Record<string, unknown> | null;
}

export interface Warning {
  code: "stale" | "invalid" | "disconnected" | "fallback" | string;
  level: "info" | "warning" | "error";
  message: string;
  since_s?: number | null;
}

export interface ApproachInfo {
  approach_id: string;
  count: number;
  queue: number;
  wait_s: number;
  speed_mps: number | null;
  occupancy_pct: number;
}

export interface AppliedControlInfo {
  request_id: number;
  controller: string;
  tls: string;
  requested_phase: number;
  applied_phase: number | null;
  effective_step: number;
  intervention: string;
  reason: string;
}

export interface MissionPlan {
  origin: string;
  destination: string;
  corridor: boolean;
  dispatch_s: number;
}

export interface IncidentPlan {
  edge_id: string;
  time_s: number;
}

export interface RunConfig {
  controller: string;
  profile: string;
  seed: number;
  duration_s: number;
  speed: number;
  mission?: MissionPlan | null;
  incident?: IncidentPlan | null;
}

export interface Check {
  field: string;
  level: "ok" | "info" | "warning" | "error";
  message: string;
}

export interface LiveState {
  status: "idle" | "starting" | "running" | "paused" | "finished" | "stopped" | "error";
  version: number;
  run_id?: string;
  config?: RunConfig;
  source_mode?: string;
  network_id?: string;
  produced_at?: number;
  effective_step?: number;
  age_s?: number;
  warnings?: Warning[];
  pauses?: { sim_time_s: number; wall_s: number | null }[];
  faults?: { kind: string; sim_time_s: number; note: string }[];
  controller_decisions?: Record<string, number>;
  history?: [number, number, number, number, number | null][]; // t, running, halting, arrived, speed
  approaches?: Record<string, ApproachInfo[]>;
  applied_controls?: AppliedControlInfo[];
  scheduled?: { mission: MissionPlan | null; incident: IncidentPlan | null };
  sim_time_s?: number;
  end_s?: number;
  stats?: {
    running: number;
    departed: number;
    arrived: number;
    planned: number;
    halting: number;
    mean_speed_mps: number | null;
    safety_violations: number;
    sim_rate: number | null;
  };
  signals?: Record<string, SignalInfo>;
  vehicles?: [number, number, number][];
  edge_halting?: Record<string, number>;
  closed_edges?: string[];
  ambulance?: Ambulance | null;
  missions_done?: number;
  error?: string;
}

// ----- store (G05) and perception (G03) -----

export interface RunRow {
  run_key: string;
  run_id: string;
  study: string;
  source: "batch" | "live";
  scenario: string | null;
  network_id: string | null;
  profile: string | null;
  seed: number | null;
  controller: string | null;
  label: string | null;
  arm: string | null;
  warmup_s: number | null;
  measure_s: number | null;
  metric_version: number | null;
  status: "completed" | "stopped" | "failed";
  termination: string;
  created_at: string | null;
  git_commit: string | null;
  has_mission: number;
}

export interface StoreSummary {
  path: string;
  runs: number;
  metric_samples: number;
  missions: number;
  route_versions: number;
  priority_events: number;
  video_jobs: number;
  observations: number;
  studies: { study: string; source: string; runs: number; completed: number; not_completed: number }[];
}

export interface GroupStats {
  n: number;
  mean: number | null;
  sd: number | null;
  ci95: number | null;
  min: number | null;
  max: number | null;
  missing: number;
  points: { run_key: string; profile: string; seed: number; value: number | null }[];
}

export interface Comparison {
  group_by: string;
  reference: string | null;
  groups: Record<string, number>;
  runs_selected: number;
  runs_used: number;
  excluded: { run_key: string; status: string; termination: string }[];
  warnings: Warning[];
  metrics: Record<
    string,
    {
      label: string;
      unit: string;
      lower_is_better: boolean | null;
      groups: Record<string, GroupStats>;
      paired_vs_reference: Record<string, Omit<GroupStats, "points" | "missing">>;
    }
  >;
}

export interface VideoJob {
  job_id: string;
  dataset: string;
  clip: string;
  clip_checksum: string | null;
  model_version: string;
  model_sha256: string | null;
  tracker: string | null;
  status: string;
  frames: number | null;
  seconds: number | null;
  fps: number | null;
  produced_by: string | null;
  label_status: string;
  imported_at: string;
  summary: Record<string, any>;
  artifacts?: { type: string; uri: string; sha256: string | null; provenance: string }[];
}

export interface Observation {
  source_mode: string;
  entity_id: string;
  observed_at_s: number;
  name: string;
  value: number | null;
  reference: number | null;
  unit: string;
}
