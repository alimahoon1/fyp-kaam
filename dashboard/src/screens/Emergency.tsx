import { useEffect, useState } from "react";
import type { Shared } from "../App";
import { api } from "../api";
import { CORRIDOR_LABEL, fmtTime, Kv } from "../common";
import { MapView } from "../MapView";
import { MapLegend } from "./Overview";

/** G04 Emergency dispatch and route: create a mission, follow route versions (with their
 *  time-based cost and trigger) and the corridor lifecycle per junction. */
export function EmergencyScreen({ net, opts, state, act, busy }: Shared) {
  const [selected, setSelected] = useState<string | null>(null);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [corridor, setCorridor] = useState(true);
  useEffect(() => {
    if (opts && !origin) { setOrigin(opts.defaults.origin); setDestination(opts.defaults.destination); }
  }, [opts]); // eslint-disable-line

  const amb = state.ambulance;
  const busyAmb = amb && (amb.status === "ACTIVE" || amb.status === "PENDING");
  const edgeIds = net ? net.edges.map((e) => e.id) : [];
  const versions = amb?.route_versions ?? [];
  const old = versions.slice(0, -1).map((v) => v.edge_ids);
  const m = amb?.metrics as Record<string, number | string | null> | null | undefined;

  return (
    <main className="map-page">
      <section className="map-wrap">
        {net ? <MapView net={net} state={state} selected={selected} onSelect={setSelected} oldRoutes={old} />
          : <div className="placeholder">Loading network…</div>}
        <MapLegend extra={<span><i className="sw old" />earlier route version</span>} />
      </section>
      <aside>
        <div className="card">
          <h2>Dispatch</h2>
          <div className="row">
            <label>Origin<select value={origin} onChange={(e) => setOrigin(e.target.value)}>{edgeIds.map((id) => <option key={id}>{id}</option>)}</select></label>
            <label>Destination<select value={destination} onChange={(e) => setDestination(e.target.value)}>{edgeIds.map((id) => <option key={id}>{id}</option>)}</select></label>
          </div>
          <div className="buttons">
            <button disabled={!selected} onClick={() => selected && setOrigin(selected)}>Selected road → origin</button>
            <button disabled={!selected} onClick={() => selected && setDestination(selected)}>→ destination</button>
          </div>
          <label className="check"><input type="checkbox" checked={corridor} onChange={(e) => setCorridor(e.target.checked)} />Green corridor (Algorithm 2)</label>
          <button className="primary wide" disabled={busy || state.status !== "running" || !!busyAmb}
            onClick={() => act(() => api.dispatch(origin, destination, corridor), (r) => `${r.vehicle_id} dispatched at ${fmtTime(r.dispatch_s)}`)}>
            Dispatch ambulance
          </button>
          {state.status !== "running" && <p className="muted">Dispatch needs a running run (status: {state.status}).</p>}
          {state.scheduled?.mission && <p className="muted">Planned in G01: {state.scheduled.mission.origin} → {state.scheduled.mission.destination} at {fmtTime(state.scheduled.mission.dispatch_s)}</p>}
        </div>

        {amb && (
          <div className="card">
            <h2>Mission {amb.vehicle_id}</h2>
            <Kv k="Status" v={<span className={`tag ${amb.status}`}>{amb.status}</span>} />
            <Kv k="From → to" v={`${amb.origin} → ${amb.destination}`} />
            <Kv k="Dispatched" v={fmtTime(amb.dispatch_s)} small={amb.arrival_s != null ? `arrived ${fmtTime(amb.arrival_s)}` : ""} />
            <Kv k="On road" v={amb.edge ?? "–"} small={amb.speed_mps != null ? `${(amb.speed_mps * 3.6).toFixed(0)} km/h` : ""} />
            <Kv k="Stops" v={amb.stops} />
            {m && amb.status === "ARRIVED" && (
              <>
                <Kv k="Travel time" v={`${m.amb_travel_time_s} s`} small={`free flow ${m.amb_free_flow_time_s} s`} />
                <Kv k="Excess delay" v={`${m.amb_excess_delay_s} s`} />
              </>
            )}
            <table className="tbl">
              <caption>Route versions (cost = time-based estimate, Eq 5.4)</caption>
              <thead><tr><th>v</th><th>trigger</th><th>cost (s)</th><th>step</th><th>roads</th></tr></thead>
              <tbody>
                {versions.map((v) => (
                  <tr key={v.version} className={v.version === amb.route_version ? "cur" : ""}>
                    <td>v{v.version}{v.version === amb.route_version ? " (current)" : ""}</td><td>{v.trigger}</td>
                    <td>{v.cost_s ?? "–"}</td><td>{v.snapshot_step}</td><td className="small">{v.edge_ids.join(" → ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(amb.routing_log ?? []).length > 0 && (
              <>
                <h3>Routing decisions (Algorithm 1)</h3>
                <ul className="events">{amb.routing_log.slice().reverse().map((e, i) => (
                  <li key={i}>{fmtTime(e.time_s)} {e.event}{e.reason ? ` · ${e.reason}` : ""}{e.saving_s != null ? ` · saving ${e.saving_s.toFixed(1)} s` : ""}</li>
                ))}</ul>
              </>
            )}
          </div>
        )}

        {amb && (
          <div className="card">
            <h2>Corridor lifecycle {amb.corridor_enabled ? "" : "(off)"}</h2>
            {amb.corridor_enabled && Object.keys(amb.corridor).length === 0 && <p className="muted">No junction held right now.</p>}
            {Object.entries(amb.corridor).map(([tls, s]) => (
              <Kv key={tls} k={tls} v={<span className={`cor ${s}`}>{s} · {CORRIDOR_LABEL[s] ?? s}</span>} />
            ))}
            {amb.corridor_events.length > 0 && (
              <ul className="events">{amb.corridor_events.slice().reverse().map((ev, i) => (
                <li key={i}>{fmtTime(ev.time_s)} {ev.tls} {ev.state}{ev.route_version ? ` (route v${ev.route_version})` : ""}{ev.reason ? ` · ${ev.reason}` : ""}</li>
              ))}</ul>
            )}
          </div>
        )}
      </aside>
    </main>
  );
}
