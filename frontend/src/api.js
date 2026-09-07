export function normalizeReport(raw) {
  if (!raw || typeof raw !== 'object' || !raw.suite || typeof raw.suite.name !== 'string') throw new Error('Expected a benchmark report or summary containing suite.name.');
  const full = Array.isArray(raw.rows);
  const insights = raw.insights ?? {};
  const decision = raw.decision_summary ?? {};
  const arrays = [raw.rows, raw.runtime_ranking, raw.scenario_leaders, raw.recommendations, insights.runtime_ranking, insights.scenario_ranking, insights.consistency];
  if (arrays.some(x => x !== undefined && !Array.isArray(x))) throw new Error('The report has invalid list fields.');
  const rows = raw.rows ?? [];
  if (rows.some(x => !x || typeof x.runtime !== 'string' || typeof x.scenario !== 'string')) throw new Error('Report rows must include runtime and scenario names.');
  const rankings = raw.runtime_ranking ?? insights.runtime_ranking ?? [];
  const scenarios = raw.scenario_leaders ?? insights.scenario_ranking ?? decision.scenario_leaders ?? [];
  return {
    raw, suite: raw.suite, rows, rankings, scenarios,
    coverage: raw.coverage ?? {
      scenario_count: decision.coverage_summary?.scenario_count ?? (full ? new Set(rows.map(r => r.scenario)).size : undefined),
      runtime_count: decision.coverage_summary?.runtime_count ?? (full ? new Set(rows.map(r => r.runtime)).size : undefined),
      observation_count: decision.coverage_summary?.total_observations ?? (full ? rows.length : undefined),
    },
    differences: raw.strongest_differences ?? insights.strongest_differences ?? [],
    consistency: raw.consistency ?? insights.consistency ?? [],
    llm: raw.llm ?? insights.llm ?? decision.llm_assessment ?? {},
    recommendations: raw.recommendations ?? decision.recommendations ?? [],
    findings: raw.findings ?? [],
  };
}
export function normalizeBase(value) {
  const base = value.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//i.test(base)) throw new Error('Enter the complete HTTP(S) backend URL ending in /api/benchmarks.');
  const url = new URL(base);
  if (url.username || url.password || url.search || url.hash) throw new Error('Use a URL without credentials, query parameters or fragments.');
  return base;
}
export async function getJson(base, path, signal) {
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), 15000);
  const abort = () => timeoutController.abort();
  signal?.addEventListener('abort', abort, { once: true });
  let response;
  try {
    response = await fetch(normalizeBase(base) + path, { headers: { Accept: 'application/json' }, signal: timeoutController.signal });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new Error(timeoutController.signal.aborted ? 'The backend took too long to respond.' : 'Cannot reach the backend. Check the URL, HTTPS and allowed CORS origins, then retry.');
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener('abort', abort);
  }
  if (!response.ok) throw new Error(`Backend returned HTTP ${response.status}. ${response.status === 404 ? 'This endpoint or record is not available.' : 'Please check backend access and availability.'}`);
  if (!response.headers.get('content-type')?.includes('json')) throw new Error('Expected JSON, but received a web page. Enter the backend API URL.');
  return response.json();
}
export function download(report) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'benchmark-report.json'; document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
