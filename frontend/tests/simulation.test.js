import test from 'node:test';
import assert from 'node:assert/strict';
import { applyEvent, mergeEvents, modelFromSnapshot } from '../src/simulationState.js';
import { normalizeApiBase } from '../src/simulationApi.js';

test('snapshot creates authoritative agent and sequence state', () => {
  const model = modelFromSnapshot({ simulation: { id: 4, status: 'running' }, world: { agent_count: 1 }, latest_sequence: 9, agents: [{ id: 2, name: 'A', wealth: 10 }] });
  assert.equal(model.latestSequence, 9);
  assert.equal(model.agents[2].name, 'A');
});

test('events update agent decisions and world tick deterministically', () => {
  let model = modelFromSnapshot({ simulation: { status: 'running' }, world: {}, latest_sequence: 0, agents: [{ id: 1, name: 'A', wealth: 10, resources: {} }] });
  model = applyEvent(model, { sequence: 1, tick: 3, event_type: 'agent.decision', agent_id: 1, data: { action: 'buy', parameters: { resource: 'food' } } });
  model = applyEvent(model, { sequence: 2, tick: 3, event_type: 'agent.state_changed', agent_id: 1, data: { wealth: 0, health: 90 } });
  assert.equal(model.latestSequence, 2);
  assert.equal(model.world.current_tick, 3);
  assert.equal(model.agents[1].current_action, 'buy');
  assert.equal(model.agents[1].wealth, 0);
});

test('event merge sorts by sequence and removes duplicates', () => {
  const result = mergeEvents([{ sequence: 2, event_type: 'b' }], [{ sequence: 1, event_type: 'a' }, { sequence: 2, event_type: 'new' }]);
  assert.deepEqual(result.map(e => e.sequence), [1, 2]);
  assert.equal(result[1].event_type, 'new');
});

test('simulation API requires an absolute HTTP(S) origin', () => {
  assert.equal(normalizeApiBase(' https://example.com/ '), 'https://example.com');
  assert.throws(() => normalizeApiBase('/api'));
  assert.throws(() => normalizeApiBase('https://user:pass@example.com'));
});
