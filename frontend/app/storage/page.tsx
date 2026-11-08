'use client';
import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import { ChronusAPIClient, type ApiRecord } from '@/lib/api-client';

export default function StoragePage() {
  const [data, setData] = useState<ApiRecord | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  async function refresh() {
    setLoading(true); setError('');
    try { setData(await ChronusAPIClient.getStorage()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Storage counters could not be loaded.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  return <div className="space-y-7">
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-neutral-800 pb-6"><div className="space-y-2"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Data / Storage</p><h1 className="text-3xl font-semibold tracking-tight text-white">Storage counters</h1><p className="max-w-3xl text-sm leading-6 text-neutral-400">Observed counters from the API instance. They do not establish persistence, durability, zero-copy transfer, or cluster-wide capacity.</p></div><button type="button" onClick={() => void refresh()} disabled={loading} className="rounded-lg border border-neutral-700 px-3 py-2 text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-50">{loading ? 'Loading…' : 'Refresh'}</button></header>
    {error && <p role="alert" className="rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">{error}</p>}
    {data && <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold text-white">Observed API response</h2><StatusPill status={String(data.status || 'UNKNOWN')} label="Process-local counters" showDot={false} /></div><p className="mt-2 text-xs text-neutral-500">Measurement scope: {String(data.measurement_scope || 'not reported')}</p><pre className="mt-4 max-h-[32rem] overflow-auto rounded-lg border border-neutral-800 bg-neutral-950 p-4 text-xs leading-5 text-neutral-300">{JSON.stringify(data, null, 2)}</pre></Card>}
  </div>;
}
