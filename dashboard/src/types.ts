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
  stops: number;
  corridor: Record<string, string>;
  corridor_events: CorridorEvent[];
  metrics: Record<string, unknown> | null;
}

export interface LiveState {
  status: "idle" | "starting" | "running" | "finished" | "stopped" | "error";
  version: number;
  run_id?: string;
  config?: { controller: string; profile: string; seed: number; duration_s: number; speed: number };
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
