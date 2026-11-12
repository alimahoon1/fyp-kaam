import { useEffect, useState } from "react";
import { api, subscribeState } from "./api";
import { MapView } from "./MapView";
import type { LiveState, Network, Options } from "./types";

const fmtTime = (s?: number) => {
  if (s === undefined) return "–";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
};
const ACTIVE = new Set(["starting", "running"]);
const CORRIDOR_LABEL: Record<string, string> = {
  REQUESTED: "requested",
  SAFE_TRANSITION: "safe transition",
  ACTIVE_PRIORITY: "green for ambulance",
  RECOVERY: "recovering",
};

export function App() {
  const [net, setNet] = useState<Network | null>(null);
  const [opts, setOpts] = useState<Options | null>(null);
  const [state, setState] = useState<LiveState>({ status: "idle", version: 0 });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const [controller, setController] = useState("fixed_time");
  const [profile, setProfile] = useState("medium");
  const [seed, setSeed] = useState(0);
  const [duration, setDuration] = useState(3600);
  const [speed, setSpeed] = useState(10);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [corridor, setCorridor] = useState(true);

  useEffect(() => {
    api.network().then(setNet).catch((e) => setError(`Cannot reach the API: ${e.message}`));
    api.options().then((o) => {
      setOpts(o);
      setController(o.defaults.controller);
      setProfile(o.defaults.profile);
      setOrigin(o.defaults.origin);
      setDestination(o.defaults.destination);
      setCorridor(o.defaults.corridor);
    }).catch(() => {});
    return subscribeState(setState);
  }, []);

  const act = async (fn: () => Promise<unknown>, ok?: (r: any) => string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (ok) setNotice(ok(r));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const running = ACTIVE.has(state.status);
  const amb = state.ambulance;
  const ambBusy = amb && (amb.status === "ACTIVE" || amb.status === "PENDING");
  const st = state.stats;
  const progress = state.end_s ? Math.min(100, ((state.sim_time_s ?? 0) / state.end_s) * 100) : 0;
  const edgeIds = net ? net.edges.map((e) => e.id) : [];

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">M</span>
          <div>
            <h1>Manzil</h1>
            <p>Live traffic &amp; emergency routing · {net?.scenario ?? "…"} (SUMO)</p>
          </div>
        </div>
        <div className="header-stats">
          <span className={`pill ${state.status}`} data-testid="status">{state.status}</span>
          <span className="clock">
            sim <b>{fmtTime(state.sim_time_s)}</b> / {fmtTime(state.end_s)}
          </span>
          {state.config && <span className="muted">{state.config.controller} · {state.config.profile} · seed {state.config.seed}</span>}
        </div>
      </header>
      <div className="progress"><div style={{ width: `${progress}%` }} /></div>

      <main>
        <section className="map-wrap">
          {net ? (
            <MapView net={net} state={state} selected={selected} onSelect={setSelected} />
          ) : (
            <div className="placeholder">{error ?? "Loading network…"}</div>
          )}
          <div className="legend">
            <span><i className="sw green" />green</span>
            <span><i className="sw yellow" />yellow</span>
            <span><i className="sw red" />red</span>
            <span><i className="sw route" />ambulance route</span>
            <span><i className="sw busy" />queue ≥ 3</span>
            <span><i className="sw jam" />queue ≥ 8</span>
            <span><i className="ring active" />corridor junction</span>
            <span className="muted">Click a road to select it</span>
          </div>
        </section>

        <aside>
          {(error || state.error) && <div className="alert">{error ?? state.error}</div>}
          {notice && !error && <div className="notice" onClick={() => setNotice(null)}>{notice}</div>}

          <div className="card">
            <h2>Run</h2>
            <label>Controller
              <select value={controller} onChange={(e) => setController(e.target.value)} disabled={running}>
                {opts?.controllers.map((c) => (
                  <option key={c.id} value={c.id} disabled={!c.available}>
                    {c.label}{c.available ? "" : " (unavailable)"}
                  </option>
                ))}
              </select>
            </label>
            <div className="row">
              <label>Demand
                <select value={profile} onChange={(e) => setProfile(e.target.value)} disabled={running}>
                  {opts?.profiles.map((p) => <option key={p.id} value={p.id}>{p.id}</option>)}
                </select>
              </label>
              <label>Seed
                <input type="number" min={0} value={seed} onChange={(e) => setSeed(Number(e.target.value))} disabled={running} />
              </label>
              <label>Length (s)
                <input type="number" min={60} step={60} value={duration} onChange={(e) => setDuration(Number(e.target.value))} disabled={running} />
              </label>
            </div>
            <label>Speed: {speed === 0 ? "max" : `${speed}× real time`}
              <input type="range" min={0} max={60} step={1} value={speed}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setSpeed(v);
                  if (running) api.speed(v).catch(() => {});
                }} />
            </label>
            <div className="buttons">
              <button className="primary" disabled={busy || running}
                onClick={() => act(() => api.start({ controller, profile, seed, duration_s: duration, speed }))}>
                Start run
              </button>
              <button className="danger" disabled={busy || !running} onClick={() => act(api.stop)}>
                Stop
              </button>
            </div>
          </div>

          <div className="card">
            <h2>Ambulance</h2>
            <div className="row">
              <label>From
                <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
                  {edgeIds.map((id) => <option key={id}>{id}</option>)}
                </select>
              </label>
              <label>To
                <select value={destination} onChange={(e) => setDestination(e.target.value)}>
                  {edgeIds.map((id) => <option key={id}>{id}</option>)}
                </select>
              </label>
            </div>
            <label className="check">
              <input type="checkbox" checked={corridor} onChange={(e) => setCorridor(e.target.checked)} />
              Green corridor (Algorithm 2)
            </label>
            <button className="primary wide" disabled={busy || state.status !== "running" || !!ambBusy}
              onClick={() => act(() => api.dispatch(origin, destination, corridor),
                (r) => `${r.vehicle_id} dispatched at ${fmtTime(r.dispatch_s)}`)}>
              Dispatch ambulance
            </button>
            {amb && (
              <div className="amb">
                <div className="kv"><span>Mission</span><b className={`tag ${amb.status}`}>{amb.status}</b></div>
                <div className="kv"><span>Route version</span><b>v{amb.route_version} <small>({amb.route_triggers.join(" → ")})</small></b></div>
                <div className="kv"><span>On road</span><b>{amb.edge ?? "–"}</b></div>
                <div className="kv"><span>Speed</span><b>{amb.speed_mps != null ? `${(amb.speed_mps * 3.6).toFixed(0)} km/h` : "–"}</b></div>
                <div className="kv"><span>Stops</span><b>{amb.stops}</b></div>
                {amb.status === "ARRIVED" && amb.metrics && (
                  <div className="kv"><span>Response time</span>
                    <b>{String(amb.metrics.amb_travel_time_s)} s <small>(free flow {String(amb.metrics.amb_free_flow_time_s)} s)</small></b>
                  </div>
                )}
                <div className="route-list">{amb.route.map((e) => (
                  <span key={e} className={e === amb.edge ? "cur" : ""}>{e}</span>
                ))}</div>
                <h3>Corridor {amb.corridor_enabled ? "" : "(off)"}</h3>
                {amb.corridor_enabled && Object.keys(amb.corridor).length === 0 && <p className="muted">No junction held right now.</p>}
                {Object.entries(amb.corridor).map(([tls, s]) => (
                  <div className="kv" key={tls}><span>{tls}</span><b className={`cor ${s}`}>{CORRIDOR_LABEL[s] ?? s}</b></div>
                ))}
                {amb.corridor_events.length > 0 && (
                  <ul className="events">
                    {amb.corridor_events.slice().reverse().map((ev, i) => (
                      <li key={i}>{fmtTime(ev.time_s)} {ev.tls} {ev.state}{ev.reason ? ` (${ev.reason})` : ""}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h2>Incident</h2>
            <p className="muted">Selected road: <b>{selected ?? "none (click the map)"}</b></p>
            <div className="buttons">
              <button className="danger" disabled={busy || !selected || state.status !== "running" || (state.closed_edges ?? []).includes(selected)}
                onClick={() => selected && act(() => api.closeRoad(selected),
                  (r) => `Closed ${r.edge_id} at ${fmtTime(r.time_s)}; ${r.vehicles_rerouted} vehicles rerouted`)}>
                Close road
              </button>
              <button disabled={!selected} onClick={() => selected && setOrigin(selected)}>Set as From</button>
              <button disabled={!selected} onClick={() => selected && setDestination(selected)}>Set as To</button>
            </div>
            {(state.closed_edges ?? []).length > 0 && (
              <p>Closed: {(state.closed_edges ?? []).map((e) => <span key={e} className="chip">{e}</span>)}</p>
            )}
          </div>

          <div className="card">
            <h2>Network</h2>
            <div className="grid-stats">
              <div><small>vehicles now</small><b>{st?.running ?? "–"}</b></div>
              <div><small>arrived</small><b>{st?.arrived ?? "–"}</b></div>
              <div><small>queued (halting)</small><b>{st?.halting ?? "–"}</b></div>
              <div><small>mean speed</small><b>{st?.mean_speed_mps != null ? `${(st.mean_speed_mps * 3.6).toFixed(0)} km/h` : "–"}</b></div>
              <div><small>safety violations</small><b className={st?.safety_violations ? "bad" : "good"}>{st?.safety_violations ?? "–"}</b></div>
              <div><small>sim rate</small><b>{st?.sim_rate != null ? `${st.sim_rate}×` : "–"}</b></div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
