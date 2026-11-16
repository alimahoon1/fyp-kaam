import type {
  Check, Comparison, LiveState, Network, Observation, Options, RunConfig, RunRow, StoreSummary,
  VideoJob,
} from "./types";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : `${res.status} ${res.statusText}`);
  }
  return data as T;
}

const qs = (p: Record<string, string | number | undefined | null>) =>
  new URLSearchParams(
    Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== "") as [string, string][],
  ).toString();

export const api = {
  options: () => request<Options>("/api/options"),
  network: () => request<Network>("/api/network"),
  state: () => request<LiveState>("/api/state"),
  validate: (cfg: RunConfig) => request<{ ok: boolean; checks: Check[] }>("/api/run/validate", cfg),
  start: (cfg: RunConfig) => request<LiveState>("/api/run/start", cfg),
  stop: () => request<LiveState>("/api/run/stop", {}),
  pause: () => request<LiveState>("/api/run/pause", {}),
  resume: () => request<LiveState>("/api/run/resume", {}),
  fault: (kind: string) => request<{ kind: string; sim_time_s: number }>("/api/run/fault", { kind }),
  speed: (speed: number) => request<{ speed: number }>("/api/run/speed", { speed }),
  dispatch: (origin: string, destination: string, corridor: boolean) =>
    request<{ vehicle_id: string; dispatch_s: number }>("/api/ambulance", { origin, destination, corridor }),
  closeRoad: (edge_id: string) =>
    request<{ edge_id: string; time_s: number; vehicles_rerouted: number }>("/api/roads/close", { edge_id }),
  storeSummary: () => request<StoreSummary>("/api/store/summary"),
  storeImport: () => request<unknown>("/api/store/import", {}),
  runs: (f: Record<string, string | undefined>) => request<RunRow[]>(`/api/runs?${qs(f)}`),
  run: (key: string) => request<any>(`/api/runs/${key}`),
  compare: (run_keys: string[], group_by: string, metrics?: string[]) =>
    request<Comparison>("/api/compare", { run_keys, group_by, metrics }),
  jobs: () => request<VideoJob[]>("/api/perception/jobs"),
  job: (id: string) => request<VideoJob>(`/api/perception/jobs/${id}`),
  observations: (id: string, name?: string) =>
    request<Observation[]>(`/api/perception/jobs/${id}/observations?${qs({ name })}`),
};

/** FR-19: download an export file (the browser saves it). */
export async function downloadExport(run_keys: string[], format: "json" | "csv") {
  const res = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_keys, format }),
  });
  if (!res.ok) throw new Error(`export failed: ${res.status}`);
  const blob = await res.blob();
  const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? `export.${format}`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

export type Connection = "connecting" | "live" | "polling" | "disconnected";

/** Live state over a WebSocket, with polling as a fallback when the socket drops (FR-16:
 *  the connection status is reported so the dashboard can show "disconnected"). */
export function subscribeState(
  onState: (s: LiveState) => void,
  onConnection: (c: Connection) => void = () => {},
): () => void {
  let closed = false;
  let ws: WebSocket | null = null;
  let poll: number | undefined;

  const startPolling = () => {
    if (poll !== undefined || closed) return;
    poll = window.setInterval(
      () =>
        api.state()
          .then((s) => { onConnection("polling"); onState(s); })
          .catch(() => onConnection("disconnected")),
      500,
    );
  };
  const connect = () => {
    if (closed) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/state`);
    ws.onmessage = (ev) => onState(JSON.parse(ev.data) as LiveState);
    ws.onopen = () => {
      onConnection("live");
      if (poll !== undefined) window.clearInterval(poll);
      poll = undefined;
    };
    ws.onclose = () => {
      if (closed) return;
      onConnection("disconnected");
      startPolling();
      window.setTimeout(connect, 2000);
    };
  };
  connect();
  return () => {
    closed = true;
    ws?.close();
    if (poll !== undefined) window.clearInterval(poll);
  };
}
