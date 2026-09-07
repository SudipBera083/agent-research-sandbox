export function modelFromSnapshot(snapshot) {
  return {
    simulation: snapshot?.simulation || null,
    world: snapshot?.world || null,
    agents: Object.fromEntries((snapshot?.agents || []).map(agent => [agent.id, agent])),
    latestSequence: Number(snapshot?.latest_sequence || 0),
  };
}

function statusFromEvent(type, data) {
  if (data?.simulation?.status) return data.simulation.status;
  if (type === 'simulation.started' || type === 'simulation.resumed') return 'running';
  if (type === 'simulation.paused') return 'paused';
  if (type === 'simulation.completed') return 'completed';
  if (type === 'simulation.error') return 'error';
  return undefined;
}

export function applyEvent(model, event) {
  const data = event.data || {};
  const simulation = { ...(model.simulation || {}) };
  const world = { ...(model.world || {}) };
  const agents = { ...model.agents };
  const status = statusFromEvent(event.event_type, data);
  if (status) simulation.status = status;
  if (Number.isFinite(Number(event.tick))) {
    simulation.current_tick = Number(event.tick);
    world.current_tick = Number(event.tick);
  }
  if (data.simulation && typeof data.simulation === 'object') Object.assign(simulation, data.simulation);
  if (data.world && typeof data.world === 'object') Object.assign(world, data.world);
  if (event.event_type === 'world.tick') {
    world.agent_count = data.agent_count ?? world.agent_count;
    world.current_tick = data.tick ?? world.current_tick;
  }
  if (event.agent_id != null && agents[event.agent_id]) {
    const agent = { ...agents[event.agent_id] };
    if (event.event_type === 'agent.decision') {
      agent.last_decision = data;
      agent.current_action = data.action ?? agent.current_action;
    }
    if (event.event_type === 'agent.action') {
      agent.current_action = data.action ?? agent.current_action;
      agent.last_action = data.action ?? agent.last_action;
    }
    if (['agent.state_changed', 'agent.resource_changed'].includes(event.event_type)) Object.assign(agent, data);
    if (event.event_type === 'resource.changed' && data.resource) {
      agent.resources = { ...(agent.resources || {}), [data.resource]: data.current ?? ((agent.resources?.[data.resource] || 0) + (data.change || 0)) };
    }
    if (event.event_type === 'agent.died') agent.status = 'died';
    if (event.event_type === 'agent.recovered') agent.status = 'active';
    agent.last_observation_tick = event.tick ?? agent.last_observation_tick;
    agents[event.agent_id] = agent;
  }
  return { simulation, world, agents, latestSequence: Math.max(model.latestSequence || 0, Number(event.sequence) || 0) };
}

export function mergeEvents(previous, incoming) {
  const merged = new Map(previous.map(event => [event.sequence, event]));
  incoming.forEach(event => { if (Number.isFinite(Number(event.sequence))) merged.set(Number(event.sequence), event); });
  return [...merged.values()].sort((a, b) => a.sequence - b.sequence).slice(-300);
}
