import { useState } from "react";
import type { Shared } from "../App";
import { api } from "../api";
import { LineChart } from "../charts";
import { ACTIVE, CORRIDOR_LABEL, fmtTime, Freshness, Kv } from "../common";
import { MapView } from "../MapView";

export function MapLegend({ extra }: { extra?: React.ReactNode }) {
  return (
    <div className="legend">
      <span><i className="sw green" />green</span>
      <span><i className="sw yellow" />yellow</span>
      <span><i className="sw red" />red</span>
      <span><i className="sw route" />ambulance route</span>
      <span><i className="sw busy" />queue ≥ 3 veh</span>
      <span><i className="sw jam" />queue ≥ 8 veh</span>
      <span><i className="ring active" />corridor junction</span>
      <span>✕ closed road</span>
      {extra}
    </div>
  );
}

/** G02 Traffic overview: map, run control (FR-02), controller and source, warnings, timeline. */
export function OverviewScreen({ net, opts, state, conn, config, act, busy, go }: Shared) {
  const [selected, setSelected] = useState<string | null>(null);
  const [speed, setSpeed] = useState(config.speed);
  const active = ACTIVE.has(state.status);
  const st = state.stats;
  const amb = state.ambulance;
  const ctrl = opts?.controllers.find((c) => c.id === state.config?.controller);
  const fb = state.controller_decisions?.fallback ?? 0;
  const history = state.history ?? [];

  const timeline = [
    ...(state.pauses ?? []).map((p) => ({ t: p.sim_time_s, text: `paused${p.wall_s != null ? ` for ${p.wall_s} s (wall clock)` : " (now)"}` })),
    ...(state.faults ?? []).map((f) => ({ t: f.sim_time_s, text: `fault injected: ${f.kind}` })),
    ...(state.closed_edges ?? []).map((e) => ({ t: null as number | null, text: `road ${e} closed` })),
    ...(amb?.corridor_events ?? []).map((e) => ({ t: e.time_s, text: `${e.tls} ${CORRIDOR_LABEL[e.state] ?? e.state}` })),
    ...(amb?.routing_log ?? []).map((e) => ({ t: e.time_s, text: `route ${e.event}${e.reason ? ` (${e.reason})` : ""}` })),
  ].sort((a, b) => (b.t ?? 1e9) - (a.t ?? 1e9));

  return (
    <main className="map-page">
      <section className="map-wrap">
        {net ? <MapView net={net} state={state} selected={selected} onSelect={setSelected} />
          : <div className="placeholder">Loading network…</div>}
        <MapLegend extra={<span className="muted">Click a road to select it</span>} />
      </section>

      <aside>
        <div className="card">
          <h2>Run</h2>
          {state.status === "idle" ? (
            <>
              <p className="muted">No run yet. Configure and validate one on G01.</p>
              <div className="buttons">
                <button className="primary" onClick={() => go("config")}>Configure run (G01)</button>
              </div>
            </>
          ) : (
            <>
              <Kv k="Run" v={<code>{state.run_id ?? "–"}</code>} />
              <Kv k="Controller" v={ctrl?.label ?? state.config?.controller ?? "–"}
                small={fb ? `· fallback holds: ${fb}` : undefined} />
              <Kv k="Demand / seed" v={`${state.config?.profile ?? "–"} / ${state.config?.seed ?? "–"}`} />
              <Freshness state={state} conn={conn} />
            </>
          )}
          <label>Speed: {speed === 0 ? "max" : `${speed}× real time`}
            <input type="range" min={0} max={60} step={1} value={speed} onChange={(e) => {
              const v = Number(e.target.value);
              setSpeed(v);
              if (active) api.speed(v).catch(() => {});
            }} />
          </label>
          <div className="buttons">
            {!active && state.status !== "idle" && (
              <button className="primary" disabled={busy} onClick={() => go("config")}>New run (G01)</button>
            )}
            <button disabled={busy || state.status !== "running"} onClick={() => act(api.pause, () => "Paused: SUMO is not stepped; commands still work")}>Pause</button>
            <button disabled={busy || state.status !== "paused"} onClick={() => act(api.resume, () => "Resumed")}>Resume</button>
            <button className="danger" disabled={busy || !active} onClick={() => act(api.stop)}>Stop</button>
          </div>
          {state.config?.controller === "dqn" && active && (
            <div className="buttons">
              <button className="danger" disabled={busy || (state.faults ?? []).length > 0}
                title="Fault injection: the DQN policy fails from now on, so its FR-20 fallback holds the current phase"
                onClick={() => act(() => api.fault("rl_loss"), (r) => `RL service loss injected at ${fmtTime(r.sim_time_s)}`)}>
                Inject fault: RL service loss
              </button>
            </div>
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
          <LineChart ariaLabel="Vehicles in the network and halting vehicles over simulated time"
            xLabel="sim time (min)" yLabel="vehicles" xFormat={(x) => (x % 1 ? x.toFixed(1) : x.toFixed(0))} height={160}
            series={[
              { name: "in network", points: history.map((h) => [h[0] / 60, h[1]]) },
              { name: "halting", points: history.map((h) => [h[0] / 60, h[2]]) },
            ]} />
        </div>

        <div className="card">
          <h2>Emergency</h2>
          {amb ? (
            <>
              <Kv k={amb.vehicle_id} v={<span className={`tag ${amb.status}`}>{amb.status}</span>} />
              <Kv k="Route" v={`v${amb.route_version}`} small={amb.route_triggers.join(" → ")} />
              <Kv k="Corridor" v={amb.corridor_enabled ? Object.entries(amb.corridor).map(([t, s]) => `${t} ${CORRIDOR_LABEL[s] ?? s}`).join(", ") || "no junction held" : "off"} />
            </>
          ) : <p className="muted">No ambulance dispatched.</p>}
          <button className="wide" onClick={() => go("emergency")}>Open dispatch (G04)</button>
        </div>

        <div className="card">
          <h2>Incident</h2>
          <p className="muted">Selected road: <b>{selected ?? "none (click the map)"}</b></p>
          <button className="danger" disabled={busy || !selected || !active || (state.closed_edges ?? []).includes(selected ?? "")}
            onClick={() => selected && act(() => api.closeRoad(selected),
              (r) => `Closed ${r.edge_id} at ${fmtTime(r.time_s)}; ${r.vehicles_rerouted} vehicles rerouted`)}>
            Close road
          </button>
          {state.scheduled?.incident && <p className="muted">Planned: close {state.scheduled.incident.edge_id} at {fmtTime(state.scheduled.incident.time_s)}</p>}
        </div>

        <div className="card">
          <h2>Event timeline</h2>
          {timeline.length ? (
            <ul className="events">{timeline.slice(0, 14).map((e, i) => <li key={i}>{fmtTime(e.t)} {e.text}</li>)}</ul>
          ) : <p className="muted">No events yet.</p>}
        </div>
      </aside>
    </main>
  );
}
