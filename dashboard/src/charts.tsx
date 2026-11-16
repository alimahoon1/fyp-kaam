import { useMemo, useRef, useState } from "react";

// Small SVG charts for G02, G03 and G05. One y-axis per chart; categorical colours in fixed
// slot order (validated for the dark surface, 3 slots all-pairs); a legend for >= 2 series
// plus direct end labels; a hover tooltip on every chart.

export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

const niceTicks = (lo: number, hi: number, n = 4): number[] => {
  if (!isFinite(lo) || !isFinite(hi)) return [];
  if (hi === lo) hi = lo + 1;
  const raw = (hi - lo) / n;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
};

const fmt = (v: number | null | undefined, nd = 1) =>
  v === null || v === undefined || !isFinite(v) ? "–" : Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(nd);

export interface Series {
  name: string;
  points: [number, number | null][]; // x, y (null = missing, drawn as a gap)
  dashed?: boolean;
}

interface LineProps {
  series: Series[];
  xLabel: string;
  yLabel: string;
  height?: number;
  xFormat?: (x: number) => string;
  ariaLabel: string;
}

/** Line chart with a crosshair tooltip (missing values leave a gap, never drop to zero). */
export function LineChart({ series, xLabel, yLabel, height = 170, xFormat = (x) => fmt(x, 0), ariaLabel }: LineProps) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 560, H = height, L = 44, R = series.length > 1 ? 70 : 14, T = 10, B = 30;
  const xs = series.flatMap((s) => s.points.map((p) => p[0]));
  const ys = series.flatMap((s) => s.points.map((p) => p[1]).filter((v): v is number => v !== null));
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y1 = ys.length ? Math.max(...ys) : 1;
  const yt = niceTicks(0, y1 || 1);
  const ymax = yt.length ? yt[yt.length - 1] : 1;
  const sx = (x: number) => L + ((x - x0) / (x1 - x0 || 1)) * (W - L - R);
  const sy = (y: number) => T + (1 - y / (ymax || 1)) * (H - T - B);
  const allX = useMemo(() => [...new Set(xs)].sort((a, b) => a - b), [series]); // eslint-disable-line
  if (!xs.length) return <div className="chart-empty">No data yet</div>;

  const path = (pts: [number, number | null][]) => {
    let d = "", pen = false;
    for (const [x, y] of pts) {
      if (y === null) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${sx(x).toFixed(1)},${sy(y).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const onMove = (e: React.PointerEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = allX[0];
    for (const x of allX) if (Math.abs(sx(x) - px) < Math.abs(sx(best) - px)) best = x;
    setHover(best);
  };
  const hx = hover !== null ? sx(hover) : 0;
  return (
    <div className="chart">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}
        onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
        {yt.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={sy(t)} y2={sy(t)} className="grid" />
            <text x={L - 6} y={sy(t) + 3} className="tick" textAnchor="end">{fmt(t, 0)}</text>
          </g>
        ))}
        {niceTicks(x0, x1, 5).map((t) => (
          <text key={t} x={sx(t)} y={H - B + 14} className="tick" textAnchor="middle">{xFormat(t)}</text>
        ))}
        <text x={W - R} y={H - 3} className="axis-label" textAnchor="end">{xLabel}</text>
        <text x={L} y={T - 1} className="axis-label">{yLabel}</text>
        {series.map((s, i) => (
          <path key={s.name} d={path(s.points)} fill="none" stroke={SERIES[i % SERIES.length]}
            strokeWidth={2} strokeLinejoin="round" strokeDasharray={s.dashed ? "5 4" : undefined} />
        ))}
        {series.length > 1 && series.map((s) => {
          const last = [...s.points].reverse().find((p) => p[1] !== null);
          return last ? (
            <text key={s.name} x={sx(last[0]) + 6} y={sy(last[1] as number) + 4} className="direct-label">{s.name}</text>
          ) : null;
        })}
        {hover !== null && (
          <g>
            <line x1={hx} x2={hx} y1={T} y2={H - B} className="crosshair" />
            {series.map((s, i) => {
              const p = s.points.find((q) => q[0] === hover);
              return p && p[1] !== null ? (
                <circle key={s.name} cx={hx} cy={sy(p[1])} r={4} fill={SERIES[i % SERIES.length]} className="ringed" />
              ) : null;
            })}
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="tooltip" style={{ left: `${(hx / W) * 100}%` }}>
          <b>{xLabel} {xFormat(hover)}</b>
          {series.map((s, i) => {
            const p = s.points.find((q) => q[0] === hover);
            return (
              <div key={s.name}><i className="sw-dot" style={{ background: SERIES[i % SERIES.length] }} />
                {s.name}: {fmt(p?.[1])}</div>
            );
          })}
        </div>
      )}
      {series.length > 1 && (
        <div className="chart-legend">
          {series.map((s, i) => (
            <span key={s.name}><i className={`sw-line ${s.dashed ? "dashed" : ""}`} style={{ borderColor: SERIES[i % SERIES.length] }} />{s.name}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export interface StripGroup {
  name: string;
  mean: number | null;
  ci95: number | null;
  n: number;
  points: { label: string; value: number | null }[];
}

/** One dot per run, with the group mean and its 95 % interval (G05). Groups are rows. */
export function StripPlot({ groups, unit, ariaLabel }: { groups: StripGroup[]; unit: string; ariaLabel: string }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const W = 560, rowH = 38, L = 120, R = 20, T = 8, B = 30;
  const H = T + B + rowH * groups.length;
  const vals = groups.flatMap((g) => [
    ...g.points.map((p) => p.value).filter((v): v is number => v !== null),
    ...(g.mean !== null && g.ci95 !== null ? [g.mean - g.ci95, g.mean + g.ci95] : []),
  ]);
  if (!vals.length) return <div className="chart-empty">No values for this metric</div>;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1;
  lo -= pad; hi += pad;
  const ticks = niceTicks(lo, hi, 5).filter((t) => t >= lo && t <= hi);
  const sx = (v: number) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} onPointerLeave={() => setTip(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={sx(t)} x2={sx(t)} y1={T} y2={H - B} className="grid" />
            <text x={sx(t)} y={H - B + 14} className="tick" textAnchor="middle">{fmt(t)}</text>
          </g>
        ))}
        <text x={W - R} y={H - 3} className="axis-label" textAnchor="end">{unit}</text>
        {groups.map((g, i) => {
          const cy = T + rowH * i + rowH / 2;
          const c = SERIES[i % SERIES.length];
          return (
            <g key={g.name}>
              <text x={L - 10} y={cy + 4} className="row-label" textAnchor="end">{g.name} <tspan className="muted">n={g.n}</tspan></text>
              {g.points.map((p, j) => p.value === null ? null : (
                <circle key={j} cx={sx(p.value)} cy={cy - 6 + ((j * 7) % 13) - 0} r={4} fill={c} fillOpacity={0.55}
                  className="ringed"
                  onPointerEnter={() => setTip({ x: sx(p.value as number), y: cy, text: `${g.name} · ${p.label}: ${fmt(p.value, 2)} ${unit}` })} />
              ))}
              {g.mean !== null && (
                <g onPointerEnter={() => setTip({ x: sx(g.mean as number), y: cy, text: `${g.name}: mean ${fmt(g.mean, 2)} ${unit}` + (g.ci95 !== null ? ` ± ${fmt(g.ci95, 2)} (95 % CI)` : " (n=1, no interval)") })}>
                  {g.ci95 !== null && (
                    <line x1={sx(g.mean - g.ci95)} x2={sx(g.mean + g.ci95)} y1={cy + 10} y2={cy + 10} stroke={c} strokeWidth={2} />
                  )}
                  <rect x={sx(g.mean) - 1.5} y={cy + 3} width={3} height={14} rx={1.5} fill="var(--text)" />
                  <rect x={sx(g.mean) - 10} y={cy - 12} width={20} height={32} fill="transparent" />
                </g>
              )}
            </g>
          );
        })}
      </svg>
      {tip && <div className="tooltip" style={{ left: `${(tip.x / W) * 100}%`, top: `${(tip.y / H) * 100}%` }}>{tip.text}</div>}
      <div className="chart-legend">
        <span><i className="sw-dot" style={{ background: "var(--muted)" }} />one run</span>
        <span><i className="sw-tick" />mean</span>
        <span><i className="sw-line" style={{ borderColor: "var(--muted)" }} />95 % t interval</span>
      </div>
    </div>
  );
}
