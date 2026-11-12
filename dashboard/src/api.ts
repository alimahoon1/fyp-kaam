import type { LiveState, Network, Options } from "./types";

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

export const api = {
  options: () => request<Options>("/api/options"),
  network: () => request<Network>("/api/network"),
  state: () => request<LiveState>("/api/state"),
  start: (cfg: { controller: string; profile: string; seed: number; duration_s: number; speed: number }) =>
    request<LiveState>("/api/run/start", cfg),
  stop: () => request<LiveState>("/api/run/stop", {}),
  speed: (speed: number) => request<{ speed: number }>("/api/run/speed", { speed }),
  dispatch: (origin: string, destination: string, corridor: boolean) =>
    request<{ vehicle_id: string; dispatch_s: number }>("/api/ambulance", { origin, destination, corridor }),
  closeRoad: (edge_id: string) =>
    request<{ edge_id: string; time_s: number; vehicles_rerouted: number }>("/api/roads/close", { edge_id }),
};

/** Live state over a WebSocket, with polling as a fallback when the socket drops. */
export function subscribeState(onState: (s: LiveState) => void): () => void {
  let closed = false;
  let ws: WebSocket | null = null;
  let poll: number | undefined;

  const startPolling = () => {
    if (poll !== undefined || closed) return;
    poll = window.setInterval(() => api.state().then(onState).catch(() => {}), 500);
  };
  const connect = () => {
    if (closed) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/state`);
    ws.onmessage = (ev) => onState(JSON.parse(ev.data) as LiveState);
    ws.onopen = () => {
      if (poll !== undefined) window.clearInterval(poll);
      poll = undefined;
    };
    ws.onclose = () => {
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
