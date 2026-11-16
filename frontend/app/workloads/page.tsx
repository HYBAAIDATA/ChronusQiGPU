'use client';

import React, { FormEvent, useState } from 'react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import { ChronusAPIClient, type ApiRecord } from '@/lib/api-client';

type EnvelopePoint = { size?: number; max_residual?: string };

export default function WorkloadsPage() {
  const [tenantId, setTenantId] = useState('');
  const [token, setToken] = useState('');
  const [workloadType, setWorkloadType] = useState('scaling.v1');
  const [payload, setPayload] = useState('{"index":10}');
  const [result, setResult] = useState<ApiRecord | null>(null);
  const [history, setHistory] = useState<ApiRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setResult(null);
    let parsed: unknown;
    try { parsed = JSON.parse(payload); } catch { setError('Payload must be valid JSON.'); return; }
    setBusy(true);
    try {
      const response = await ChronusAPIClient.dispatchWorkload({ tenant_id: tenantId.trim(), workload_type: workloadType, payload_bytes: JSON.stringify(parsed) }, token.trim());
      setResult(response);
      setHistory(await ChronusAPIClient.getWorkloads(token.trim(), 1, 20));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Workload request failed.'); }
    finally { setBusy(false); }
  }

  async function refreshHistory() {
    setError(''); setBusy(true);
    try { setHistory(await ChronusAPIClient.getWorkloads(token.trim(), 1, 20)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not retrieve workload history.'); }
    finally { setBusy(false); }
  }

  const items: ApiRecord[] = Array.isArray(history?.items) ? history.items : [];
  const envelopePoints: EnvelopePoint[] = Array.isArray((result?.envelope as { residual_bound?: EnvelopePoint[] } | undefined)?.residual_bound)
    ? ((result?.envelope as { residual_bound: EnvelopePoint[] }).residual_bound)
    : [];

  return (
    <div className="space-y-7">
      <header className="space-y-2 border-b border-neutral-800 pb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Operations / Workloads</p>
        <h1 className="text-3xl font-semibold tracking-tight text-white">Workload console</h1>
        <p className="max-w-3xl text-sm leading-6 text-neutral-400">
          Submit a request to the configured API using your tenant credentials.
          Tier class is assigned by measured convergence behavior under our qualification harness.
          In native reference mode, execution uses the local reference backend; persistence and production
          characteristics depend on deployment configuration and are not established here.
          Do not submit sensitive production data in this preview.
        </p>
      </header>
      <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
        <div className="mb-5 flex items-center justify-between gap-3"><div><h2 className="font-semibold text-white">Submit workload</h2><p className="mt-1 text-xs text-neutral-500">The API validates tenant identity and reports its actual response.</p></div><StatusPill status="PREVIEW" label="Reference API" showDot={false} /></div>
        <form onSubmit={submit} className="grid gap-4 lg:grid-cols-2">
          <label className="space-y-1.5 text-sm text-neutral-300"><span>Tenant ID</span><input value={tenantId} onChange={(e) => setTenantId(e.target.value)} required maxLength={128} autoComplete="organization" className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20" /></label>
          <label className="space-y-1.5 text-sm text-neutral-300"><span>Bearer token</span><input type="password" value={token} onChange={(e) => setToken(e.target.value)} required autoComplete="off" className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20" /><span className="block text-xs text-neutral-500">Used only for this browser session; not saved by this page.</span></label>
          <label className="space-y-1.5 text-sm text-neutral-300"><span>Workload class</span><select value={workloadType} onChange={(e) => setWorkloadType(e.target.value)} className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-400"><option value="scaling.v1">scaling.v1</option><option value="EXACT_Q5_ALGEBRAIC">Exact Q(√5) algebra</option><option value="PV_LATTICE_FOLD">PV lattice fold</option></select></label>
          <label className="space-y-1.5 text-sm text-neutral-300 lg:row-span-2"><span>JSON payload</span><textarea value={payload} onChange={(e) => setPayload(e.target.value)} required rows={6} spellCheck={false} className="w-full resize-y rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 font-mono text-xs text-neutral-100 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20" /></label>
          <div className="flex flex-wrap items-end gap-2"><button type="submit" disabled={busy || !tenantId.trim() || !token.trim()} className="rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50">{busy ? 'Sending…' : 'Submit workload'}</button><button type="button" onClick={() => void refreshHistory()} disabled={busy || !token.trim()} className="rounded-lg border border-neutral-700 px-4 py-2.5 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50">Refresh history</button></div>
        </form>
        {error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">{error}</p>}
      </Card>
      {result && (
        <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="font-semibold text-white">API response</h2>
            <StatusPill status={String(result.status || 'RESPONSE')} showDot={false} />
          </div>
          {(result.tier || result.qualification_evidence_hash) && (
            <div className="mb-4 grid gap-3 rounded-lg border border-neutral-800 bg-neutral-950/70 p-4 sm:grid-cols-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-neutral-500">Current tier</p>
                <p className="mt-1 font-mono text-sm text-white">{String(result.tier || 'unassigned')}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-neutral-500">Contract</p>
                <p className="mt-1 font-mono text-sm text-neutral-200">{String(result.tier_contract_version || '—')}</p>
              </div>
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-wide text-neutral-500">Evidence hash</p>
                <p className="mt-1 truncate font-mono text-xs text-neutral-300">{String(result.qualification_evidence_hash || '—')}</p>
              </div>
              {envelopePoints.length > 0 && (
                <div className="sm:col-span-3">
                  <p className="text-xs uppercase tracking-wide text-neutral-500">Envelope (max residual by size)</p>
                  <ul className="mt-2 grid gap-1 font-mono text-xs text-neutral-300 sm:grid-cols-2">
                    {envelopePoints.map((point) => (
                      <li key={`${point.size}-${point.max_residual}`}>
                        size={String(point.size)} → max_residual={String(point.max_residual)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          <pre className="max-h-96 overflow-auto rounded-lg border border-neutral-800 bg-neutral-950 p-4 text-xs leading-5 text-neutral-300">{JSON.stringify(result, null, 2)}</pre>
          <p className="mt-3 text-xs text-neutral-500">A receipt signature, if present, is not a release qualification or a guarantee of external hardware execution.</p>
        </Card>
      )}
      <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><div className="mb-4 flex items-center justify-between gap-3"><div><h2 className="font-semibold text-white">Recent workload records</h2><p className="mt-1 text-xs text-neutral-500">Loaded only after an authenticated request.</p></div>{typeof history?.total === 'number' && <span className="text-xs text-neutral-400">{history.total} total · page {history.page}</span>}</div>{items.length === 0 ? <p className="rounded-lg border border-dashed border-neutral-800 px-4 py-8 text-center text-sm text-neutral-500">No records loaded. Provide a bearer token and refresh history.</p> : <div className="space-y-2">{items.map((item) => <div key={String(item.workload_id)} className="grid gap-2 rounded-lg border border-neutral-800 bg-neutral-950/70 p-3 text-sm sm:grid-cols-[1fr_auto] sm:items-center"><div className="min-w-0"><p className="truncate font-mono text-xs text-neutral-200">{String(item.workload_id)}</p><p className="mt-1 text-xs text-neutral-500">{String(item.workload_type)}{item.tier ? ` · ${String(item.tier)}` : ''} · {String(item.submitted_at || 'timestamp not reported')}</p></div><StatusPill status={String(item.status || 'UNKNOWN')} showDot={false} /></div>)}</div>}</Card>
    </div>
  );
}
