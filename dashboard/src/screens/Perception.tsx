import { useEffect, useState } from "react";
import type { Shared } from "../App";
import { api } from "../api";
import { LineChart } from "../charts";
import { Freshness, Kv } from "../common";
import { MapView } from "../MapView";
import type { Observation, VideoJob } from "../types";

const n1 = (v: number | null | undefined, nd = 1) => (v === null || v === undefined ? "–" : v.toFixed(nd));

/** G03: (a) one intersection from the live SUMO run (exact simulated values) and (b) prepared
 *  perception results from recorded video with their provenance. The two are separate
 *  evidence paths (D2): no video drives the SUMO run. */
export function PerceptionScreen({ net, state, conn }: Shared) {
  const [tls, setTls] = useState<string>("B1");
  const [jobs, setJobs] = useState<VideoJob[]>([]);
  const [jobId, setJobId] = useState("detrac/MVI_40714");
  const [job, setJob] = useState<VideoJob | null>(null);
  const [obs, setObs] = useState<Observation[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.jobs().then(setJobs).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    setJob(null);
    setObs([]);
    api.job(jobId).then(setJob).catch((e) => setErr(e.message));
    api.observations(jobId).then(setObs).catch(() => {});
  }, [jobId]);

  const sig = state.signals?.[tls];
  const approaches = state.approaches?.[tls] ?? [];
  const controls = (state.applied_controls ?? []).filter((a) => a.tls === tls).slice(-8).reverse();
  const live = state.status !== "idle";
  const queue = obs.filter((o) => o.name === "queue_proxy");
  const counts = obs.filter((o) => o.name.startsWith("count_"));
  const frame = job?.artifacts?.find((a) => a.type === "frame");
  const s = job?.summary ?? {};

  return (
    <main className="page">
      <div className="two-col">
        <section className="card">
          <h2>Intersection detail · {tls}</h2>
          <p className="muted">Source: the live SUMO run (exact simulated state, confidence 1.0). Click a junction on the map to change it.</p>
          {live ? <Freshness state={state} conn={conn} /> : <p className="muted">No run: start one on G01 to see live values.</p>}
          <div className="mini-map">
            {net && <MapView net={net} state={state} selected={null} onSelect={() => {}} selectedTls={tls} onSelectTls={setTls} />}
          </div>
          {sig && (
            <div className="kv-grid">
              <Kv k="Signal state" v={<code>{sig.state}</code>} />
              <Kv k="Green phase" v={sig.phase ?? "clearance (yellow / all-red)"} small={`for ${sig.elapsed_s} s`} />
              <Kv k="Owner" v={sig.owner === "CORRIDOR" ? "CORRIDOR (ambulance priority)" : "NORMAL (controller)"} />
            </div>
          )}
          <table className="tbl">
            <caption>Approaches (incoming roads)</caption>
            <thead><tr><th>approach</th><th>vehicles</th><th>queue (veh)</th><th>waiting (s)</th><th>speed (m/s)</th><th>occupancy (%)</th></tr></thead>
            <tbody>
              {approaches.map((a) => (
                <tr key={a.approach_id}><td>{a.approach_id}</td><td>{a.count}</td><td>{a.queue}</td><td>{n1(a.wait_s, 0)}</td>
                  <td>{a.speed_mps === null ? <span className="muted" title="empty approach: missing, not zero">– (empty)</span> : n1(a.speed_mps)}</td><td>{n1(a.occupancy_pct)}</td></tr>
              ))}
              {!approaches.length && <tr><td colSpan={6} className="muted">no live values</td></tr>}
            </tbody>
          </table>
          <table className="tbl">
            <caption>Requested vs applied controls (FR-07), newest first</caption>
            <thead><tr><th>step</th><th>by</th><th>requested</th><th>applied</th><th>safety filter</th><th>reason</th></tr></thead>
            <tbody>
              {controls.map((c) => (
                <tr key={c.request_id}><td>{c.effective_step}</td><td>{c.controller}</td><td>{c.requested_phase}</td>
                  <td>{c.applied_phase ?? "rejected"}</td><td>{c.intervention}</td><td>{c.reason}</td></tr>
              ))}
              {!controls.length && <tr><td colSpan={6} className="muted">no recent switches at {tls}</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="card">
          <h2>Prepared perception results (recorded video)</h2>
          <div className="info-box">
            Recorded video processed offline on Kaggle; <b>not live</b> and <b>not connected to the SUMO run</b>.
            Counts are line crossings in the image; the queue is a stopped-vehicle proxy in view, not a per-lane queue (no calibration).
          </div>
          {err && <div className="alert">{err}</div>}
          <label>Video job ({jobs.length} prepared)
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              {jobs.map((j) => (
                <option key={j.job_id} value={j.job_id}>{j.clip} · {j.summary.true_total} true / {j.summary.pred_total} counted{j.artifacts?.length ? "" : ""}</option>
              ))}
            </select>
          </label>
          {job && (
            <>
              <div className="kv-grid">
                <Kv k="Dataset" v={job.dataset} />
                <Kv k="Clip" v={job.clip} small={`${job.frames} frames, ${n1(job.seconds)} s`} />
                <Kv k="Model" v={job.model_version} />
                <Kv k="Model sha256" v={<code>{job.model_sha256?.slice(0, 16)}…</code>} />
                <Kv k="Tracker" v={job.tracker} />
                <Kv k="Produced by" v={job.produced_by} />
                <Kv k="Ground truth" v={job.label_status} />
                <Kv k="Freshness" v="recorded: processed 12 Nov 2026" small="(not a live stream)" />
                <Kv k="Calibration" v="unavailable" small="(image-space proxies only)" />
                <Kv k="Processing speed" v={`${n1(job.fps)} frames/s`} small="(detection + tracking, Tesla T4)" />
              </div>
              <table className="tbl">
                <caption>Line-crossing counts, counted vs ground truth (veh)</caption>
                <thead><tr><th>measure</th><th>counted</th><th>true</th><th>error</th></tr></thead>
                <tbody>
                  <tr><td><b>all vehicles</b></td><td>{s.pred_total}</td><td>{s.true_total}</td><td>{s.pred_total - s.true_total >= 0 ? "+" : ""}{s.pred_total - s.true_total}</td></tr>
                  {counts.map((o) => (
                    <tr key={o.name}><td>{o.name.replace("count_", "")}</td><td>{o.value}</td><td>{o.reference}</td>
                      <td>{o.value !== null && o.reference !== null ? `${o.value - o.reference >= 0 ? "+" : ""}${o.value - o.reference}` : "–"}</td></tr>
                  ))}
                </tbody>
              </table>
              <h3>Queue proxy over the clip (stopped vehicles in view)</h3>
              <LineChart ariaLabel={`Estimated and true stopped vehicles over time in ${job.clip}`}
                xLabel="clip time (s)" yLabel="stopped veh" height={170}
                series={[
                  { name: "estimated", points: queue.map((o) => [o.observed_at_s, o.value]) },
                  { name: "true", points: queue.map((o) => [o.observed_at_s, o.reference]), dashed: true },
                ]} />
              <p className="muted">Mean per-frame error {n1(s.queue_mae_per_frame, 2)} stopped veh; mean queue {n1(s.pred_queue_mean, 2)} estimated vs {n1(s.true_queue_mean, 2)} true.</p>
              {frame ? (
                <figure className="frame">
                  <img src={`/api/files/${frame.uri}`} alt={`Tracked frame from ${job.clip}`} />
                  <figcaption>{frame.uri} · sha256 {frame.sha256?.slice(0, 12)}… · {frame.provenance}</figcaption>
                </figure>
              ) : <p className="muted">No rendered frames kept in the repository for this clip (only MVI_40714 has sample frames).</p>}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
