import { useEffect, useMemo, useState } from 'react'
import { Activity, Ambulance, BarChart3, CircleAlert, Download, Gauge, Map, Pause, Play, RefreshCw, Route, ShieldCheck, Sparkles, Timer, TrafficCone } from 'lucide-react'
import { api } from './api'
import type { Comparison, EdgeState, Perception, State } from './types'

const initialState: State = {
  schemaVersion: '1.0', sourceMode: 'prototype-sim', step: 0, running: false, seed: 104, scenario: 'balanced', controller: 'adaptive',
  nodes: [], edges: [], corridor: {}, mission: null,
  metrics: { totalQueue: 0, meanQueue: 0, meanWaitProxy: 0, throughput: 0, fallbackInterventions: 0 }, events: []
}

function edgeKey(a: string, b: string) { return `${a}>${b}` }

function NetworkMap({ state, onToggleClosure }: { state: State; onToggleClosure: (edge: EdgeState) => void }) {
  const nodes = Object.fromEntries(state.nodes.map(node => [node.id, node]))
  const missionPair = state.mission && state.mission.route.length > 1 ? edgeKey(state.mission.route[0], state.mission.route[1]) : ''
  return <div className="map-wrap">
    <svg className="network-map" viewBox="0 0 680 370" role="img" aria-label="Synthetic six-intersection traffic network">
      <defs>
        <filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        <linearGradient id="routeGradient"><stop stopColor="#ffcf57"/><stop offset="1" stopColor="#ff7452"/></linearGradient>
      </defs>
      {state.edges.map(edge => {
        const a = nodes[edge.source], b = nodes[edge.target]
        if (!a || !b) return null
        const active = state.mission?.route.some((item, index) => edgeKey(item, state.mission!.route[index + 1]) === edge.id || edgeKey(state.mission!.route[index + 1], item) === edge.id)
        return <g key={edge.id} onClick={() => onToggleClosure(edge)} className="road-group" role="button">
          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`road ${edge.closed ? 'closed' : ''} ${active ? 'active-route' : ''}`} />
          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="road-hit" />
          {edge.closed && <text x={(a.x+b.x)/2} y={(a.y+b.y)/2-8} className="closure-label">CLOSED</text>}
        </g>
      })}
      {state.nodes.map(node => {
        const queue = node.queues.EW + node.queues.NS
        const level = queue > 20 ? 'severe' : queue > 12 ? 'busy' : 'clear'
        const corridor = state.corridor[node.id]
        return <g key={node.id} transform={`translate(${node.x},${node.y})`}>
          {corridor && <circle r="29" className="corridor-ring" filter="url(#glow)" />}
          <circle r="19" className={`junction ${level}`} />
          <text y="4" className="junction-id">{node.id.replace('I-0','')}</text>
          <text y="39" className="junction-label">{node.label}</text>
          <rect x="-18" y="-33" width="36" height="12" rx="6" className={`phase phase-${node.signal.displayPhase.toLowerCase()}`} />
          <text y="-24" className="phase-label">{node.signal.displayPhase === 'CLEARANCE' ? 'CLR' : node.signal.phase}</text>
        </g>
      })}
      {state.mission && state.mission.route.length > 1 && (() => {
        const a = nodes[state.mission!.route[0]], b = nodes[state.mission!.route[1]]
        if (!a || !b) return null
        const x = a.x + (b.x-a.x) * state.mission!.progress
        const y = a.y + (b.y-a.y) * state.mission!.progress
        return <g transform={`translate(${x},${y})`} filter="url(#glow)"><circle r="13" className="ambulance-dot"/><text y="4" className="ambulance-mark">+</text></g>
      })()}
    </svg>
    <div className="map-legend"><span><i className="dot clear"/>Flowing</span><span><i className="dot busy"/>Busy</span><span><i className="dot severe"/>Severe</span><span><i className="route-line"/>Mission route</span><span>Click a road to close it</span></div>
    {missionPair && <div className="live-route"><Route size={15}/> Active segment {missionPair.replace('>',' → ')}</div>}
  </div>
}

function Metric({ icon, label, value, note }: { icon: React.ReactNode; label: string; value: string | number; note: string }) {
  return <div className="metric-card"><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></div>
}

export default function App() {
  const [state, setState] = useState<State>(initialState)
  const [playing, setPlaying] = useState(false)
  const [scenario, setScenario] = useState('balanced')
  const [controller, setController] = useState('adaptive')
  const [perception, setPerception] = useState<Perception | null>(null)
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [message, setMessage] = useState('')
  const [tab, setTab] = useState<'operations'|'evidence'>('operations')

  const perform = async (action: () => Promise<State>) => {
    try { setMessage(''); setState(await action()) } catch (error) { setMessage(error instanceof Error ? error.message : 'Action failed') }
  }

  useEffect(() => { api.state<State>().then(setState); api.perception<Perception>().then(setPerception) }, [])
  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(async () => {
      try { const next = await api.step<State>(1); setState(next); if (next.step % 4 === 0) setPerception(await api.perception<Perception>()) } catch { setPlaying(false); setMessage('Live simulation connection stopped.') }
    }, 700)
    return () => window.clearInterval(id)
  }, [playing])

  const activeCorridor = Object.entries(state.corridor)
  const selectedObservation = perception?.observations[0]
  const eventTone = (kind:string) => kind === 'MISSION' || kind === 'CORRIDOR' ? 'green' : kind === 'INCIDENT' || kind === 'REROUTE' ? 'amber' : 'blue'

  const toggleClosure = (edge: EdgeState) => perform(() => api.closure<State>(edge.id, !edge.closed))
  const reset = () => perform(async () => { setPlaying(false); return api.reset<State>(scenario, controller) })
  const dispatch = () => perform(() => api.dispatch<State>('I-01','I-06'))
  const changeController = (value:string) => { setController(value); perform(() => api.controller<State>(value)) }

  const routeText = useMemo(() => state.mission?.route.join(' → ') ?? 'Awaiting dispatch', [state.mission])

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><Map size={24}/></div><div><b>MANZIL</b><span>Traffic intelligence prototype</span></div></div>
      <nav><button className={tab==='operations'?'active':''} onClick={()=>setTab('operations')}>Operations</button><button className={tab==='evidence'?'active':''} onClick={()=>setTab('evidence')}>Evidence lab</button></nav>
      <div className="system-state"><i/> prototype-sim <span>Step {state.step}</span></div>
    </header>

    <main>
      <section className="hero-row">
        <div><p className="eyebrow">CONTROL ROOM / F26-104</p><h1>City flow, with a path cleared for urgency.</h1><p>Operate a bounded traffic experiment, compare control policies, and coordinate one ambulance through a moving green corridor.</p></div>
        <div className="hero-actions"><button className="primary" onClick={()=>setPlaying(!playing)}>{playing?<Pause size={17}/>:<Play size={17}/>} {playing?'Pause live run':'Start live run'}</button><button className="secondary" onClick={reset}><RefreshCw size={17}/> Reset scenario</button></div>
      </section>

      {message && <div className="alert"><CircleAlert size={18}/>{message}</div>}

      {tab === 'operations' ? <>
        <section className="control-strip">
          <label>Scenario<select value={scenario} onChange={e=>setScenario(e.target.value)}><option value="balanced">Balanced demand</option><option value="north_pressure">North–south pressure</option><option value="rush_hour">Rush hour</option></select></label>
          <label>Normal controller<select value={controller} onChange={e=>changeController(e.target.value)}><option value="fixed">Fixed time</option><option value="adaptive">Pressure adaptive</option><option value="q_learning">Tabular-Q prototype</option></select></label>
          <div className="source-chip"><Activity size={16}/><div><span>Observation source</span><b>Exact fallback simulation</b></div></div>
          <button className="dispatch" disabled={state.mission?.status==='ACTIVE'} onClick={dispatch}><Ambulance size={18}/>{state.mission?.status==='ACTIVE'?'Mission active':'Dispatch ambulance'}</button>
        </section>

        <section className="metrics-grid">
          <Metric icon={<Gauge/>} label="Network queue" value={state.metrics.totalQueue} note="vehicles across approaches" />
          <Metric icon={<Timer/>} label="Mean wait proxy" value={`${state.metrics.meanWaitProxy}s`} note="prototype measure" />
          <Metric icon={<Activity/>} label="Throughput" value={state.metrics.throughput} note="served vehicles" />
          <Metric icon={<ShieldCheck/>} label="Safety interventions" value={state.metrics.fallbackInterventions} note="invalid requests blocked" />
        </section>

        <section className="main-grid">
          <article className="panel network-panel"><div className="panel-head"><div><span className="kicker">LIVE NETWORK</span><h2>Synthetic corridor testbed</h2></div><span className="badge">Seed {state.seed}</span></div><NetworkMap state={state} onToggleClosure={toggleClosure}/></article>
          <aside className="side-stack">
            <article className="panel mission-card"><div className="panel-head"><div><span className="kicker">EMERGENCY MISSION</span><h2>{state.mission?.id ?? 'No active vehicle'}</h2></div><Ambulance className="accent-icon"/></div>
              <div className="route-box"><span>Dynamic route · version {state.mission?.routeVersion ?? '—'}</span><strong>{routeText}</strong></div>
              <div className="mission-stats"><div><b>{state.mission?.status ?? 'STANDBY'}</b><span>Status</span></div><div><b>{state.mission?.stops ?? 0}</b><span>Stops</span></div><div><b>{state.mission?.reroutes ?? 0}</b><span>Reroutes</span></div></div>
              <div className="corridor-list"><span className="kicker">MOVING CORRIDOR</span>{activeCorridor.length ? activeCorridor.map(([id,status])=><div key={id}><span>{id}</span><b>{status.replace('_',' ')}</b></div>) : <p>Dispatch an ambulance to prepare bounded signal priority.</p>}</div>
            </article>
            <article className="panel events"><div className="panel-head"><div><span className="kicker">AUDIT TRAIL</span><h2>Decision timeline</h2></div></div><div className="event-list">{state.events.slice(0,7).map((event,index)=><div className="event" key={`${event.step}-${index}`}><i className={eventTone(event.kind)}/><div><b>{event.kind}</b><p>{event.message}</p></div><time>t+{event.step}</time></div>)}</div></article>
          </aside>
        </section>
      </> : <>
        <section className="evidence-grid">
          <article className="panel perception-card"><div className="panel-head"><div><span className="kicker">PERCEPTION CONTRACT</span><h2>Mock traffic observation</h2></div><span className="badge warning">Not YOLO output</span></div>
            <div className="camera-frame"><div className="scanline"/><TrafficCone/><span>Recorded-video adapter placeholder</span>{perception?.observations.slice(0,4).map((item,index)=><i key={item.intersectionId} style={{left:`${18+index*19}%`,top:`${28+(index%2)*24}%`}}><small>track {17+index}</small></i>)}</div>
            <p className="notice">{perception?.notice}</p>
            <div className="observation-grid"><div><span>Source</span><b>{perception?.sourceMode}</b></div><div><span>Calibration</span><b>{perception?.calibrated?'Available':'Unavailable'}</b></div><div><span>I-01 count</span><b>{selectedObservation?.vehicleCount ?? '—'}</b></div><div><span>Confidence</span><b>{selectedObservation ? `${Math.round(selectedObservation.confidence*100)}%`:'—'}</b></div></div>
          </article>
          <article className="panel comparison-card"><div className="panel-head"><div><span className="kicker">MATCHED COMPARISON</span><h2>Controller evidence</h2></div><BarChart3 className="accent-icon"/></div>
            {!comparison ? <div className="empty-chart"><Sparkles/><p>Run the same rush-hour seed across all three controllers.</p><button className="primary" onClick={async()=>setComparison(await api.compare<Comparison>())}>Run comparison</button></div> : <><div className="bars">{comparison.results.map(result=><div className="bar-row" key={result.controller}><span>{result.controller.replace('_',' ')}</span><div><i style={{width:`${Math.min(100,result.meanWaitProxy*5)}%`}}/></div><b>{result.meanWaitProxy}s</b></div>)}</div><p className="notice">{comparison.warning}</p></>}
          </article>
        </section>
        <section className="panel export-panel"><div><span className="kicker">REPRODUCIBILITY</span><h2>Export the current evidence package</h2><p>Includes the seed, scenario, controller, traffic state, route versions, event history, mock perception metadata, and limitations.</p></div><a className="secondary link-button" href="/api/export" download><Download size={17}/> Download JSON</a></section>
      </>}
    </main>
    <footer><span>MANZIL PROTOTYPE · FAST-NUCES</span><span>Simulation only — not for public-road operation</span></footer>
  </div>
}
