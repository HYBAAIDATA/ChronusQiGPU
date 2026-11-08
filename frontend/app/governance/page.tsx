'use client';

import React, { FormEvent, useState } from 'react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import { ChronusAPIClient, type VerifyReceiptResponse } from '@/lib/api-client';

export default function GovernancePage() {
  const [receiptId, setReceiptId] = useState('');
  const [result, setResult] = useState<VerifyReceiptResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setResult(null); setError(''); setBusy(true);
    try { setResult(await ChronusAPIClient.verifyReceipt(receiptId.trim())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Receipt verification failed.'); }
    finally { setBusy(false); }
  }
  const boolLabel = (value: unknown) => value === true ? 'Yes' : value === false ? 'No' : 'Not reported';

  return <div className="space-y-7">
    <header className="space-y-2 border-b border-neutral-800 pb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Trust / Evidence</p><h1 className="text-3xl font-semibold tracking-tight text-white">Receipt verification</h1><p className="max-w-3xl text-sm leading-6 text-neutral-400">Verify one receipt against the configured service. A valid signature is a narrow cryptographic check; it does not establish compliance, security certification, or release qualification.</p></header>
    <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><form onSubmit={verify} className="flex flex-col gap-3 sm:flex-row sm:items-end"><label className="flex-1 space-y-1.5 text-sm text-neutral-300"><span>Receipt identifier</span><input value={receiptId} onChange={(e) => setReceiptId(e.target.value)} required className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 font-mono text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20" placeholder="Paste a receipt ID" /></label><button type="submit" disabled={busy || !receiptId.trim()} className="rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-400 disabled:opacity-50">{busy ? 'Verifying…' : 'Verify receipt'}</button></form>{error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">{error}</p>}</Card>
    {result && <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs uppercase tracking-[0.14em] text-neutral-500">Observed receipt result</p><h2 className="mt-1 font-semibold text-white">Signature verification response</h2></div><StatusPill status={String(result.qualification_status || 'NOT_REPORTED')} label={String(result.qualification_status || 'Not reported')} showDot={false} /></div><dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2"><div><dt className="text-xs text-neutral-500">Receipt ID</dt><dd className="mt-1 break-all font-mono text-xs text-neutral-200">{result.receipt_id || receiptId}</dd></div><div><dt className="text-xs text-neutral-500">Ed25519 signature valid</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.ed25519_verified)}</dd></div><div><dt className="text-xs text-neutral-500">ML-DSA verification</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.ml_dsa_verified)}</dd></div><div><dt className="text-xs text-neutral-500">STARK quotient verification</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.stark_quotient_verified)}</dd></div><div><dt className="text-xs text-neutral-500">Release gates evaluated</dt><dd className="mt-1 text-sm text-neutral-200">{typeof result.total_release_gates_evaluated === 'number' ? result.total_release_gates_evaluated : 'Not reported'}</dd></div><div><dt className="text-xs text-neutral-500">Summary</dt><dd className="mt-1 text-sm text-neutral-200">{result.invariant_summary || 'Not reported'}</dd></div></dl><p className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2.5 text-xs leading-5 text-amber-100/80">This response reports the verifier's result only. It is not evidence of NCSC, FedRAMP, DoD, FIPS module, or any other certification unless independently documented and validated.</p></Card>}
  </div>;
}
