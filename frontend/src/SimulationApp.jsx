import { useEffect, useMemo, useRef, useState } from 'react';
import { createEventStream, getAgentEvents, getEvents, getSnapshot, lifecycle, normalizeApiBase } from './simulationApi.js';
import { applyEvent, mergeEvents, modelFromSnapshot } from './simulationState.js';
import './simulation.css';

const defaultBase = import.meta.env.VITE_API_BASE_URL || 'https://agent-research-sandbox.vercel.app';
const eventLabel = type => String(type || 'event').replaceAll('.', ' ');
const fmt = value => value == null ? 'N/A' : typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value);
const ago = timestamp => { const date = new Date(timestamp); return Number.isNaN(date.valueOf()) ? 'recently' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); };

function Empty({ title, text }) { return <div className="sim-empty"><span>o</span><h3>{title}</h3><p>{text}</p></div>; }

function AgentCard({ agent, selected, onSelect }) {
  const health = Math.max(0, Math.min(100, Number(agent.health ?? 0)));
  return <button className={`agent-card ${selected ? 'selected' : ''}`} onClick={() => onSelect(agent.id)}>
    <div className="agent-card-head"><span className="agent-avatar">{String(agent.name || 'A').slice(0, 2).toUpperCase()}</span><span className={`agent-status ${agent.status}`}>{agent.status || 'unknown'}</span></div>
    <h3>{agent.name || `Agent ${agent.id}`}</h3><p>{agent.role || 'general'} · {agent.runtime || 'unknown'}</p>
    <div className="agent-metrics"><span><small>WEALTH</small><b>${fmt(agent.wealth)}</b></span><span><small>HEALTH</small><b>{fmt(agent.health)}%</b></span></div>
    <div className="health-track"><i style={{ width: `${health}%` }} /></div><div className="agent-action">{agent.current_action || agent.last_action || 'waiting'}</div>
  </button>;
}

function EventRow({ event }) { return <div className="event-row"><span className="event-seq">#{event.sequence}</span><div><b>{eventLabel(event.event_type)}</b><p>{event.agent_id == null ? 'World event' : `Agent ${event.agent_id}`} · tick {event.tick}</p></div><time>{ago(event.timestamp)}</time></div>; }

export default function SimulationApp() {
  const [base, setBase] = useState(defaultBase);
  const [simulationId, setSimulationId] = useState('1');
  const [model, setModel] = useState(null);
  const [events, setEvents] = useState([]);
  const [agentEvents, setAgentEvents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [busy, setBusy] = useState(false);
  const [stream, setStream] = useState('offline');
  const [reconnects, setReconnects] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const streamStop = useRef(null);
  const sequence = useRef(0);
  const modelRef = useRef(null);
  const queue = useRef(Promise.resolve());
  const loadController = useRef(null);
  const reconnectTimer = useRef(null);

  const stopStream = () => { reconnectTimer.current && clearTimeout(reconnectTimer.current); reconnectTimer.current = null; streamStop.current?.(); streamStop.current = null; setStream('offline'); };
  const commitEvent = event => {
    if (Number(event.sequence) <= sequence.current) return;
    sequence.current = Number(event.sequence);
    setModel(previous => { const next = applyEvent(previous || { agents: {}, latestSequence: 0 }, event); modelRef.current = next; return next; });
    setEvents(previous => mergeEvents(previous, [event]));
  };
  const processEvent = event => {
    queue.current = queue.current.then(async () => {
      const incoming = Number(event.sequence);
      if (!Number.isFinite(incoming) || incoming <= sequence.current) return;
      if (incoming > sequence.current + 1) {
        const replay = await getEvents(base, simulationId, sequence.current, loadController.current?.signal);
        (replay.events || []).sort((a, b) => a.sequence - b.sequence).forEach(commitEvent);
        if (incoming > sequence.current + 1) { await load(); return; }
      }
      commitEvent(event);
    }).catch(reason => { if (reason?.name !== 'AbortError') setError(reason.message || 'Unable to replay simulation events.'); });
  };
  const openStream = after => {
    stopStream();
    let closed = false;
    let reconnectAttempt = 0;
    let activeStop = null;
    const connect = sequenceAtConnect => {
      if (closed) return;
      try {
        activeStop = createEventStream(base, simulationId, sequenceAtConnect, {
          onEvent: processEvent,
          onOpen: () => { reconnectAttempt = 0; setStream('live'); setNotice('Live event stream connected.'); },
          onError: message => {
            activeStop?.(); activeStop = null;
            if (closed) return;
            setStream('reconnecting'); setNotice(message.message); setReconnects(value => value + 1);
            const delay = Math.min(1000 * (2 ** reconnectAttempt), 10000); reconnectAttempt += 1;
            reconnectTimer.current = setTimeout(() => connect(sequence.current), delay);
          },
        });
        setStream('connecting');
      } catch (reason) { setStream('offline'); setError(reason.message); }
    };
    streamStop.current = () => { closed = true; reconnectTimer.current && clearTimeout(reconnectTimer.current); reconnectTimer.current = null; activeStop?.(); activeStop = null; };
    connect(after);
  };
  async function load(event) {
    event?.preventDefault();
    stopStream(); loadController.current?.abort(); loadController.current = new AbortController();
    setBusy(true); setError(''); setNotice(''); setModel(null); setEvents([]); setAgentEvents([]); sequence.current = 0;
    try {
      const endpoint = normalizeApiBase(base);
      const snapshot = await getSnapshot(endpoint, simulationId, loadController.current.signal);
      const next = modelFromSnapshot(snapshot); modelRef.current = next; sequence.current = next.latestSequence; setModel(next);
      const replay = await getEvents(endpoint, simulationId, sequence.current, loadController.current.signal);
      (replay.events || []).sort((a, b) => a.sequence - b.sequence).forEach(commitEvent);
      openStream(sequence.current);
      setNotice(`Connected to simulation ${simulationId}.`);
    } catch (reason) { if (reason?.name !== 'AbortError') setError(reason.message || 'Unable to load the simulation.'); }
    finally { setBusy(false); }
  }
  async function control(action) {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await lifecycle(base, simulationId, action);
      if (response.simulation) setModel(previous => ({ ...(previous || {}), simulation: { ...(previous?.simulation || {}), ...response.simulation } }));
      if (Array.isArray(response.events)) response.events.sort((a, b) => a.sequence - b.sequence).forEach(commitEvent);
      setNotice(`${action} request accepted.`);
    } catch (reason) { setError(reason.message || `Unable to ${action} the simulation.`); }
    finally { setBusy(false); }
  }
  useEffect(() => () => { stopStream(); loadController.current?.abort(); }, []);
  useEffect(() => { if (selectedAgent == null || !model) return; const controller = new AbortController(); getAgentEvents(base, simulationId, selectedAgent, 0, controller.signal).then(result => setAgentEvents(result.events || [])).catch(() => setAgentEvents([])); return () => controller.abort(); }, [selectedAgent, simulationId, base, Boolean(model)]);

  const agents = useMemo(() => Object.values(model?.agents || {}).sort((a, b) => a.id - b.id), [model]);
  const selected = selectedAgent == null ? null : model?.agents?.[selectedAgent];
  const status = model?.simulation?.status || 'not loaded';
  const canStart = ['created', 'paused', 'running'].includes(status);
  const canPause = status === 'running';
  const canStep = ['created', 'paused', 'running'].includes(status);
  return <div className="sim-shell">
    <header className="sim-top"><div className="sim-brand"><span>AR</span><div>Agent Research<small>LIVE SIMULATION</small></div></div><div className={`stream-pill ${stream}`}><i />{stream === 'live' ? 'SSE live' : stream === 'reconnecting' ? 'Reconnecting' : 'Stream offline'}</div></header>
    <main className="sim-main"><section className="sim-hero"><div><p className="sim-eyebrow">REAL-TIME AGENT OBSERVATORY</p><h1>Watch decisions become behavior.</h1><p>Inspect the world state, agent reasoning, and ordered event ledger as the simulation runs.</p></div><form className="sim-connect" onSubmit={load}><label>Backend URL<input value={base} onChange={e => setBase(e.target.value)} aria-label="Backend URL" /></label><label>Simulation ID<input value={simulationId} onChange={e => setSimulationId(e.target.value)} inputMode="numeric" aria-label="Simulation ID" /></label><button className="sim-primary" disabled={busy}>Load simulation</button></form></section>
      {error && <div className="sim-error" role="alert">{error}</div>}{notice && <div className="sim-notice" role="status">{notice}</div>}
      <section className="control-bar"><div><small>SIMULATION STATUS</small><strong className={`status-text ${status}`}>{status}</strong></div><div><small>TICK</small><strong>{model?.simulation ? `${fmt(model.simulation.current_tick)} / ${fmt(model.simulation.total_ticks)}` : 'N/A'}</strong></div><div><small>SEQUENCE</small><strong>#{model?.latestSequence ?? 0}</strong></div><div><small>AGENTS</small><strong>{model?.world?.agent_count ?? agents.length}</strong></div><div className="control-actions"><button onClick={() => control('start')} disabled={busy || !model || !canStart}>Start</button><button onClick={() => control('pause')} disabled={busy || !model || !canPause}>Pause</button><button onClick={() => control('step')} disabled={busy || !model || !canStep}>Step</button></div></section>
      {!model && !busy && !error && <Empty title="Load a simulation to begin" text="Enter a simulation ID and connect to the API contract supplied by the backend team." />}
      {busy && !model && <div className="sim-loading">Loading snapshot and event history…</div>}
      {model && <><section className="world-strip"><div><small>WORLD</small><b>{model.simulation?.name || `Simulation ${simulationId}`}</b></div><div><small>LEDGER EVENTS</small><b>{fmt(model.world?.total_events)}</b></div><div><small>STREAM RECONNECTS</small><b>{reconnects}</b></div><div><small>SEED</small><b>{fmt(model.simulation?.seed)}</b></div></section><div className="sim-grid"><section><div className="section-heading"><div><p className="sim-eyebrow">AGENT STATE</p><h2>Agents in this world</h2></div><span>{agents.length} registered</span></div><div className="agent-grid">{agents.length ? agents.map(agent => <AgentCard key={agent.id} agent={agent} selected={selectedAgent === agent.id} onSelect={setSelectedAgent} />) : <Empty title="No agents in snapshot" text="The backend returned a valid simulation without agent state." />}</div></section><aside className="activity-panel"><div className="section-heading"><div><p className="sim-eyebrow">ORDERED LEDGER</p><h2>Activity feed</h2></div><span>#{model.latestSequence}</span></div><div className="event-list">{events.length ? [...events].reverse().map(event => <EventRow key={event.sequence} event={event} />) : <Empty title="No new events" text="Events will appear here as the SSE stream advances." />}</div></aside></div></>}
      {selected && <section className="detail-panel"><div className="section-heading"><div><p className="sim-eyebrow">AGENT DETAIL</p><h2>{selected.name || `Agent ${selected.id}`}</h2></div><button onClick={() => setSelectedAgent(null)}>Close</button></div><div className="detail-grid"><div><small>ROLE / RUNTIME</small><b>{selected.role || 'general'} · {selected.runtime || 'unknown'}</b><small>PROVIDER / MODEL</small><b>{selected.provider || 'N/A'} · {selected.model || 'N/A'}</b><small>LAST ACTION</small><b>{selected.last_action || selected.current_action || 'N/A'}</b></div><div><small>WEALTH</small><strong>${fmt(selected.wealth)}</strong><small>HEALTH</small><div className="health-track large"><i style={{ width: `${Math.max(0, Math.min(100, Number(selected.health || 0)))}%` }} /></div><small>INVENTORY</small><div className="inventory">{Object.entries(selected.resources || {}).map(([name, value]) => <span key={name}>{name}<b>{fmt(value)}</b></span>)}</div></div><div><small>DECISION TRACE</small><pre>{selected.last_decision ? JSON.stringify(selected.last_decision, null, 2) : 'No decision trace in snapshot.'}</pre></div><div><small>AGENT EVENTS</small><div className="mini-events">{agentEvents.length ? agentEvents.slice(-8).reverse().map(event => <EventRow key={event.sequence} event={event} />) : <p>No agent events loaded.</p>}</div></div></div></section>}
      <footer className="sim-footer">Sequence ordering is authoritative. Browser arrival time is never used for causality.<span>Reconnects: {reconnects}</span></footer>
    </main>
  </div>;
}
