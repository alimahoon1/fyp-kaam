import { useMemo } from "react";
import type { LiveState, Network, Point } from "./types";

// SUMO's y axis points up and SVG's points down, so every point is drawn at (x, -y).
const pt = ([x, y]: Point) => `${x},${-y}`;
const poly = (shape: Point[]) => shape.map(pt).join(" ");

const SIGNAL_COLOURS: Record<string, string> = {
  G: "var(--sig-green)",
  g: "var(--sig-green-minor)",
  y: "var(--sig-yellow)",
  Y: "var(--sig-yellow)",
  r: "var(--sig-red)",
  R: "var(--sig-red)",
  u: "var(--sig-yellow)",
};

const CORRIDOR_COLOURS: Record<string, string> = {
  REQUESTED: "var(--cor-requested)",
  SAFE_TRANSITION: "var(--cor-transition)",
  ACTIVE_PRIORITY: "var(--cor-active)",
  RECOVERY: "var(--cor-recovery)",
};

interface StopBar {
  key: string;
  tls: string;
  index: number;
  a: Point;
  b: Point;
}

/** One short bar per signal link, side by side across the stop line of its incoming lane. */
function stopBars(net: Network): StopBar[] {
  const lanes = new Map<string, { width: number; shape: Point[] }>();
  for (const e of net.edges) for (const l of e.lanes) lanes.set(l.id, l);
  const bars: StopBar[] = [];
  for (const t of net.tls) {
    const byLane = new Map<string, number[]>();
    for (const lk of t.links) byLane.set(lk.from_lane, [...(byLane.get(lk.from_lane) ?? []), lk.index]);
    for (const [laneId, idx] of byLane) {
      const lane = lanes.get(laneId);
      if (!lane || lane.shape.length < 2) continue;
      const [x1, y1] = lane.shape[lane.shape.length - 2];
      const [x2, y2] = lane.shape[lane.shape.length - 1];
      const len = Math.hypot(x2 - x1, y2 - y1) || 1;
      const [dx, dy] = [(x2 - x1) / len, (y2 - y1) / len];
      const [nx, ny] = [dy, -dx]; // right-hand normal
      const w = lane.width;
      const back = 0.8; // draw the bar just before the stop line
      const [cx, cy] = [x2 - dx * back, y2 - dy * back];
      idx.sort((p, q) => p - q);
      // SUMO numbers a lane's links from right to left.
      idx.forEach((index, k) => {
        const s0 = w / 2 - (k * w) / idx.length;
        const s1 = w / 2 - ((k + 1) * w) / idx.length;
        bars.push({
          key: `${t.id}-${index}`,
          tls: t.id,
          index,
          a: [cx + nx * s0, cy + ny * s0],
          b: [cx + nx * s1, cy + ny * s1],
        });
      });
    }
  }
  return bars;
}

interface Props {
  net: Network;
  state: LiveState;
  selected: string | null;
  onSelect: (edgeId: string | null) => void;
}

export function MapView({ net, state, selected, onSelect }: Props) {
  const bars = useMemo(() => stopBars(net), [net]);
  const [xmin, ymin, xmax, ymax] = net.bounds;
  const pad = 20;
  const viewBox = `${xmin - pad} ${-ymax - pad} ${xmax - xmin + 2 * pad} ${ymax - ymin + 2 * pad}`;
  const halting = state.edge_halting ?? {};
  const closed = new Set(state.closed_edges ?? []);
  const amb = state.ambulance;
  const ambActive = amb && (amb.status === "ACTIVE" || amb.status === "PENDING");
  const route = new Set(ambActive ? amb.route : []);
  const corridor = ambActive ? amb.corridor : {};
  const junctions = new Map(net.junctions.map((j) => [j.id, j]));

  return (
    <svg className="map" viewBox={viewBox} role="img" aria-label="Live road network map">
      {/* junction areas */}
      {net.junctions.map((j) =>
        j.shape.length > 2 ? <polygon key={j.id} points={poly(j.shape)} className="junction" /> : null,
      )}

      {/* lanes, shaded by halting vehicles on the edge */}
      {net.edges.map((e) => {
        const q = halting[e.id] ?? 0;
        const cls = closed.has(e.id) ? "lane closed" : q >= 8 ? "lane jam" : q >= 3 ? "lane busy" : "lane";
        return e.lanes.map((l) => (
          <polyline key={l.id} points={poly(l.shape)} className={cls} strokeWidth={l.width - 0.4} />
        ));
      })}

      {/* the ambulance's current route */}
      {net.edges
        .filter((e) => route.has(e.id))
        .map((e) =>
          e.lanes.map((l) => <polyline key={`r-${l.id}`} points={poly(l.shape)} className="route" />),
        )}

      {/* closed roads */}
      {net.edges
        .filter((e) => closed.has(e.id))
        .map((e) => {
          const s = e.lanes[Math.floor(e.lanes.length / 2)].shape;
          const [x0, y0] = s[0];
          const [x1, y1] = s[s.length - 1];
          const [mx, my] = [(x0 + x1) / 2, (y0 + y1) / 2];
          return (
            <g key={`c-${e.id}`} className="closure">
              <line x1={mx - 6} y1={-my - 6} x2={mx + 6} y2={-my + 6} />
              <line x1={mx - 6} y1={-my + 6} x2={mx + 6} y2={-my - 6} />
            </g>
          );
        })}

      {/* selected road */}
      {net.edges
        .filter((e) => e.id === selected)
        .map((e) =>
          e.lanes.map((l) => <polyline key={`s-${l.id}`} points={poly(l.shape)} className="selected" />),
        )}

      {/* corridor rings at junctions taking part */}
      {Object.entries(corridor).map(([tls, st]) => {
        const t = net.tls.find((x) => x.id === tls);
        const j = t && junctions.get(t.junction);
        if (!j) return null;
        return (
          <circle
            key={`cor-${tls}`}
            cx={j.x}
            cy={-j.y}
            r={16}
            className={`corridor-ring ${st === "REQUESTED" ? "dashed" : ""}`}
            stroke={CORRIDOR_COLOURS[st] ?? "white"}
          />
        );
      })}

      {/* signal heads */}
      {bars.map((b) => {
        const s = state.signals?.[b.tls]?.state;
        const c = s ? SIGNAL_COLOURS[s[b.index]] ?? "var(--sig-off)" : "var(--sig-off)";
        return (
          <line
            key={b.key}
            x1={b.a[0]}
            y1={-b.a[1]}
            x2={b.b[0]}
            y2={-b.b[1]}
            stroke={c}
            className="signal"
          />
        );
      })}

      {/* background vehicles (position = front bumper, angle = degrees clockwise from north) */}
      {(state.vehicles ?? []).map(([x, y, a], i) => (
        <rect key={i} x={-0.9} y={0} width={1.8} height={4.5} className="vehicle"
          transform={`translate(${x},${-y}) rotate(${a})`} />
      ))}

      {/* ambulance */}
      {ambActive && amb.position && (
        <g transform={`translate(${amb.position[0]},${-amb.position[1]})`} className="ambulance">
          <circle r={9} className="amb-halo" />
          <rect x={-1.3} y={0} width={2.6} height={6} transform={`rotate(${amb.position[2]})`} className="amb-body" />
        </g>
      )}

      {/* junction labels */}
      {net.tls.map((t) => {
        const j = junctions.get(t.junction);
        return j ? (
          <text key={`t-${t.id}`} x={j.x + 11} y={-j.y - 11} className="label">
            {t.id}
          </text>
        ) : null;
      })}

      {/* wide invisible hit areas for picking a road */}
      {net.edges.map((e) =>
        e.lanes.map((l) => (
          <polyline
            key={`h-${l.id}`}
            points={poly(l.shape)}
            className="hit"
            strokeWidth={l.width}
            onClick={(ev) => {
              ev.stopPropagation();
              onSelect(e.id === selected ? null : e.id);
            }}
          >
            <title>{e.id}</title>
          </polyline>
        )),
      )}
    </svg>
  );
}
