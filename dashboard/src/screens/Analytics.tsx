import { useEffect, useMemo, useState } from "react";
import type { Shared } from "../App";
import { api, downloadExport } from "../api";
import { StripPlot } from "../charts";
import { LEVEL_ICON } from "../common";
import type { Comparison, RunRow, StoreSummary } from "../types";

const f = (v: number | null | undefined, nd = 2) => (v === null || v === undefined ? "–" : v.toFixed(nd));
const PREFERRED = ["travel_time_mean_s", "waiting_time_mean_s", "amb_travel_time_s", "queue_mean_veh", "throughput_veh"];

/** G05 Comparative analytics over the experiment store: comparability (FR-18) before numbers,
 *  every run as a dot, failed runs listed, export (FR-19). */
export function AnalyticsScreen({ act, busy }: Shared) {
  const [summary, setSummary] = useState<StoreSummary | null>(null);
  const [study, setStudy] = useState("results/phase4/comparison");
  const [profile, setProfile] = useState("heavy");
  const [groupBy, setGroupBy] = useState("arm");
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [metric, setMetric] = useState("travel_time_mean_s");
  const [err, setErr] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => { api.storeSummary().then(setSummary).catch((e) => setErr(e.message)); }, [reload]);
  useEffect(() => {
    api.runs({ study, profile: profile || undefined }).then((r) => { setRuns(r); setExcluded(new Set()); })
      .catch((e) => setErr(e.message));
  }, [study, profile, reload]);
  const selected = useMemo(() => runs.filter((r) => !excluded.has(r.run_key)).map((r) => r.run_key), [runs, excluded]);
  useEffect(() => {
    if (!selected.length) { setCmp(null); return; }
    api.compare(selected, groupBy).then((c) => {
      setCmp(c);
      const names = Object.keys(c.metrics);
      if (!names.includes(metric)) setMetric(PREFERRED.find((p) => names.includes(p)) ?? names[0] ?? "");
    }).catch((e) => setErr(e.message));
  }, [selected, groupBy]); // eslint-disable-line

  const profiles = useMemo(() => [...new Set(runs.map((r) => r.profile))], [runs]);
  const md = cmp?.metrics[metric];
  const groupNames = md ? Object.keys(md.groups) : [];
  const seeds = useMemo(() => {
    const by: Record<string, Set<number>> = {};
    for (const r of runs) if (!excluded.has(r.run_key)) (by[String((r as any)[groupBy])] ??= new Set()).add(r.seed ?? -1);
    return by;
  }, [runs, excluded, groupBy]);

  return (
    <main className="page">
      <section className="card filters">
        <div className="row wrap">
          <label>Study (folder of runs)
            <select value={study} onChange={(e) => { setStudy(e.target.value); setProfile(""); }}>
              {summary?.studies.map((s) => <option key={s.study + s.source} value={s.study}>{s.study} ({s.runs} runs, {s.source})</option>)}
            </select>
          </label>
          <label>Demand profile
            <select value={profile} onChange={(e) => setProfile(e.target.value)}>
              <option value="">all (mixes demand levels)</option>
              {["light", "medium", "heavy", "uneven"].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label>Group by
            <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
              <option value="arm">experiment arm</option><option value="controller">controller</option><option value="profile">profile</option>
            </select>
          </label>
          <label>Metric
            <select value={metric} onChange={(e) => setMetric(e.target.value)}>
              {cmp && Object.entries(cmp.metrics).map(([k, v]) => <option key={k} value={k}>{v.label === k ? k : `${v.label} (${k})`}</option>)}
            </select>
          </label>
        </div>
        <p className="muted">
          Store: {summary ? `${summary.runs} runs, ${summary.metric_samples} metric samples, ${summary.missions} missions, ${summary.video_jobs} video jobs` : "…"} ·
          {" "}{selected.length} of {runs.length} runs selected{profiles.length > 1 ? ` · profiles ${profiles.join(", ")}` : ""}
          {" "}<button className="link" disabled={busy} onClick={() => act(api.storeImport, () => { setReload((x) => x + 1); return "Run folders re-imported"; })}>re-import run folders</button>
        </p>
      </section>

      {cmp && (
        <section className={`card comparability ${cmp.warnings.length ? "has-warnings" : "ok"}`} data-testid="comparability">
          <h2>Comparability (FR-18)</h2>
          {cmp.warnings.length === 0
            ? <p><b>✓</b> Same network, demand generator, warm-up, measurement window and metric version; seeds matched across groups.</p>
            : <ul className="checks">{cmp.warnings.map((w, i) => <li key={i} className={`check-${w.level}`}><b>{LEVEL_ICON[w.level]}</b><span>{w.message}</span></li>)}</ul>}
        </section>
      )}

      <div className="two-col">
        <section className="card">
          <h2>{md ? `${md.label} (${md.unit})` : "Metric"}</h2>
          {md && (
            <>
              <p className="muted">
                {md.lower_is_better === true ? "Lower is better. " : md.lower_is_better === false ? "Higher is better. " : ""}
                One dot per run; bar = mean; line = 95 % t interval over runs. Reference for paired differences: <b>{cmp?.reference}</b>.
              </p>
              <StripPlot unit={md.unit} ariaLabel={`${md.label} per run, grouped by ${groupBy}`}
                groups={groupNames.map((g) => ({
                  name: g, mean: md.groups[g].mean, ci95: md.groups[g].ci95, n: md.groups[g].n,
                  points: md.groups[g].points.map((p) => ({ label: `${p.profile} seed ${p.seed}`, value: p.value })),
                }))} />
              <table className="tbl">
                <caption>Per group ({md.unit}) and paired difference vs {cmp?.reference} on matched (profile, seed)</caption>
                <thead><tr><th>{groupBy}</th><th>n</th><th>mean</th><th>SD</th><th>95 % CI ±</th><th>Δ vs ref</th><th>Δ 95 % CI ±</th></tr></thead>
                <tbody>
                  {groupNames.map((g) => {
                    const s = md.groups[g], d = md.paired_vs_reference[g];
                    return (
                      <tr key={g}><td>{g}</td><td>{s.n}{s.missing ? ` (+${s.missing} missing)` : ""}</td><td>{f(s.mean)}</td><td>{f(s.sd)}</td><td>{f(s.ci95)}</td>
                        <td>{g === cmp?.reference ? "reference" : d ? `${d.mean! >= 0 ? "+" : ""}${f(d.mean)} (n=${d.n})` : "no matched runs"}</td><td>{d ? f(d.ci95) : "–"}</td></tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
          {!md && <p className="muted">Select runs with a metric in common.</p>}
        </section>

        <section className="card">
          <h2>Runs, seed coverage and export</h2>
          <div className="kv-grid">
            {Object.entries(seeds).map(([g, s]) => (
              <div className="kv" key={g}><span>{g}</span><b>seeds {[...s].sort((a, b) => a - b).join(", ")}</b></div>
            ))}
          </div>
          <p className="muted">Failed or stopped runs stay listed and are left out of the statistics{cmp?.excluded.length ? `: ${cmp.excluded.length} excluded` : " (none in this selection)"}.</p>
          <div className="buttons">
            <button className="primary" disabled={!selected.length} onClick={() => act(() => downloadExport(selected, "json"), () => `Exported ${selected.length} runs (JSON, manzil.export v1)`)}>Export JSON</button>
            <button disabled={!selected.length} onClick={() => act(() => downloadExport(selected, "csv"), () => `Exported ${selected.length} runs (CSV)`)}>Export CSV</button>
          </div>
          <div className="run-list">
            <table className="tbl">
              <thead><tr><th /><th>arm</th><th>profile</th><th>seed</th><th>status</th><th>run folder</th></tr></thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_key} className={r.status !== "completed" ? "failed" : ""}>
                    <td><input type="checkbox" aria-label={`include ${r.run_key}`} checked={!excluded.has(r.run_key)} onChange={(e) => {
                      const n = new Set(excluded);
                      if (e.target.checked) n.delete(r.run_key); else n.add(r.run_key);
                      setExcluded(n);
                    }} /></td>
                    <td>{r.arm}</td><td>{r.profile}</td><td>{r.seed}</td>
                    <td>{r.status === "completed" ? "✓ completed" : `✕ ${r.termination}`}</td>
                    <td className="small">{r.run_key.split("/").slice(-1)[0]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {err && <div className="alert">{err}</div>}
        </section>
      </div>
    </main>
  );
}
