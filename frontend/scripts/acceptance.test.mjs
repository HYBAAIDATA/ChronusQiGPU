import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { performance } from 'node:perf_hooks';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';
import './workload-journey.test.mjs';

const port = 31_000 + Math.floor(Math.random() * 5_000);
const baseUrl = `http://127.0.0.1:${port}`;
const nextCommand = process.platform === 'win32' ? 'node_modules/.bin/next.cmd' : './node_modules/.bin/next';
let server;
let fixtureBackend;
let fixtureSubmissions = 0;
const fixtureRecord = {
  workload_id: '79712fbc-baf9-46f6-ae1a-0973398da822', tenant_id: 'http-fixture', workload_type: 'scaling.v1',
  status: 'QUEUED', result: null, verification_receipt: null,
};

async function loadFrontendModule(file) {
  const source = await readFile(new URL(`../lib/${file}.ts`, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}

before(async () => {
  // Loopback-only synthetic service: no real backend, credentials, or durable state writes.
  fixtureBackend = createServer(async (request, response) => {
    const send = (status, body) => { response.writeHead(status, { 'content-type': 'application/json' }); response.end(JSON.stringify(body)); };
    const url = new URL(request.url, 'http://fixture.invalid');
    if (url.pathname.startsWith('/v1/workloads') && request.headers.authorization !== 'Bearer http-fixture-access') return send(401, { detail: 'Synthetic authentication required' });
    if (url.pathname === '/v1/workloads' && request.method === 'POST') {
      let raw = '';
      for await (const chunk of request) raw += chunk;
      const body = JSON.parse(raw);
      if (body.tenant_id !== 'http-fixture' || body.workload_type !== 'scaling.v1' || body.payload_bytes !== '{"index":10}') return send(422, { detail: 'Unexpected synthetic request' });
      fixtureSubmissions += 1;
      return send(202, fixtureRecord);
    }
    if (url.pathname === `/v1/workloads/${fixtureRecord.workload_id}`) {
      Object.assign(fixtureRecord, { status: 'COMPLETED', result: { backend: 'synthetic-http-fixture', duration_ms: 1, result: { family: 'scaling.v1', index: 10, sequence_value: '123', companion_value: '55' } }, verification_receipt: 'http-fixture-receipt' });
      return send(200, fixtureRecord);
    }
    if (url.pathname === '/v1/workloads') return send(200, { items: [fixtureRecord], page: Number(url.searchParams.get('page')), page_size: 20, total: 1 });
    if (url.pathname === '/v1/verify/http-fixture-receipt') return send(200, { valid: true, receipt_handle: 'http-fixture-receipt', reason: 'synthetic_fixture_only', total_release_gates_evaluated: 0 });
    return send(404, { detail: 'Synthetic route not found' });
  });
  await new Promise((resolve) => fixtureBackend.listen(0, '127.0.0.1', resolve));
  const fixtureUrl = `http://127.0.0.1:${fixtureBackend.address().port}`;
  server = spawn(nextCommand, ['start', '--hostname', '127.0.0.1', '--port', String(port)], {
    cwd: process.cwd(),
    env: { ...process.env, CHRONUS_BACKEND_URL: fixtureUrl, NEXT_TELEMETRY_DISABLED: '1' },
    stdio: 'ignore',
  });

  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (server.exitCode !== null) throw new Error(`Next server exited with code ${server.exitCode}`);
    try {
      const response = await fetch(`${baseUrl}/ciaas/welcome`);
      if (response.ok) return;
    } catch {
      // The server is still starting; poll again.
    }
    await delay(250);
  }
  throw new Error('Next server did not become ready within 30 seconds');
});

after(async () => {
  if (fixtureBackend) { fixtureBackend.closeAllConnections(); await new Promise((resolve) => fixtureBackend.close(resolve)); }
  if (!server || server.exitCode !== null) return;
  server.kill('SIGTERM');
  await Promise.race([
    new Promise((resolve) => server.once('exit', resolve)),
    delay(2_000),
  ]);
  if (server.exitCode === null) server.kill('SIGKILL');
});

async function getHtml(path) {
  const response = await fetch(`${baseUrl}${path}`);
  assert.equal(response.status, 200, `${path} should return HTTP 200`);
  // React may insert comment delimiters between adjacent text nodes.
  // Exclude hydration scripts so assertions only inspect rendered markup.
  return (await response.text()).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<!--.*?-->/gs, '');
}

test('workload controller, API transport and Next proxy complete a synthetic HTTP journey without resubmitting', async () => {
  const { WorkloadJourney, buildWorkloadRequest, evidenceBundle } = await loadFrontendModule('workload-journey');
  const { ChronusAPIClient } = await loadFrontendModule('api-client');
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (url, init) => originalFetch(typeof url === 'string' && url.startsWith('/api/chronus') ? `${baseUrl}${url}` : url, init);
  try {
    const journey = new WorkloadJourney(ChronusAPIClient);
    await journey.submit(buildWorkloadRequest('http-fixture', 'guided', '10'), 'http-fixture-access');
    assert.equal(journey.getSnapshot().record?.data.status, 'QUEUED');
    await journey.inspect(fixtureRecord.workload_id, 'http-fixture', 'http-fixture-access');
    assert.equal(journey.getSnapshot().record?.data.status, 'COMPLETED');
    assert.equal(journey.getSnapshot().record.data.result.result.sequence_value, '123');
    await journey.verify();
    assert.equal(journey.getSnapshot().verification?.data.valid, true);
    await journey.loadHistory('http-fixture', 'http-fixture-access');
    assert.equal(journey.getSnapshot().history?.data.items.length, 1);
    assert.equal(fixtureSubmissions, 1);
    const exported = evidenceBundle(journey.getSnapshot());
    assert.equal(exported.workload.verification_receipt, 'http-fixture-receipt');
    assert.doesNotMatch(JSON.stringify(exported), /http-fixture-access/);
    journey.clear();
    await journey.loadHistory('http-fixture', '');
    assert.equal(journey.getSnapshot().historyIssue.title, 'Authentication required');
    assert.equal(journey.getSnapshot().history, null);
  } finally { globalThis.fetch = originalFetch; }
});

test('workload journey renders a usable, evidence-led empty state with accessible navigation', async () => {
  const html = await getHtml('/workloads');
  for (const text of ['HYBA Data / Chronus / Workloads', 'Run a workload. Inspect the evidence.', 'Configure request', 'Inspect execution', 'Review evidence', 'Sequence index', 'Guided calculation', 'Advanced JSON', 'No execution observed', 'History has not been requested', 'Sign-in and credential provisioning are not available here', 'Requests are never retried automatically']) {
    assert.ok(html.includes(text), `missing journey content: ${text}`);
  }
  assert.match(html, /href="#main-content"[^>]*>Skip to main content/);
  assert.match(html, /<main[^>]*id="main-content"[^>]*tabindex="-1"/);
  assert.match(html, /aria-label="Workload journey"/);
  assert.match(html, /aria-label="Run &amp; inspect workloads"[^>]*aria-current|aria-current="page"[^>]*aria-label="Run &amp; inspect workloads"/);
  assert.match(html, /<button[^>]*disabled[^>]*>Submit workload/);
  assert.match(html, /<input[^>]*type="password"/);
  assert.doesNotMatch(html, /href="\/mining"|Hashrate Observatory|Mining Intelligence/);
  assert.doesNotMatch(html, /Verifier reports valid|Execution completed|Production ready/);
});

test('overview leads with the implemented workload journey, not unsupported account or mining actions', async () => {
  const html = await getHtml('/');
  assert.match(html, /Your compute workspace/);
  assert.match(html, /From input to an inspectable result/);
  assert.match(html, /href="\/workloads"[^>]*>Open workloads/);
  assert.match(html, /aria-label="Primary navigation"/);
  assert.doesNotMatch(html, /href="\/mining"|Hashrate Observatory/);
});

test('welcome screen exposes the three metrics with inline provenance and an account action', async () => {
  const html = await getHtml('/ciaas/welcome');
  assert.match(html, /Welcome back\./);
  assert.match(html, /Avoided capex this period/);
  assert.match(html, /Speedup delivered/);
  assert.match(html, /Next invoice estimate/);
  assert.match(html, /Source: tenant settlement ledger\. Window: current billing period\. Last verified: not available\./);
  assert.match(html, /Source: verified benchmark artifact\. Window: current billing period\. Last verified: not available\./);
  assert.match(html, /Source: tenant settlement engine\. Window: current period to date\. Last verified: not available\./);
  assert.match(html, /href="\/ciaas\/account"[^>]*>.*View account/s);
  assert.match(html, /Sign-in is not available in this deployment\. Contact the platform operator\./);
  assert.doesNotMatch(html, /<dialog[\s>]|aria-modal="true"/i);
  assert.doesNotMatch(html, /<input\b[^>]*type="(?:password|email)"/i);
});

test('account overview refuses unsupported values and makes missing actions visible', async () => {
  const html = await getHtml('/ciaas/account');
  assert.match(html, /What is your account doing right now\?/);
  assert.match(html, /Account data unavailable/);
  assert.match(html, /Settlement and benchmark data are not available in this deployment\. Contact the platform operator\./);
  assert.match(html, /Live account feeds are not available in this deployment\. Contact the platform operator\./);
  assert.match(html, /href="\/ciaas\/provision"/);
  for (const label of ['Tier', 'Provisioned capacity and utilization', 'Avoided capex to date', 'Next invoice']) {
    assert.ok(html.includes(label), `missing account field: ${label}`);
  }
  assert.match(html, /Counterfactual spend − actual spend − incremental spend = avoided capex/);
  assert.match(html, /Source: tenant settlement engine\. Window: current billing period to date\. Last verified: not available\./);
  assert.match(html, /Capacity health/);
  assert.match(html, /Unverified/);
  assert.match(html, /Settlement history — unavailable/);
  assert.match(html, /Export data — unavailable/);
  assert.match(html, /Contact support — unavailable/);
  assert.match(html, /href="\/"[^>]*>.*Investigate service status/s);
});

test('welcome response completes within 1.2 seconds after warmup', async () => {
  await getHtml('/ciaas/welcome');
  const startedAt = performance.now();
  const response = await fetch(`${baseUrl}/ciaas/welcome`);
  const elapsedMs = performance.now() - startedAt;
  assert.equal(response.status, 200);
  assert.ok(elapsedMs < 1_200, `warm route took ${elapsedMs.toFixed(0)}ms`);
});

test('provisioning states unavailable sources and does not promise a working action', async () => {
  const html = await getHtml('/ciaas/provision');
  assert.match(html, /What do you need\?/);
  assert.match(html, /Provisioning is not available in this deployment\. Contact the platform operator\./);
  assert.match(html, /No capacity will be created/);
  assert.match(html, /Customer usage and approved default sizes are unavailable/);
  for (const option of ['Small', 'Medium', 'Large', 'Custom']) {
    assert.match(html, new RegExp(`>${option}</h3>`));
  }
  assert.match(html, /Projected cost — unavailable/);
  assert.match(html, /Source: tenant settlement projection\. Window: not available\. Last verified: not available\./);
  assert.match(html, /settlement window and charge date are not connected/);
  assert.match(html, /Projected avoided capex — unavailable/);
  assert.match(html, /Source: customer benchmark artifact\. Window: not available\. Last verified: not available\./);
  assert.match(html, /<button\b[^>]*disabled[^>]*>Provision — unavailable<\/button>/);
  assert.doesNotMatch(html, /Your capacity is live/);
  assert.doesNotMatch(html, /<input\b/i);
});
