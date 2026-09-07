import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeReport, normalizeBase, getJson } from '../src/api.js';
test('full reports preserve zero and derive coverage only from recorded rows', () => {
 const raw={suite:{name:'Test'},rows:[{runtime:'rule',scenario:'baseline',total_wealth:0}]};
 const data=normalizeReport(raw); assert.equal(data.rows[0].total_wealth,0);assert.equal(data.coverage.observation_count,1);assert.equal(data.raw,raw);
});
test('summary preserves backend coverage and missing measurements', () => {
 const data=normalizeReport({suite:{name:'Test'},coverage:{scenario_count:5},runtime_ranking:[]});
 assert.equal(data.coverage.scenario_count,5);assert.equal(data.llm.total_tokens,undefined);
});
test('invalid imports rejected', () => {for(const x of [null,{}, {suite:{name:'X'},rows:'invalid'},{suite:{name:'X'},rows:[{}]}]) assert.throws(()=>normalizeReport(x));});
test('base URLs normalized and credentials rejected', () => {assert.equal(normalizeBase(' https://example.com/api/benchmarks/ '),'https://example.com/api/benchmarks');assert.throws(()=>normalizeBase('https://user:secret@example.com'));assert.throws(()=>normalizeBase('javascript:alert(1)'));});
test('HTML and HTTP failures are not accepted as benchmark data', async t => {
 t.mock.method(globalThis,'fetch', async()=>new Response('html',{headers:{'content-type':'text/html'}}));
 await assert.rejects(()=>getJson('https://example.com','/',new AbortController().signal),/Expected JSON/);
 globalThis.fetch=async()=>new Response('',{status:404});
 await assert.rejects(()=>getJson('https://example.com','/',new AbortController().signal),/404/);
});
