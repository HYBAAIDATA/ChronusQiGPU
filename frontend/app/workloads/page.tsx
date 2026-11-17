'use client';

import React, { type FormEvent, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import { ArrowDown, ArrowRight, Download, RotateCw } from 'lucide-react';
import { StatusPill } from '@/components/console/status-pill';
import { ChronusAPIClient } from '@/lib/api-client';
import {
  WorkloadJourney, asObject, buildWorkloadRequest, describeExecution, evidenceBundle,
  isStale, verificationLabel, type JourneyIssue,
} from '@/lib/workload-journey';

function Issue({ issue }: { issue: JourneyIssue | null }) {
  if (!issue) return null;
  return <div role="alert" className="console-issue"><p className="font-semibold">{issue.title}</p><p className="mt-1 leading-6">{issue.action}</p></div>;
}
function SnapshotTime({ value }: { value: string }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  return <p className="text-xs leading-5 text-neutral-400">Source: Chronus API · observed <time dateTime={value}>{value}</time> · {isStale(value, now) ? 'Snapshot may be stale — refresh before relying on it.' : 'Point-in-time snapshot; not a live feed.'}</p>;
}
const shown = (value: unknown) => value === null || value === undefined ? 'Not reported' : String(value);

export default function WorkloadsPage() {
  const [journey] = useState(() => new WorkloadJourney(ChronusAPIClient));
  const state = useSyncExternalStore(journey.subscribe, journey.getSnapshot, journey.getSnapshot);
  const [tenantId, setTenantId] = useState('');
  const [credential, setCredential] = useState('');
  const [mode, setMode] = useState<'guided' | 'json'>('guided');
  const [index, setIndex] = useState('10');
  const [workloadType, setWorkloadType] = useState('scaling.v1');
  const [payload, setPayload] = useState('{"index":10}');
  const [validation, setValidation] = useState('');
  const [draftChanged, setDraftChanged] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const validationBox = useRef<HTMLDivElement>(null);
  const busy = state.pending !== null;
  const connected = Boolean(tenantId.trim() && credential.trim());
  const record = state.record?.data || null;
  const execution = describeExecution(record);
  const runtime = asObject(record?.result);
  const output = asObject(runtime?.result);
  const history = state.history?.data;
  const verification = state.verification?.data || null;
  const requestInput = mode === 'guided' ? index : payload;
  let requestPreview = '';
  try { requestPreview = JSON.stringify(buildWorkloadRequest(tenantId, mode, requestInput, workloadType), null, 2); } catch { /* Inline validation appears on submit. */ }

  useEffect(() => { if (state.record) { resultHeading.current?.focus(); setDownloaded(false); } }, [state.record]);
  useEffect(() => { if (validation) validationBox.current?.focus(); }, [validation]);
  useEffect(() => () => journey.clear(), [journey]);

  function changeIdentity(update: () => void) {
    journey.clear(); update(); setValidation(''); setDraftChanged(false); setDownloaded(false);
  }
  function changeDraft(update: () => void) { update(); setValidation(''); setDraftChanged(Boolean(record)); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !connected) return;
    setValidation('');
    let body;
    try { body = buildWorkloadRequest(tenantId, mode, requestInput, workloadType); }
    catch (cause) { setValidation(cause instanceof Error ? cause.message : 'Check your inputs.'); return; }
    setDraftChanged(false);
    await journey.submit(body, credential);
  }
  function downloadEvidence() {
    const bundle = evidenceBundle(state);
    if (!bundle) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2) + '\n'], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url; link.download = 'chronus-workload-observation.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
    setDownloaded(true);
  }

  return (
    <div className="space-y-7">
      <header className="space-y-3">
        <p className="console-eyebrow">HYBA Data / Chronus / Workloads</p>
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Run a workload. Inspect the evidence.</h1>
        <p className="max-w-3xl text-sm leading-6 text-neutral-300">Configure a calculation, submit it to your configured API, then inspect its actual result and receipt. No execution is inferred from service readiness.</p>
        <p className="text-xs leading-5 text-amber-200">Product preview · use non-sensitive inputs only. Reference execution and records may be process-local; persistence and hardware execution are not established here.</p>
      </header>

      <nav aria-label="Workload journey" className="grid gap-2 sm:grid-cols-3">
        {[['01', 'Configure request', '#configure'], ['02', 'Inspect execution', '#execution'], ['03', 'Review evidence', '#evidence']].map(([step, label, href]) => (
          <a key={step} href={href} className="flex min-h-12 items-center gap-3 rounded-xl border border-neutral-800 bg-neutral-900/50 px-4 py-3 text-sm text-neutral-200 hover:border-neutral-600"><span className="font-mono text-xs text-blue-300">{step}</span>{label}<ArrowDown aria-hidden="true" className="ml-auto h-4 w-4 text-neutral-400" /></a>
        ))}
      </nav>

      <section id="configure" aria-labelledby="configure-heading" className="console-panel scroll-mt-24">
        <div className="console-section-heading"><div><p className="console-eyebrow">01 / Input</p><h2 id="configure-heading" className="mt-1 text-xl font-semibold text-white">What would you like to calculate?</h2></div><StatusPill status="PREVIEW" label="API-backed preview" showDot={false} /></div>
        <form onSubmit={submit} className="mt-6 space-y-6">
          <fieldset disabled={busy} className="space-y-4">
            <legend className="mb-1 text-sm font-semibold text-neutral-100">Access your tenant</legend>
            <p id="access-help" className="text-xs leading-5 text-neutral-400">Sign-in and credential provisioning are not available here. Use access issued by your platform operator. Credentials stay in page memory and are cleared on reload or when you leave this page; they are never included in downloads.</p>
            <div className="grid gap-4 lg:grid-cols-2">
              <label className="console-label"><span>Tenant ID</span><input id="tenant-id" value={tenantId} onChange={(e) => changeIdentity(() => setTenantId(e.target.value))} required maxLength={128} autoComplete="off" autoCapitalize="none" spellCheck={false} aria-describedby="access-help" className="console-input" /></label>
              <label className="console-label"><span>Bearer credential</span><input type="password" value={credential} onChange={(e) => changeIdentity(() => setCredential(e.target.value))} required autoComplete="off" spellCheck={false} aria-describedby="access-help" className="console-input" /></label>
            </div>
          </fieldset>
          <fieldset disabled={busy} className="space-y-4 border-t border-neutral-800 pt-5">
            <legend className="px-1 text-sm font-semibold text-neutral-100">Configure the input</legend>
            <div className="flex flex-wrap gap-4 text-sm text-neutral-200">
              <label className="flex min-h-11 items-center gap-2"><input type="radio" name="input-mode" checked={mode === 'guided'} onChange={() => changeDraft(() => setMode('guided'))} className="h-4 w-4 accent-blue-400" />Guided calculation</label>
              <label className="flex min-h-11 items-center gap-2"><input type="radio" name="input-mode" checked={mode === 'json'} onChange={() => changeDraft(() => setMode('json'))} className="h-4 w-4 accent-blue-400" />Advanced JSON</label>
            </div>
            {mode === 'guided' ? <div className="grid gap-4 lg:grid-cols-2">
              <div><h3 className="font-medium text-neutral-100">Sequence calculation</h3><p id="index-help" className="mt-2 text-sm leading-6 text-neutral-400">Request the sequence and companion values at a non-negative whole-number index using <code>scaling.v1</code>. The API enforces its configured execution limits.</p></div>
              <label className="console-label"><span>Sequence index</span><input value={index} onChange={(e) => changeDraft(() => setIndex(e.target.value))} required inputMode="numeric" aria-describedby="index-help" aria-invalid={Boolean(validation)} className="console-input font-mono" /></label>
            </div> : <div className="grid gap-4 lg:grid-cols-2">
              <label className="console-label"><span>Workload class</span><select value={workloadType} onChange={(e) => changeDraft(() => setWorkloadType(e.target.value))} className="console-input"><option value="scaling.v1">Sequence calculation (scaling.v1)</option><option value="EXACT_Q5_ALGEBRAIC">Exact Q(√5) algebra</option><option value="PV_LATTICE_FOLD">Lattice fold</option></select><span className="text-xs leading-5 text-neutral-400">Use a JSON object that matches the selected API contract. Availability and input limits are checked by the backend.</span></label>
              <label className="console-label"><span>JSON payload</span><textarea value={payload} onChange={(e) => changeDraft(() => setPayload(e.target.value))} required rows={6} spellCheck={false} aria-invalid={Boolean(validation)} className="console-input resize-y font-mono text-xs" /></label>
            </div>}
          </fieldset>
          <details className="rounded-lg border border-neutral-800 p-4"><summary className="cursor-pointer text-sm font-medium text-neutral-200">Review request before sending</summary><p className="mt-3 text-xs text-neutral-400">POST /v1/workloads · authorization is sent separately and is not shown here.</p>{requestPreview ? <pre tabIndex={0} aria-label="Request JSON" className="console-code mt-3">{requestPreview}</pre> : <p className="mt-3 text-sm text-neutral-400">Enter a tenant ID and valid input to preview the request.</p>}</details>
          {validation && <div ref={validationBox} tabIndex={-1} role="alert" className="console-issue">{validation}</div>}
          <Issue issue={state.submitIssue} />
          <div className="flex flex-wrap items-center gap-3"><button type="submit" disabled={busy || !connected} className="console-button-primary">{state.pending === 'submit' ? 'Submitting request…' : 'Submit workload'}<ArrowRight aria-hidden="true" className="h-4 w-4" /></button><button type="button" onClick={() => changeIdentity(() => { setCredential(''); setTenantId(''); })} disabled={busy || (!credential && !tenantId)} className="console-button">Clear access and observations</button></div>
          {!connected && <p className="text-xs leading-5 text-neutral-400">A tenant ID and bearer credential are required to submit or read tenant records. This does not create an account.</p>}
          <p className="text-xs leading-5 text-neutral-400">Submission requests real execution on the configured service. Requests are never retried automatically; a timeout does not prove the workload did not run.</p>
        </form>
      </section>

      <p role="status" aria-live="polite" className="text-sm text-blue-200">{state.pending ? ({ submit: 'Waiting for the API submission response. No progress estimate is available.', record: 'Reading the selected workload record…', history: 'Reading tenant history…', verify: 'Waiting for the receipt verifier…' })[state.pending] : 'No request in progress.'}</p>

      <section id="execution" aria-labelledby="execution-heading" aria-busy={state.pending === 'submit' || state.pending === 'record'} className="console-panel scroll-mt-24">
        <div className="console-section-heading"><div><p className="console-eyebrow">02 / Actual execution state</p><h2 id="execution-heading" ref={resultHeading} tabIndex={-1} className="mt-1 text-xl font-semibold text-white">{execution.title}</h2></div>{record && <StatusPill status={record.status} showDot={false} />}</div>
        <p className="mt-3 text-sm leading-6 text-neutral-300">{execution.detail}</p>
        <Issue issue={state.recordIssue} />
        {draftChanged && record && <p className="mt-4 text-sm text-amber-200">The configuration has changed. This observation belongs to the earlier request, not your current draft.</p>}
        {record && state.record ? <div className="mt-5 space-y-5">
          <SnapshotTime value={state.record.observedAt} />
          <dl className="grid gap-4 rounded-lg border border-neutral-800 bg-neutral-950 p-4 text-sm sm:grid-cols-2">
            {[['Workload ID', record.workload_id], ['Workload class', record.workload_type], ['Submitted (API time)', record.submitted_at], ['Completed (API time)', record.completed_at], ['Execution backend (API-reported)', runtime?.backend], ['Execution duration (API-reported, ms)', runtime?.duration_ms]].map(([label, value]) => <div key={String(label)} className="min-w-0"><dt className="text-xs text-neutral-400">{String(label)}</dt><dd className="mt-1 break-all font-mono text-xs leading-6 text-neutral-100">{shown(value)}</dd></div>)}
          </dl>
          {record.status === 'COMPLETED' && output?.family === 'scaling.v1' && <div className="grid gap-4 sm:grid-cols-2">{[['Sequence value', output.sequence_value], ['Companion value', output.companion_value]].map(([label, value]) => <div key={String(label)} className="min-w-0 rounded-lg border border-blue-400/20 bg-blue-400/5 p-4"><h3 className="text-xs font-medium text-blue-200">{String(label)}</h3><p className="mt-2 max-h-48 overflow-auto break-all font-mono text-xl text-white">{shown(value)}</p><p className="mt-2 text-xs text-neutral-400">API-returned value · index {shown(output.index)}</p></div>)}</div>}
          {!runtime && <p className="text-sm text-neutral-400">No result is attached to this snapshot. Refresh the record if execution is still in progress.</p>}
          {record.status === 'FAILED' && <p className="console-issue">API failure detail: {shown(record.error_message)}</p>}
          <div className="flex flex-wrap gap-3"><button type="button" disabled={busy || !connected} onClick={() => void journey.inspect(record.workload_id, tenantId, credential)} className="console-button"><RotateCw aria-hidden="true" className="h-4 w-4" />Refresh this record</button><a href="#configure" className="console-button">Configure another request</a></div>
          <details className="rounded-lg border border-neutral-800 p-4"><summary className="cursor-pointer text-sm font-medium text-neutral-200">Inspect full API response and tier evidence</summary><p className="mt-3 text-xs leading-5 text-neutral-400">API-reported tier, envelope and evidence hashes are not independent qualification. Backend names and timings do not establish physical hardware execution or comparative performance.</p><pre tabIndex={0} aria-label="Workload API response" className="console-code mt-3">{JSON.stringify(record, null, 2)}</pre></details>
        </div> : <div className="mt-5 rounded-lg border border-dashed border-neutral-700 p-6 text-sm leading-6 text-neutral-400">{state.pending === 'submit' ? 'Request sent. Waiting for an actual API response; no result is available yet.' : 'No workload record is confirmed in this view. Submit a request above, or load history below to inspect an existing record.'}</div>}
      </section>

      <section id="evidence" aria-labelledby="evidence-heading" className="console-panel scroll-mt-24">
        <div><p className="console-eyebrow">03 / Evidence and next action</p><h2 id="evidence-heading" className="mt-1 text-xl font-semibold text-white">Can you inspect the receipt?</h2></div>
        <p className="mt-3 text-sm leading-6 text-neutral-300">Receipt verification reports only what the configured verifier evaluates. It does not qualify a release, certify security or prove external hardware execution.</p>
        {record ? <div className="mt-5 space-y-4">
          <div className="rounded-lg border border-neutral-800 bg-neutral-950 p-4"><p className="text-xs text-neutral-400">Receipt identifier from workload response</p><p className="mt-2 break-all font-mono text-xs leading-6 text-neutral-100">{record.verification_receipt || 'No receipt attached to this snapshot.'}</p></div>
          {!record.verification_receipt && <p className="text-sm text-neutral-400">Verification is unavailable until the API attaches a receipt. You can still download the observation or refresh the record.</p>}
          <Issue issue={state.verificationIssue} />
          {state.verification && <div className="space-y-3 rounded-lg border border-neutral-700 p-4"><h3 role="status" className="font-semibold text-neutral-100">{verificationLabel(verification)}</h3><SnapshotTime value={state.verification.observedAt} /><p className="text-sm text-neutral-300">Reason: {shown(verification?.reason)}</p><details><summary className="cursor-pointer text-sm text-neutral-200">Inspect verifier response</summary><pre tabIndex={0} aria-label="Receipt verifier response" className="console-code mt-3">{JSON.stringify(verification, null, 2)}</pre></details></div>}
          <div className="flex flex-wrap gap-3"><button type="button" onClick={() => void journey.verify()} disabled={busy || !record.verification_receipt} className="console-button">{state.pending === 'verify' ? 'Verifying receipt…' : 'Verify attached receipt'}</button><button type="button" onClick={downloadEvidence} disabled={busy} className="console-button"><Download aria-hidden="true" className="h-4 w-4" />Download observation JSON</button></div>
          <p className="text-xs leading-5 text-neutral-400">The download contains the observed result, identifiers, timestamps and any verifier response, not your bearer credential or input payload. Treat results as potentially sensitive. It is an observation, not an attestation.</p>
          <p role="status" className="text-xs text-blue-200">{downloaded ? 'Observation download requested. Check your browser downloads.' : ''}</p>
        </div> : <p className="mt-5 text-sm text-neutral-400">Inspect a workload first. Receipt verification and evidence download become available only when there is an observed record.</p>}
      </section>

      <section aria-labelledby="history-heading" aria-busy={state.pending === 'history'} className="console-panel">
        <div className="console-section-heading"><div><p className="console-eyebrow">Continue existing work</p><h2 id="history-heading" className="mt-1 text-xl font-semibold text-white">Your tenant records</h2></div><button type="button" onClick={() => void journey.loadHistory(tenantId, credential)} disabled={busy || !connected} className="console-button">{state.pending === 'history' ? 'Loading history…' : state.history ? 'Refresh history' : 'Load history'}</button></div>
        <p className="mt-3 text-sm leading-6 text-neutral-400">Read existing records without submitting again. Access is enforced by the API. History is loaded separately so a failed read cannot turn a completed submission into a failure.</p>
        <Issue issue={state.historyIssue} />
        {history && state.history ? <div className="mt-5 space-y-4">
          <SnapshotTime value={state.history.observedAt} />
          {record && <p className="text-xs text-neutral-400">History is a separate snapshot. Refresh it to include subsequent submissions or status changes.</p>}
          {history.items.length === 0 ? <p className="rounded-lg border border-dashed border-neutral-700 p-6 text-sm text-neutral-300">No records were returned for this tenant on this page. Configure a request above, or check another page.</p> : <ul className="space-y-2">{history.items.map((item) => <li key={item.workload_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-neutral-800 bg-neutral-950 p-4"><div className="min-w-0 flex-1 basis-48"><p className="break-all font-mono text-xs leading-5 text-neutral-100">{item.workload_id}</p><p className="mt-1 text-xs leading-5 text-neutral-400">{item.workload_type} · submitted {shown(item.submitted_at)}</p></div><StatusPill status={item.status} showDot={false} /><button type="button" onClick={() => { setDraftChanged(false); void journey.inspect(item.workload_id, tenantId, credential); }} disabled={busy || !connected} aria-label={`Inspect workload ${item.workload_id}`} className="console-button">Inspect<ArrowRight aria-hidden="true" className="h-4 w-4" /></button></li>)}</ul>}
          <div className="flex flex-wrap items-center gap-3"><p className="mr-auto text-xs text-neutral-400">{history.total} records reported · page {history.page} · up to 20 per page</p><button type="button" onClick={() => void journey.loadHistory(tenantId, credential, history.page - 1)} disabled={busy || !connected || history.page <= 1} className="console-button">Previous page</button><button type="button" onClick={() => void journey.loadHistory(tenantId, credential, history.page + 1)} disabled={busy || !connected || history.page * 20 >= history.total} className="console-button">Next page</button></div>
        </div> : <p className="mt-5 rounded-lg border border-dashed border-neutral-700 p-6 text-sm text-neutral-400">History has not been requested. No tenant records or activity counts are assumed.</p>}
      </section>
      <details className="console-panel"><summary className="cursor-pointer text-sm font-medium text-neutral-200">Connection and API contract</summary><p className="mt-3 text-sm leading-6 text-neutral-400">Requests use the same-origin <code>/api/chronus</code> proxy to the operator-configured backend. Tenant access is checked by the API, not by local form state. Record and verification timestamps are observations, not durable audit attestations.</p><ul className="mt-3 space-y-2 font-mono text-xs leading-6 text-neutral-300"><li>POST /v1/workloads — submit tenant_id, workload_type and JSON text in payload_bytes</li><li>GET /v1/workloads?page=1&amp;page_size=20 — tenant history</li><li>GET /v1/workloads/{'{workload_id}'} — refresh a single execution record</li><li>GET /v1/verify/{'{receipt_identifier}'} — inspect the public receipt verifier response</li></ul></details>
      <p className="text-xs leading-6 text-neutral-400">Connection unavailable? <Link href="/" className="text-blue-300 underline underline-offset-4">Inspect service readiness and setup</Link>. A ready API is not a guarantee that your workload can execute.</p>
    </div>
  );
}
