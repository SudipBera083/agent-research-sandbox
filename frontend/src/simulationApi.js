const EVENT_TYPES = [
  'simulation.created', 'simulation.started', 'simulation.paused', 'simulation.resumed',
  'simulation.completed', 'simulation.error', 'world.tick', 'agent.spawned',
  'agent.observation', 'agent.decision', 'agent.action', 'agent.state_changed',
  'agent.resource_changed', 'message.created', 'trade.proposed', 'trade.accepted',
  'trade.rejected', 'trade.completed', 'resource.changed', 'agent.died', 'agent.recovered',
];

export const eventTypes = EVENT_TYPES;

export function normalizeApiBase(value) {
  const base = String(value || '').trim().replace(/\/+$/, '');
  if (!/^https?:\/\//i.test(base)) throw new Error('Enter the complete HTTP(S) backend URL, for example https://api.example.com.');
  const url = new URL(base);
  if (url.username || url.password || url.search || url.hash) throw new Error('Use a backend URL without credentials, query parameters, or fragments.');
  return base;
}

function endpoint(base, simulationId, suffix, query = '') {
  return `${normalizeApiBase(base)}/api/simulations/${encodeURIComponent(simulationId)}/${suffix}/${query}`;
}

async function request(base, path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 15000);
  const cancel = () => controller.abort();
  options.signal?.addEventListener('abort', cancel, { once: true });
  try {
    const response = await fetch(path, {
      method: options.method || 'GET',
      headers: { Accept: 'application/json', ...(options.method && { 'Content-Type': 'application/json' }) },
      body: options.body,
      signal: controller.signal,
    });
    const contentType = response.headers.get('content-type') || '';
    let payload = null;
    if (contentType.includes('json')) payload = await response.json();
    if (!response.ok) {
      const detail = payload?.message || payload?.detail || payload?.error;
      throw new Error(detail ? `Backend returned HTTP ${response.status}: ${detail}` : `Backend returned HTTP ${response.status}.`);
    }
    if (!contentType.includes('json')) throw new Error('The backend returned a non-JSON response. Check the API URL and route.');
    return payload;
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (controller.signal.aborted) throw new Error('The backend took too long to respond.');
    if (error instanceof TypeError) throw new Error('Cannot reach the backend. Check HTTPS, CORS, and the backend URL.');
    throw error;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener('abort', cancel);
  }
}

export const getSnapshot = (base, id, signal) => request(base, endpoint(base, id, 'snapshot'), { signal });

export const getEvents = (base, id, afterSequence, signal) => request(
  base,
  endpoint(base, id, 'events', `?after_sequence=${encodeURIComponent(afterSequence || 0)}&limit=1000`),
  { signal },
);

export const getAgentEvents = (base, id, agentId, afterSequence, signal) => request(
  base,
  `${normalizeApiBase(base)}/api/simulations/${encodeURIComponent(id)}/agents/${encodeURIComponent(agentId)}/events/?after_sequence=${encodeURIComponent(afterSequence || 0)}&limit=1000`,
  { signal },
);

export const lifecycle = (base, id, action, signal) => request(
  base,
  endpoint(base, id, action),
  { method: 'POST', body: undefined, signal },
);

export function createEventStream(base, id, afterSequence, { onEvent, onOpen, onError }) {
  const url = endpoint(base, id, 'stream', `?after_sequence=${encodeURIComponent(afterSequence || 0)}`);
  const source = new EventSource(url);
  const listeners = EVENT_TYPES.map(type => {
    const handler = event => {
      try {
        const payload = JSON.parse(event.data);
        if (payload && Number.isFinite(Number(payload.sequence))) onEvent(payload);
      } catch {
        onError?.(new Error('The backend sent an invalid SSE event.'));
      }
    };
    source.addEventListener(type, handler);
    return [type, handler];
  });
  source.onopen = () => onOpen?.();
  source.onerror = () => onError?.(new Error('The live stream disconnected. Reconnecting…'));
  return () => {
    listeners.forEach(([type, handler]) => source.removeEventListener(type, handler));
    source.close();
  };
}
