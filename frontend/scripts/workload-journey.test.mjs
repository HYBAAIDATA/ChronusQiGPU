import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

// Use the declared compiler so this suite also runs on the documented Node 20 minimum.
const source = await readFile(new URL('../lib/workload-journey.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { WorkloadJourney, buildWorkloadRequest, createWorkloadPageActions, describeExecution, downloadObservation, evidenceBundle, isStale, requestIssue, verificationLabel } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputText).toString('base64')}`);

// Synthetic transport fixtures only: these tests do not execute a backend or use real credentials.
const observedAt = '2026-11-16T09:00:00.000Z';
const record = (patch = {}) => ({
  workload_id: '24c42c58-6ad6-4d2f-9d31-c1dbf0412a9b', tenant_id: 'fixture-tenant',
  workload_type: 'scaling.v1', status: 'COMPLETED', submitted_at: observedAt,
  result: { backend: 'fixture-reference', duration_ms: 2, result: { family: 'scaling.v1', index: 10, sequence_value: '123', companion_value: '55' } },
  verification_receipt: 'fixture-receipt', ...patch,
});
const body = () => buildWorkloadRequest('fixture-tenant', 'guided', '10');
function setup(overrides = {}) {
  const calls = [];
  const transport = {
    dispatchWorkload: async (...args) => { calls.push(['submit', ...args]); return record(); },
    getWorkload: async (...args) => { calls.push(['record', ...args]); return record(); },
    getWorkloads: async (...args) => { calls.push(['history', ...args]); return { items: [record()], total: 1, page: args[1] }; },
    verifyReceipt: async (...args) => { calls.push(['verify', ...args]); return { valid: true, receipt_handle: 'fixture-receipt', reason: 'ok', total_release_gates_evaluated: 0 }; },
    ...overrides,
  };
  return { calls, journey: new WorkloadJourney(transport, () => observedAt) };
}

test('guided and advanced requests validate input and match the existing API wire contract', () => {
  assert.deepEqual(buildWorkloadRequest(' fixture-tenant ', 'guided', ' 10 '), {
    tenant_id: 'fixture-tenant', workload_type: 'scaling.v1', payload_bytes: '{"index":10}',
  });
  for (const index of ['', ' ', '-1', '1.5', '1e3', 'abc', '9007199254740992']) {
    assert.throws(() => buildWorkloadRequest('fixture-tenant', 'guided', index), /whole-number/);
  }
  assert.equal(buildWorkloadRequest('fixture-tenant', 'guided', '0').payload_bytes, '{"index":0}');
  assert.throws(() => buildWorkloadRequest(' ', 'guided', '10'), /tenant ID/);
  assert.throws(() => buildWorkloadRequest('x'.repeat(129), 'guided', '10'), /tenant ID/);
  for (const payload of ['{', '[]', 'null', '1', '"text"']) assert.throws(() => buildWorkloadRequest('fixture-tenant', 'json', payload), /JSON/);
  assert.equal(buildWorkloadRequest('fixture-tenant', 'json', '{"index":12}').payload_bytes, '{"index":12}');
  assert.equal(buildWorkloadRequest('fixture-tenant', 'json', '{"operation":"test"}', 'EXACT_Q5_ALGEBRAIC').workload_type, 'EXACT_Q5_ALGEBRAIC');
});

test('complete journey submits once, reads the same record, verifies its attached receipt and exports scoped evidence', async () => {
  const { journey, calls } = setup();
  const transitions = [];
  const unsubscribe = journey.subscribe(() => transitions.push(journey.getSnapshot().pending));
  assert.equal(evidenceBundle(journey.getSnapshot()), null);
  await journey.submit(body(), ' fixture-access ');
  assert.equal(journey.getSnapshot().record.data.result.result.sequence_value, '123');
  assert.equal(describeExecution(journey.getSnapshot().record.data).title, 'Execution completed');
  await journey.inspect(record().workload_id, 'fixture-tenant', 'fixture-access');
  await journey.verify();
  await journey.loadHistory('fixture-tenant', 'fixture-access');
  assert.deepEqual(calls.map(([name]) => name), ['submit', 'record', 'verify', 'history']);
  assert.equal(calls[0][2], 'fixture-access');
  assert.deepEqual(calls[2], ['verify', 'fixture-receipt']);
  assert.deepEqual(transitions, ['submit', 'submit', null, 'record', 'record', null, 'verify', 'verify', null, 'history', 'history', null]);
  const evidence = evidenceBundle(journey.getSnapshot());
  assert.equal(evidence.observed_at, observedAt);
  assert.equal(evidence.verification.response.valid, true);
  assert.equal(evidence.verification.response.total_release_gates_evaluated, 0);
  assert.match(evidence.scope, /not independent verification/);
  assert.doesNotMatch(JSON.stringify(evidence), /fixture-access|payload_bytes/);
  unsubscribe();
});

test('pending execution is an API snapshot; refreshing reads status without duplicate submission', async () => {
  let resolve;
  let submissions = 0;
  const { journey, calls } = setup({ dispatchWorkload: () => { submissions += 1; return new Promise((done) => { resolve = done; }); } });
  const waiting = journey.submit(body(), 'fixture-access');
  assert.equal(journey.getSnapshot().pending, 'submit');
  assert.equal(journey.getSnapshot().record, null);
  await journey.submit(body(), 'fixture-access');
  assert.equal(submissions, 1);
  resolve(record({ status: 'QUEUED', result: null, verification_receipt: null }));
  await waiting;
  assert.match(describeExecution(journey.getSnapshot().record.data).detail, /without resubmitting/);
  await journey.verify();
  assert.equal(calls.length, 0, 'no verifier request without a receipt');
  await journey.inspect(record().workload_id, 'fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().record.data.status, 'COMPLETED');
  assert.equal(submissions, 1);
  assert.deepEqual(calls.map(([name]) => name), ['record']);
});

test('a failed history read preserves a completed result and the previous history snapshot', async () => {
  let unavailable = false;
  const { journey } = setup({ getWorkloads: async () => {
    if (unavailable) throw { status: 503 };
    return { items: [], total: 0, page: 1 };
  } });
  await journey.submit(body(), 'fixture-access');
  await journey.loadHistory('fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().history.data.total, 0, 'empty history is observed, not assumed');
  unavailable = true;
  await journey.loadHistory('fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().record.data.status, 'COMPLETED');
  assert.equal(journey.getSnapshot().history.data.total, 0);
  assert.equal(journey.getSnapshot().submitIssue, null);
  assert.equal(journey.getSnapshot().historyIssue.title, 'Observation unavailable');
});

test('unknown submission outcome never retries or fabricates a result; history remains a recovery path', async () => {
  let attempts = 0;
  const { journey } = setup({ dispatchWorkload: async () => { attempts += 1; throw { status: 0 }; } });
  await journey.submit(body(), 'fixture-access');
  assert.equal(attempts, 1);
  assert.equal(journey.getSnapshot().record, null);
  assert.equal(journey.getSnapshot().submitIssue.title, 'Submission outcome unknown');
  assert.match(journey.getSnapshot().submitIssue.action, /load history/);
  await journey.loadHistory('fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().history.data.items.length, 1);
});

test('permission, authentication, rate and validation failures have explicit recovery guidance', async () => {
  for (const [status, title] of [[401, 'Authentication required'], [403, 'Permission denied'], [429, 'Request rate limited'], [422, 'Request rejected']]) {
    const { journey } = setup({ dispatchWorkload: async () => { throw { status, message: 'Do not reflect arbitrary upstream text' }; } });
    await journey.submit(body(), 'fixture-access');
    assert.equal(journey.getSnapshot().submitIssue.title, title);
    assert.equal(journey.getSnapshot().record, null);
    assert.doesNotMatch(JSON.stringify(journey.getSnapshot()), /arbitrary upstream/);
  }
  assert.equal(requestIssue({ status: 404 }).title, 'Record unavailable');
});

test('failed, cancelled and recovering executions remain distinct from completed results', async () => {
  for (const [status, title] of [['FAILED', 'Execution failed'], ['CANCELLED', 'Execution cancelled'], ['RECOVERING', 'Execution recovering']]) {
    const { journey } = setup({ dispatchWorkload: async () => record({ status, result: null }) });
    await journey.submit(body(), 'fixture-access');
    assert.equal(journey.getSnapshot().record.data.status, status);
    assert.equal(describeExecution(journey.getSnapshot().record.data).title, title);
    assert.equal(journey.getSnapshot().submitIssue, null);
  }
});

test('unexpected tenant, record identity and malformed history fail closed without invented empty or successful states', async () => {
  const { journey } = setup({
    dispatchWorkload: async () => record({ tenant_id: 'other-tenant' }),
    getWorkload: async () => record({ workload_id: 'different-record' }),
    getWorkloads: async () => ({ items: [record({ tenant_id: 'other-tenant' })], total: 1, page: 1 }),
  });
  await journey.submit(body(), 'fixture-access');
  assert.equal(journey.getSnapshot().record, null);
  await journey.inspect(record().workload_id, 'fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().record, null);
  await journey.loadHistory('fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().history, null);
  assert.ok(journey.getSnapshot().historyIssue);
  const malformed = setup({ getWorkloads: async () => ({}) }).journey;
  await malformed.loadHistory('fixture-tenant', 'fixture-access');
  assert.equal(malformed.getSnapshot().history, null);
});

test('verifier valid, invalid, missing and unassessed outcomes preserve their actual meaning', async () => {
  for (const [response, label] of [
    [{ valid: true, receipt_handle: 'fixture-receipt' }, 'Verifier reports valid'],
    [{ valid: false, receipt_handle: 'fixture-receipt' }, 'Verifier reports invalid'],
    [{ valid: false, reason: 'not_found' }, 'Receipt not found in this API process'],
    [{ valid: null, receipt_handle: 'fixture-receipt' }, 'Validity not established'],
  ]) {
    const { journey } = setup({ verifyReceipt: async () => response });
    await journey.submit(body(), 'fixture-access');
    await journey.verify();
    assert.equal(verificationLabel(journey.getSnapshot().verification.data), label);
  }
  const { journey } = setup({ verifyReceipt: async () => ({ valid: true, receipt_handle: 'unrelated' }) });
  await journey.submit(body(), 'fixture-access');
  await journey.verify();
  assert.equal(journey.getSnapshot().verification, null);
  assert.ok(journey.getSnapshot().verificationIssue);
});

test('changing receipt invalidates earlier verification; a failed read retains its explicitly dated snapshot', async () => {
  let receipt = 'fixture-receipt';
  let fail = false;
  const { journey } = setup({ getWorkload: async () => { if (fail) throw { status: 503 }; return record({ verification_receipt: receipt }); } });
  await journey.submit(body(), 'fixture-access');
  await journey.verify();
  await journey.inspect(record().workload_id, 'fixture-tenant', 'fixture-access');
  assert.ok(journey.getSnapshot().verification);
  fail = true;
  await journey.inspect(record().workload_id, 'fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().record.observedAt, observedAt);
  assert.ok(journey.getSnapshot().recordIssue);
  fail = false; receipt = 'new-fixture-receipt';
  await journey.inspect(record().workload_id, 'fixture-tenant', 'fixture-access');
  assert.equal(journey.getSnapshot().verification, null);
});

test('clearing access discards observations and ignores a late response from the previous identity', async () => {
  let resolve;
  const { journey } = setup({ dispatchWorkload: () => new Promise((done) => { resolve = done; }) });
  const pending = journey.submit(body(), 'fixture-access');
  journey.clear();
  resolve(record());
  await pending;
  assert.equal(journey.getSnapshot().record, null);
  assert.equal(journey.getSnapshot().pending, null);
  assert.doesNotMatch(JSON.stringify(journey.getSnapshot()), /fixture-access|fixture-tenant/);
});

test('evidence omits unapproved metadata and callbacks; stale observations are labelled at sixty seconds', async () => {
  const { journey } = setup({ dispatchWorkload: async () => record({ metadata: { internal_note: 'not-for-export' }, callback_url: 'not-for-export', payload_bytes: 'not-for-export' }) });
  await journey.submit(body(), 'fixture-access');
  assert.doesNotMatch(JSON.stringify(evidenceBundle(journey.getSnapshot())), /not-for-export|metadata|callback_url|payload_bytes/);
  assert.equal(isStale(observedAt, Date.parse(observedAt) + 59_999), false);
  assert.equal(isStale(observedAt, Date.parse(observedAt) + 60_000), true);
  assert.equal(isStale('invalid'), true);
});

function pageActions(journey, download) {
  const draft = { tenantId: 'fixture-tenant', credential: 'fixture-access', mode: 'guided', input: '10', workloadType: 'scaling.v1' };
  const view = { validation: '', draftChanged: false, downloaded: false, downloadError: '' };
  const actions = createWorkloadPageActions({
    journey, getDraft: () => draft, download,
    setTenantId: (value) => { draft.tenantId = value; },
    setCredential: (value) => { draft.credential = value; },
    setValidation: (value) => { view.validation = value; },
    setDraftChanged: (value) => { view.draftChanged = value; },
    setDownloaded: (value) => { view.downloaded = value; },
    setDownloadError: (value) => { view.downloadError = value; },
  });
  return { draft, view, actions };
}

test('page submission handler prevents navigation, validates before transport, and submits the configured draft once', async () => {
  const { journey, calls } = setup();
  const { draft, view, actions } = pageActions(journey);
  let prevented = 0;
  const event = { preventDefault() { prevented += 1; } };
  draft.input = 'invalid';
  await actions.submit(event);
  assert.match(view.validation, /whole-number/);
  assert.equal(calls.length, 0);
  draft.mode = 'json'; draft.input = '[]';
  await actions.submit(event);
  assert.match(view.validation, /JSON payload must be an object/);
  assert.equal(calls.length, 0);
  draft.mode = 'guided'; draft.input = '10';
  await actions.submit(event);
  assert.equal(prevented, 3);
  assert.equal(view.validation, '');
  assert.deepEqual(calls, [['submit', body(), 'fixture-access']]);
  assert.equal(journey.getSnapshot().record.data.status, 'COMPLETED');
});

test('page handlers ignore submission without access and guard clear/download while a request is pending', async () => {
  let resolve;
  const { journey } = setup({ dispatchWorkload: () => new Promise((done) => { resolve = done; }) });
  let downloads = 0;
  const { draft, actions } = pageActions(journey, () => { downloads += 1; });
  draft.credential = ' ';
  await actions.submit({ preventDefault() {} });
  assert.equal(journey.getSnapshot().pending, null);
  draft.credential = 'fixture-access';
  const waiting = actions.submit({ preventDefault() {} });
  actions.clearAccess(); actions.downloadEvidence();
  assert.equal(draft.credential, 'fixture-access');
  assert.equal(journey.getSnapshot().pending, 'submit');
  assert.equal(downloads, 0);
  resolve(record()); await waiting;
});

test('page clear-access handler clears both credentials and every retained observation and message', async () => {
  const { journey } = setup();
  const { draft, view, actions } = pageActions(journey);
  await actions.submit({ preventDefault() {} });
  await journey.verify();
  await journey.loadHistory(draft.tenantId, draft.credential);
  Object.assign(view, { validation: 'old validation', draftChanged: true, downloaded: true, downloadError: 'old failure' });
  actions.clearAccess();
  assert.equal(draft.tenantId, '');
  assert.equal(draft.credential, '');
  assert.deepEqual(view, { validation: '', draftChanged: false, downloaded: false, downloadError: '' });
  for (const field of ['record', 'history', 'verification', 'submitIssue', 'recordIssue', 'historyIssue', 'verificationIssue', 'pending']) assert.equal(journey.getSnapshot()[field], null);
});

test('page inspection handler preserves draft-mismatch warning and the old result after a failed history inspection', async () => {
  const { journey } = setup({ getWorkload: async () => { throw { status: 503 }; } });
  const { draft, view, actions } = pageActions(journey);
  await actions.submit({ preventDefault() {} });
  const previous = journey.getSnapshot().record;
  actions.changeDraft(() => { draft.input = '20'; });
  assert.equal(view.draftChanged, true);
  await actions.inspect('a-different-history-record');
  assert.equal(journey.getSnapshot().record, previous);
  assert.equal(journey.getSnapshot().record.data.result.result.index, 10);
  assert.equal(draft.input, '20');
  assert.equal(view.draftChanged, true, 'a failed read must not remove the earlier-request warning');
  assert.equal(journey.getSnapshot().recordIssue.title, 'Observation unavailable');
});

function downloadEnvironment(click = () => {}) {
  const effects = { blobs: [], revoked: [], deferred: [], link: { href: '', download: '', click } };
  return { effects, environment: {
    createObjectURL: (blob) => { effects.blobs.push(blob); return 'blob:synthetic-fixture'; },
    revokeObjectURL: (url) => effects.revoked.push(url),
    createLink: () => effects.link,
    defer: (callback, delay) => effects.deferred.push({ callback, delay }),
  } };
}

test('page download handler creates the actual scoped JSON Blob, names/clicks the link and schedules URL cleanup', async () => {
  const { journey } = setup();
  let clicks = 0;
  const { effects, environment } = downloadEnvironment(() => { clicks += 1; });
  const { view, actions } = pageActions(journey, (bundle) => downloadObservation(bundle, environment));
  actions.downloadEvidence();
  assert.equal(effects.blobs.length, 0, 'empty view cannot fabricate an observation download');
  await actions.submit({ preventDefault() {} });
  actions.downloadEvidence();
  assert.equal(clicks, 1);
  assert.equal(effects.link.href, 'blob:synthetic-fixture');
  assert.equal(effects.link.download, 'chronus-workload-observation.json');
  assert.equal(effects.blobs[0].type, 'application/json');
  const text = await effects.blobs[0].text();
  assert.deepEqual(JSON.parse(text), evidenceBundle(journey.getSnapshot()));
  assert.doesNotMatch(text, /fixture-access|payload_bytes/);
  assert.equal(view.downloaded, true);
  assert.equal(view.downloadError, '');
  assert.equal(effects.revoked.length, 0);
  assert.equal(effects.deferred[0].delay, 1_000);
  effects.deferred[0].callback();
  assert.deepEqual(effects.revoked, ['blob:synthetic-fixture']);
});

test('a download API failure reports recovery instead of a successful download and still cleans up its URL', async () => {
  const { journey } = setup();
  const { effects, environment } = downloadEnvironment(() => { throw new Error('synthetic browser API failure'); });
  const { view, actions } = pageActions(journey, (bundle) => downloadObservation(bundle, environment));
  await actions.submit({ preventDefault() {} });
  actions.downloadEvidence();
  assert.equal(view.downloaded, false);
  assert.match(view.downloadError, /Download could not be started/);
  effects.deferred[0].callback();
  assert.deepEqual(effects.revoked, ['blob:synthetic-fixture']);
});

test('WorkloadsPage binds the tested submit, clear, download and inspection handlers without separate inline action logic', async () => {
  const page = await readFile(new URL('../app/workloads/page.tsx', import.meta.url), 'utf8');
  assert.match(page, /<form onSubmit=\{actions\.submit\}/);
  assert.match(page, /onClick=\{actions\.clearAccess\}/);
  assert.match(page, /onClick=\{actions\.downloadEvidence\}/);
  assert.match(page, /onClick=\{\(\) => void actions\.inspect\(item\.workload_id\)\}/);
});
