import { useEffect, useRef, useState } from 'react';
import { normalizeReport, normalizeBase, getJson, download } from './api.js';

const tabs = ['Overview', 'Runtimes', 'Scenarios', 'Insights', 'Repository'];
const metrics = { total_wealth: 'Total wealth', trade_volume: 'Trade volume', messages: 'Messages', llm_latency: 'LLM latency (ms)', llm_tokens: 'LLM tokens' };
const n = value => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : 'N/A';
const txt = value => typeof value === 'string' || typeof value === 'number' ? String(value) : 'N/A';
const list = value => Array.isArray(value) ? value.filter(x => x && typeof x === 'object') : [];
function Empty({ title = 'No observations yet', children = 'Import a persisted report or connect your benchmark API to populate this view.' }) {
  return <div className="empty"><span aria-hidden="true">o</span><h3>{title}</h3><p>{children}</p></div>;
}
function Panel({ title, note, children, className = '' }) {
  return <section className={'panel ' + className}><div className="panel-head"><h2>{title}</h2>{note && <span className="subtle">{note}</span>}</div>{children}</section>;
}
function Table({ columns, rows }) {
  return rows.length ? <div className="table-wrap"><table><thead><tr>{columns.map(c => <th key={c[0]}>{c[0]}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{columns.map(c => <td key={c[0]}>{c[1](r, i)}</td>)}</tr>)}</tbody></table></div> : <Empty />;
}
function Chart({ rows, metric }) {
  const valid = rows.filter(r => typeof r[metric] === 'number' && Number.isFinite(r[metric]));
  const max = Math.max(1, ...valid.map(r => Math.abs(r[metric])));
  return valid.length ? <div className="bars" role="list" aria-label={metrics[metric]}>{valid.map((r, i) => <div className="bar-row" key={i} role="listitem"><div className="bar-label"><b>{r.runtime}</b><span>{r.scenario}</span></div><div className="track"><div className={'bar c' + (i % 3)} style={{ width: Math.abs(r[metric]) / max * 100 + '%' }} /></div><strong>{n(r[metric])}</strong></div>)}</div> : <Empty title="Your next comparison starts here" />;
}
export default function App() {
  const [tab, setTab] = useState('Overview');
  const [data, setData] = useState(null);
  const [source, setSource] = useState('Repository snapshot');
  const [base, setBase] = useState(import.meta.env.VITE_API_BASE_URL || '');
  const [connectedBase, setConnectedBase] = useState('');
  const [suites, setSuites] = useState([]);
  const [suiteId, setSuiteId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [settings, setSettings] = useState(false);
  const [metric, setMetric] = useState('total_wealth');
  const [search, setSearch] = useState('');
  const [updated, setUpdated] = useState('');
  const controller = useRef(null);
  const upload = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  function begin() { controller.current?.abort(); controller.current = new AbortController(); setBusy(true); setError(''); return controller.current; }
  async function connect(event, selected = '') {
    event?.preventDefault();
    const request = begin();
    setData(null); setSource('No results loaded'); setSuites([]); setSuiteId('');
    try {
      const endpoint = normalizeBase(base);
      const result = await getJson(endpoint, '/suites/', request.signal);
      if (!Array.isArray(result.results) || result.results.some(s => !Number.isInteger(s?.id) || typeof s.name !== 'string')) throw new Error('Suite list does not match the API contract.');
      const id = result.results.some(s => String(s.id) === String(selected)) ? selected : result.results[0]?.id;
      if (id !== undefined) {
        let raw = await getJson(endpoint, '/suites/' + encodeURIComponent(id) + '/summary/', request.signal);
        try {
          raw = await getJson(endpoint, '/suites/' + encodeURIComponent(id) + '/report/', request.signal);
        } catch (detailError) {
          if (request.signal.aborted) throw detailError;
        }
        const next = normalizeReport(raw);
        if (String(raw.suite.id) !== String(id)) throw new Error('The backend returned a different suite.');
        if (request.signal.aborted) return;
        setData(next); setSuiteId(String(id));
      }
      if (request.signal.aborted) return;
      setSuites(result.results); setConnectedBase(endpoint); setSource('Backend API'); setUpdated(new Date().toLocaleTimeString());
    } catch (e) { if (!request.signal.aborted) setError(e.message); }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  async function importFile(event) {
    const file = event.target.files?.[0]; event.target.value = '';
    if (!file) return;
    const request = begin();
    try {
      if (file.size > 5 * 1024 * 1024) throw new Error('Choose a JSON report smaller than 5 MB.');
      const report = normalizeReport(JSON.parse(await file.text()));
      if (request.signal.aborted) return;
      setData(report); setSource('Imported report'); setSuiteId(''); setSuites([]); setConnectedBase(''); setUpdated(new Date().toLocaleTimeString());
    } catch (e) { if (!request.signal.aborted) setError('Could not import report: ' + e.message); }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  const match = row => Object.values(row).some(v => typeof v === 'string' && v.toLowerCase().includes(search.toLowerCase()));
  const rows = (data?.rows || []).filter(match);
  const rankings = list(data?.rankings).filter(match);
  const scenarios = list(data?.scenarios).filter(match);
  const runtimeColumns = [['Rank', (r,i) => r.rank ?? i+1], ['Runtime', r => <b>{txt(r.runtime)}</b>], ['Avg. wealth', r => n(r.average_total_wealth)], ['Avg. trades', r => n(r.average_trade_volume)], ['Avg. messages', r => n(r.average_message_count)], ['Diversity', r => n(r.average_action_diversity)]];
  return <div className="layout">
    <a className="skip" href="#main">Skip to content</a>
    <aside className="sidebar"><a className="brand" href="#main"><span className="brand-icon">AR</span><span>Sandbox<span className="brand-sub">AGENT RESEARCH</span></span></a>
      <div className="workspace"><span className="workspace-avatar">AR</span><div>Research workspace<small>Benchmark explorer</small></div></div>
      <p className="nav-label">WORKSPACE</p><nav aria-label="Dashboard navigation">{tabs.map((t,i) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)} aria-current={tab === t ? 'page' : undefined}><span aria-hidden="true">{['O','R','S','I','D'][i]}</span>{t}</button>)}</nav>
      <div className="sidebar-bottom"><div className="small-orbit">o</div><b>Observe. Compare. Understand.</b><p>Explore agent behavior through persisted experiment results.</p><span className="tag">READ-ONLY WORKSPACE</span></div>
    </aside>
    <div className="body"><div className="topbar"><div>Workspace <span>/</span> <b>{tab}</b></div><div className="source"><i />{source}</div></div>
    <main id="main"><header><div><p className="eyebrow">BENCHMARK INTELLIGENCE</p><h1>{tab === 'Overview' ? 'A clearer view of your agents.' : tab}</h1><p className="description">Understand performance, compare runtimes, and explore what happened.</p></div><div className="actions"><button onClick={() => upload.current.click()} disabled={busy}>Import report</button><button className="primary" onClick={() => setSettings(!settings)} aria-expanded={settings}>Connect API &gt;</button><input className="hidden" ref={upload} type="file" accept=".json,application/json" onChange={importFile} aria-label="Import benchmark report" /></div></header>
    {settings && <form className="connection" onSubmit={connect}><label>Benchmark API URL<input type="url" required placeholder="https://backend.example.com/api/benchmarks" value={base} onChange={e=>setBase(e.target.value)} /></label><button className="primary" disabled={busy}>Load suites</button><p>Uses the documented Step 31 suite list and full report endpoints.</p></form>}
    {error && <div className="error" role="alert">{error}</div>}
    <div className="filterbar"><div><span className="tag">{busy ? 'LOADING' : data ? 'REPORT LOADED' : 'AWAITING RESULTS'}</span><strong>{data?.suite.name || 'Research overview'}</strong></div><div className="filters">{suites.length > 0 && <select aria-label="Benchmark suite" value={suiteId} disabled={busy} onChange={e=>connect(null,e.target.value)}>{suites.map(s=><option value={s.id} key={s.id}>{s.name}</option>)}</select>}<input aria-label="Filter runtimes and scenarios" type="search" placeholder="Search runtimes or scenarios..." value={search} onChange={e=>setSearch(e.target.value)} /><button disabled={!connectedBase || busy} onClick={()=>connect(null,suiteId)} aria-label="Refresh backend data">Refresh</button></div></div>
    <div role="status" className="sr-only">{busy ? 'Loading data' : error || source}</div>
    {tab !== 'Repository' && <div className="stats">{[['Scenarios',data?.coverage.scenario_count,'Scenario coverage'],['Runtimes',data?.coverage.runtime_count,'Compared agent strategies'],['Observations',data?.coverage.observation_count,'Persisted comparisons'],['LLM tokens',data?.llm.total_tokens,'Recorded model usage']].map(([label,value,desc],i)=><div className="stat" key={label}><div>{label}<span className={'stat-icon c'+i}>{['S','R','O','L'][i]}</span></div><strong>{n(value)}</strong><small>{value == null ? 'Not available in this report' : desc}</small></div>)}</div>}
    {tab === 'Overview' && <><div className="visual-grid"><Panel title="Performance comparison" note="By scenario and runtime"><div className="chart-controls"><select aria-label="Comparison metric" value={metric} onChange={e=>setMetric(e.target.value)}>{Object.entries(metrics).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><span className="subtle">Recorded values - no projections</span></div><Chart rows={rows} metric={metric} /></Panel><Panel title="Research context"><div className="context-orbit" aria-hidden="true"><span>o</span></div><h3>{data ? txt(data.suite.name) : 'Ready for your first report'}</h3><p className="context-text">{data ? 'This workspace presents recorded observations from your selected source.' : 'Your backend contains the agent simulation and reporting engine. Import its JSON report to explore the results here.'}</p><dl><div><dt>Data source</dt><dd>{source}</dd></div><div><dt>Experiment seed</dt><dd>{txt(data?.suite.seed)}</dd></div><div><dt>Last loaded</dt><dd>{updated || 'N/A'}</dd></div></dl></Panel></div><Panel title="Runtime comparison" note="Backend ranking order"><Table rows={rankings} columns={runtimeColumns}/></Panel></>}
    {tab === 'Runtimes' && <><Panel title="Runtime comparison"><Table rows={rankings} columns={runtimeColumns}/></Panel><Panel title="Observation detail" note="Values from report rows"><Table rows={rows} columns={[['Scenario',r=>r.scenario],['Runtime',r=>r.runtime],['Wealth',r=>n(r.total_wealth)],['Trades',r=>n(r.trade_volume)],['Messages',r=>n(r.messages)],['Latency (ms)',r=>n(r.llm_latency)],['Tokens',r=>n(r.llm_tokens)]]}/></Panel></>}
    {tab === 'Scenarios' && <Panel title="Scenario leaders"><Table rows={scenarios} columns={[['Scenario',r=>txt(r.scenario)],['Leading runtime',r=>txt(r.best_runtime ?? r.winning_runtime)],['Best wealth',r=>n(r.best_wealth)],['Wealth spread',r=>n(r.wealth_spread ?? r.wealth_advantage)]]}/></Panel>}
    {tab === 'Insights' && <><div className="visual-grid"><Panel title="Observed recommendations">{data?.recommendations.length ? <ul className="recommendations">{data.recommendations.map((r,i)=><li key={i}>{txt(r)}</li>)}</ul> : <Empty title="No recommendations recorded" />}</Panel><Panel title="LLM assessment"><dl>{[['Provider',data?.llm.provider],['Model',data?.llm.model],['Average latency (ms)',n(data?.llm.average_latency_ms)],['Failures',n(data?.llm.failure_count)]].map(([a,b])=><div key={a}><dt>{a}</dt><dd>{txt(b)}</dd></div>)}</dl></Panel></div><Panel title="Strongest observed differences"><Table rows={list(data?.differences)} columns={[['Metric',r=>txt(r.metric)],['Scenario',r=>txt(r.scenario)],['Runtime A',r=>txt(r.runtime_a)],['Runtime B',r=>txt(r.runtime_b)],['Difference',r=>n(r.difference)]]}/></Panel><Panel title="Consistency"><Table rows={list(data?.consistency)} columns={[['Runtime',r=>txt(r.runtime)],['Classification',r=>txt(r.classification)],['Wealth range',r=>n(r.wealth_range)],['Mean wealth',r=>n(r.mean_wealth)]]}/></Panel></>}
    {tab === 'Repository' && <><Panel title="Included in ZIP (3)" note="Source code inventory - not experiment results"><div className="repo-grid">{[['agents','Agent state, memory, retrieval and model providers'],['simulation','Worlds, resources, communication, trades and tick execution'],['events','Persisted simulation event records'],['experiments','Experiment results, decision traces, metrics and report builders']].map(([a,b])=><div className="repo-card" key={a}><span className="tag">DJANGO MODULE</span><h3>{a}</h3><p>{b}</p></div>)}</div></Panel><Panel title="Integration status"><Table rows={[{a:'Application API',b:'Not included; only /admin/ is routed'},{a:'Benchmark results',b:'No database or exported reports included'},{a:'Report format',b:'BenchmarkReporter.build(): suite, rows, insights, decision_summary'},{a:'Frontend integration',b:'JSON import plus the documented Step 31 REST contract'},{a:'Live simulation stream',b:'No WebSocket or SSE transport in the supplied source'}]} columns={[['Capability',r=>r.a],['Verified status',r=>r.b]]}/></Panel></>}
    <footer><span>Sandbox / Agent Research <span className="footer-dot">-</span> Persisted observations only</span><button disabled={!data} onClick={()=>download(data.raw)}>Download JSON</button></footer>
    </main></div>
  </div>;
}
