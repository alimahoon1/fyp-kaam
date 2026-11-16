import { useEffect, useRef, useState } from "react";
import { api, subscribeState, type Connection } from "./api";
import { ACTIVE, collectWarnings, fmtTime, WarningBanner } from "./common";
import type { LiveState, Network, Options, RunConfig } from "./types";
import { ConfigScreen } from "./screens/Config";
import { OverviewScreen } from "./screens/Overview";
import { PerceptionScreen } from "./screens/Perception";
import { EmergencyScreen } from "./screens/Emergency";
import { AnalyticsScreen } from "./screens/Analytics";

// The five screens of D2 Section 4.8 (W5). Navigation follows Figure 4.x: configure (G01) ->
// overview (G02) <-> perception (G03) / emergency (G04); completed runs -> analytics (G05).
export const SCREENS = [
  { id: "config", code: "G01", title: "Configuration" },
  { id: "overview", code: "G02", title: "Traffic overview" },
  { id: "perception", code: "G03", title: "Perception & intersection" },
  { id: "emergency", code: "G04", title: "Emergency dispatch" },
  { id: "analytics", code: "G05", title: "Comparative analytics" },
] as const;
export type ScreenId = (typeof SCREENS)[number]["id"];

const fromHash = (): ScreenId => {
  const h = location.hash.replace("#/", "").replace("#", "");
  return (SCREENS.find((s) => s.id === h)?.id ?? "overview") as ScreenId;
};

export interface Shared {
  net: Network | null;
  opts: Options | null;
  state: LiveState;
  conn: Connection;
  config: RunConfig;
  setConfig: (c: RunConfig) => void;
  go: (s: ScreenId) => void;
  act: (fn: () => Promise<unknown>, ok?: (r: any) => string) => Promise<void>;
  busy: boolean;
}

export function App() {
  const [screen, setScreen] = useState<ScreenId>(fromHash());
  const [net, setNet] = useState<Network | null>(null);
  const [opts, setOpts] = useState<Options | null>(null);
  const [state, setState] = useState<LiveState>({ status: "idle", version: 0 });
  const [conn, setConn] = useState<Connection>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<RunConfig>({
    controller: "fixed_time", profile: "medium", seed: 0, duration_s: 3600, speed: 10,
    mission: null, incident: null,
  });
  const lastMsg = useRef(Date.now());
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const onHash = () => setScreen(fromHash());
    window.addEventListener("hashchange", onHash);
    api.network().then(setNet).catch((e) => setError(`Cannot reach the API: ${e.message}`));
    api.options().then((o) => {
      setOpts(o);
      setConfig((c) => ({ ...c, controller: o.defaults.controller, profile: o.defaults.profile }));
    }).catch(() => {});
    const unsub = subscribeState((s) => { lastMsg.current = Date.now(); setState(s); }, setConn);
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { unsub(); window.removeEventListener("hashchange", onHash); window.clearInterval(tick); };
  }, []);

  const go = (s: ScreenId) => { location.hash = `#/${s}`; setScreen(s); };
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

  const warnings = collectWarnings(state, conn, (now - lastMsg.current) / 1000);
  const progress = state.end_s ? Math.min(100, ((state.sim_time_s ?? 0) / state.end_s) * 100) : 0;
  const shared: Shared = { net, opts, state, conn, config, setConfig, go, act, busy };

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">M</span>
          <div>
            <h1>Manzil</h1>
            <p>Traffic &amp; emergency routing · {net?.scenario ?? "…"} (SUMO)</p>
          </div>
        </div>
        <nav aria-label="Screens">
          {SCREENS.map((s) => (
            <a key={s.id} href={`#/${s.id}`} className={screen === s.id ? "on" : ""}
              aria-current={screen === s.id ? "page" : undefined}>
              <small>{s.code}</small> {s.title}
            </a>
          ))}
        </nav>
        <div className="header-stats">
          <span className={`pill ${state.status}`} data-testid="status">{state.status}</span>
          <span className="clock">sim <b>{fmtTime(state.sim_time_s)}</b> / {fmtTime(state.end_s)}</span>
          {state.config && ACTIVE.has(state.status) && (
            <span className="muted">{state.config.controller} · {state.config.profile} · seed {state.config.seed}</span>
          )}
        </div>
      </header>
      <div className="progress"><div style={{ width: `${progress}%` }} /></div>
      <WarningBanner warnings={warnings} />
      {(error || state.error) && <div className="alert top">{error ?? state.error}</div>}
      {notice && !error && <div className="notice top" onClick={() => setNotice(null)}>{notice} <small>(click to hide)</small></div>}

      {screen === "config" && <ConfigScreen {...shared} />}
      {screen === "overview" && <OverviewScreen {...shared} />}
      {screen === "perception" && <PerceptionScreen {...shared} />}
      {screen === "emergency" && <EmergencyScreen {...shared} />}
      {screen === "analytics" && <AnalyticsScreen {...shared} />}
    </div>
  );
}
