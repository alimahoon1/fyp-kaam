import { useEffect, useState } from "react";
import type { Shared } from "../App";
import { api } from "../api";
import { ACTIVE, LEVEL_ICON } from "../common";
import type { Check } from "../types";

/** G01 Experiment configuration: every field is validated by the API before Start (FR-01). */
export function ConfigScreen({ net, opts, state, config, setConfig, act, busy, go }: Shared) {
  const [checks, setChecks] = useState<Check[] | null>(null);
  const [checking, setChecking] = useState(false);
  const running = ACTIVE.has(state.status);
  const edgeIds = net ? net.edges.map((e) => e.id) : [];
  const set = (patch: Partial<typeof config>) => setConfig({ ...config, ...patch });

  useEffect(() => {
    setChecking(true);
    const t = window.setTimeout(() => {
      api.validate(config)
        .then((r) => setChecks(r.checks))
        .catch((e) => setChecks([{ field: "api", level: "error", message: (e as Error).message }]))
        .finally(() => setChecking(false));
    }, 250);
    return () => window.clearTimeout(t);
  }, [config]);

  const errors = (checks ?? []).filter((c) => c.level === "error").length;
  const m = config.mission;
  const inc = config.incident;
  const defaults = opts?.defaults;

  return (
    <main className="page two-col">
      <section className="card form">
        <h2>Experiment configuration</h2>
        <p className="muted">A live run is a demonstration on the synthetic grid. The configuration is fixed once the run starts (NFR-10).</p>

        <fieldset disabled={running}>
          <legend>Network and demand</legend>
          <div className="row">
            <label>Scenario
              <select value="grid3x3" disabled><option value="grid3x3">grid3x3 (synthetic, 9 signals)</option></select>
            </label>
            <label>Demand profile
              <select value={config.profile} onChange={(e) => set({ profile: e.target.value })}>
                {opts?.profiles.map((p) => <option key={p.id} value={p.id}>{p.id} – {p.description}</option>)}
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset disabled={running}>
          <legend>Controller</legend>
          <label>Signal controller
            <select value={config.controller} onChange={(e) => set({ controller: e.target.value })}>
              {opts?.controllers.map((c) => (
                <option key={c.id} value={c.id}>{c.label}{c.available ? "" : ` (unavailable: ${c.note})`}</option>
              ))}
            </select>
          </label>
        </fieldset>

        <fieldset disabled={running}>
          <legend>Seed and duration</legend>
          <div className="row">
            <label>Seed<input type="number" min={0} value={config.seed} onChange={(e) => set({ seed: Number(e.target.value) })} /></label>
            <label>Duration (s)<input type="number" min={60} step={60} value={config.duration_s} onChange={(e) => set({ duration_s: Number(e.target.value) })} /></label>
            <label>Speed (× real time, 0 = max)<input type="number" min={0} max={1000} value={config.speed} onChange={(e) => set({ speed: Number(e.target.value) })} /></label>
          </div>
        </fieldset>

        <fieldset disabled={running}>
          <legend>Emergency mission and incident (optional)</legend>
          <label className="check">
            <input type="checkbox" checked={!!m} onChange={(e) => set({
              mission: e.target.checked ? { origin: defaults?.origin ?? edgeIds[0], destination: defaults?.destination ?? edgeIds[1], corridor: true, dispatch_s: 60 } : null,
            })} />
            Plan an ambulance mission
          </label>
          {m && (
            <div className="row">
              <label>From<select value={m.origin} onChange={(e) => set({ mission: { ...m, origin: e.target.value } })}>{edgeIds.map((id) => <option key={id}>{id}</option>)}</select></label>
              <label>To<select value={m.destination} onChange={(e) => set({ mission: { ...m, destination: e.target.value } })}>{edgeIds.map((id) => <option key={id}>{id}</option>)}</select></label>
              <label>Dispatch at (s)<input type="number" min={0} value={m.dispatch_s} onChange={(e) => set({ mission: { ...m, dispatch_s: Number(e.target.value) } })} /></label>
              <label className="check"><input type="checkbox" checked={m.corridor} onChange={(e) => set({ mission: { ...m, corridor: e.target.checked } })} />Corridor</label>
            </div>
          )}
          <label className="check">
            <input type="checkbox" checked={!!inc} onChange={(e) => set({ incident: e.target.checked ? { edge_id: "B1C1", time_s: 120 } : null })} />
            Plan a road closure
          </label>
          {inc && (
            <div className="row">
              <label>Road<select value={inc.edge_id} onChange={(e) => set({ incident: { ...inc, edge_id: e.target.value } })}>{edgeIds.map((id) => <option key={id}>{id}</option>)}</select></label>
              <label>At (s)<input type="number" min={0} value={inc.time_s} onChange={(e) => set({ incident: { ...inc, time_s: Number(e.target.value) } })} /></label>
            </div>
          )}
        </fieldset>
      </section>

      <section className="card">
        <h2>Validation summary {checking && <small className="muted">checking…</small>}</h2>
        <ul className="checks" data-testid="checks">
          {(checks ?? []).map((c, i) => (
            <li key={i} className={`check-${c.level}`}>
              <b aria-label={c.level}>{LEVEL_ICON[c.level]}</b>
              <span><small>{c.field}</small> {c.message}</span>
            </li>
          ))}
        </ul>
        <p className="muted">{errors ? `${errors} error(s): Start stays disabled until they are fixed. The API refuses the same errors.` : "No errors. Warnings and notes stay visible after the start."}</p>
        <div className="buttons">
          <button className="primary" disabled={busy || running || errors > 0 || checks === null || checking}
            onClick={() => act(() => api.start(config), () => { go("overview"); return "Run started"; })}>
            Validate and start run
          </button>
          {running && <span className="muted">A run is active ({state.status}); stop it on G02 first.</span>}
        </div>
      </section>
    </main>
  );
}
