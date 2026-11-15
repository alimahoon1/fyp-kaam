import type { Connection } from "./api";
import type { LiveState, Warning } from "./types";

export const fmtTime = (s?: number | null) => {
  if (s === undefined || s === null) return "–";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
};

export const ACTIVE = new Set(["starting", "running", "paused"]);

export const CORRIDOR_LABEL: Record<string, string> = {
  REQUESTED: "requested",
  SAFE_TRANSITION: "safe transition",
  ACTIVE_PRIORITY: "green for ambulance",
  PASSAGE: "ambulance passing",
  RECOVERY: "recovering",
  CANCELLED: "cancelled",
  IDLE: "idle",
};

/** Text icon per level, so colour is never the only signal. */
export const LEVEL_ICON: Record<string, string> = { ok: "✓", info: "i", warning: "!", error: "✕" };

const WARNING_TITLE: Record<string, string> = {
  stale: "STALE",
  invalid: "INVALID",
  disconnected: "DISCONNECTED",
  fallback: "FALLBACK",
};

/** FR-16: every warning of the live view, plus the browser's own connection state. */
export function collectWarnings(state: LiveState, conn: Connection, lastMsgAge: number): Warning[] {
  const out = [...(state.warnings ?? [])];
  if (conn === "disconnected") {
    out.unshift({
      code: "disconnected",
      level: "error",
      message: "the dashboard cannot reach the Manzil API; the values shown are the last ones received",
    });
  } else if (ACTIVE.has(state.status) && lastMsgAge > 3 && !out.some((w) => w.code === "stale")) {
    out.unshift({ code: "stale", level: "error", message: `no update received for ${lastMsgAge.toFixed(0)} s` });
  }
  return out;
}

export function WarningBanner({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) return null;
  return (
    <div className="warnings" role="alert" data-testid="warnings">
      {warnings.map((w, i) => (
        <div key={`${w.code}-${i}`} className={`warning ${w.level} code-${w.code}`}>
          <b className="wcode">{LEVEL_ICON[w.level] ?? "!"} {WARNING_TITLE[w.code] ?? w.code.toUpperCase()}</b>
          <span>{w.message}{w.since_s != null ? ` (since ${fmtTime(w.since_s)})` : ""}</span>
        </div>
      ))}
    </div>
  );
}

/** Source, step and age of the values on screen (NFR-04). */
export function Freshness({ state, conn }: { state: LiveState; conn: Connection }) {
  if (state.status === "idle") return <span className="muted">no run</span>;
  const age = state.age_s;
  return (
    <span className="freshness muted">
      source <b>{state.source_mode === "sumo" ? "SUMO (exact simulated state)" : state.source_mode ?? "–"}</b>
      {" · "}step <b>{state.effective_step ?? "–"}</b>
      {" · "}age <b>{age != null ? `${age.toFixed(1)} s` : "–"}</b>
      {" · "}link <b>{conn}</b>
    </span>
  );
}

export function Kv({ k, v, small }: { k: string; v: React.ReactNode; small?: React.ReactNode }) {
  return (
    <div className="kv">
      <span>{k}</span>
      <b>{v}{small ? <small> {small}</small> : null}</b>
    </div>
  );
}
