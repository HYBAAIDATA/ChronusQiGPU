'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Activity, ArrowRight, CircleHelp, Clock3, ExternalLink, Server, ShieldAlert } from 'lucide-react';
import { StatusPill } from '@/components/console/status-pill';
import { Card } from '@/components/ui/card';
import { fetchSystemStatus, type SystemStatus } from '@/lib/chronus-client';

const initialStatus: SystemStatus = { status: 'CHECKING', checked_at: '' };

function displayTime(value: string) {
  if (!value) return 'Not checked yet';
  return new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value));
}

export default function OverviewPage() {
  const [status, setStatus] = useState<SystemStatus>(initialStatus);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setStatus(await fetchSystemStatus());
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const ready = status.status === 'READY';
  const mode = status.execution_mode?.replace(/-/g, ' ') || 'Not reported';

  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-4 border-b border-neutral-800 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Operations / Overview</p>
          <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Platform overview</h1>
          <p className="max-w-2xl text-sm leading-6 text-neutral-400">
            A source-first view of Chronus API readiness. This page reports only what the service probe returns; it is not a product or production qualification.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill status={status.status} />
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={refreshing}
            className="rounded-lg border border-neutral-700 px-3 py-2 text-xs font-medium text-neutral-200 transition hover:bg-neutral-800 disabled:opacity-50"
          >
            {refreshing ? 'Checking…' : 'Refresh check'}
          </button>
        </div>
      </div>

      <Card className="overflow-hidden border-neutral-800 bg-neutral-900/70">
        <div className="grid gap-0 lg:grid-cols-[1.5fr_1fr]">
          <div className="space-y-5 p-6 sm:p-8">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-neutral-500">
              <Activity aria-hidden="true" className="h-4 w-4 text-blue-300" />
              Live service observation
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-white">{ready ? 'Readiness probe passed' : 'Readiness not confirmed'}</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-neutral-400">
                {status.message || (ready
                  ? 'The configured service returned a ready response at the time shown.'
                  : 'No successful ready response has been observed. Check backend configuration and service availability.')}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-neutral-400">
              <span className="inline-flex items-center gap-2"><Clock3 aria-hidden="true" className="h-3.5 w-3.5" /> Checked {displayTime(status.checked_at)}</span>
              {status.version && <span>Service version {status.version}</span>}
            </div>
          </div>
          <div className="border-t border-neutral-800 bg-neutral-950/50 p-6 sm:p-8 lg:border-l lg:border-t-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Observed response</p>
            <dl className="mt-4 space-y-4">
              <div>
                <dt className="text-xs text-neutral-500">Probe</dt>
                <dd className="mt-1 font-mono text-sm text-neutral-200">GET /health/ready</dd>
              </div>
              <div>
                <dt className="text-xs text-neutral-500">Service</dt>
                <dd className="mt-1 text-sm text-neutral-200">{status.service || 'Not reported'}</dd>
              </div>
              <div>
                <dt className="text-xs text-neutral-500">Execution mode</dt>
                <dd className="mt-1 capitalize text-sm text-neutral-200">{mode}</dd>
              </div>
            </dl>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-4 border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-amber-500/10 p-2 text-amber-300"><ShieldAlert aria-hidden="true" className="h-4 w-4" /></span>
            <h2 className="text-base font-semibold text-white">Qualification boundary</h2>
          </div>
          <p className="text-sm leading-6 text-neutral-400">
            Readiness confirms only that this API accepted its readiness check. It does not establish workload correctness, durable storage, cryptographic assurance, accelerator availability, compliance, an SLA, or production capacity.
          </p>
          <p className="text-xs text-neutral-500">Treat other console modules as exploratory unless each output is independently backed by test results or an observed API response.</p>
        </Card>

        <Card className="space-y-4 border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-blue-500/10 p-2 text-blue-300"><CircleHelp aria-hidden="true" className="h-4 w-4" /></span>
            <h2 className="text-base font-semibold text-white">Connection setup</h2>
          </div>
          <p className="text-sm leading-6 text-neutral-400">
            The web service requires <code className="rounded bg-neutral-950 px-1.5 py-0.5 font-mono text-xs text-neutral-200">CHRONUS_BACKEND_URL</code> to point to the API. If it is unset or unreachable, the console reports that state instead of substituting simulated success.
          </p>
          <div className="flex items-center gap-2 text-xs text-neutral-500"><Server aria-hidden="true" className="h-3.5 w-3.5" /> No backend address or credentials are displayed in this browser.</div>
        </Card>
      </div>

      <section aria-labelledby="modules-heading" className="space-y-3">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Explore</p>
            <h2 id="modules-heading" className="mt-1 text-lg font-semibold text-white">Console modules</h2>
          </div>
          <span className="text-xs text-neutral-500">Preview surfaces · verify before relying on outputs</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['Workloads', 'Execution requests and results', '/workloads'],
            ['Execution fabric', 'Backend and hardware exploration', '/fabric'],
            ['Storage', 'Storage and reconstruction exploration', '/storage'],
            ['Governance', 'Receipt and policy exploration', '/governance'],
          ].map(([title, description, href]) => (
            <Link key={href} href={href} className="group rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400">
              <Card className="h-full border-neutral-800 bg-neutral-900/40 p-4 transition-colors group-hover:border-neutral-600 group-hover:bg-neutral-900/80">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-neutral-100">{title}</h3>
                  <ArrowRight aria-hidden="true" className="h-4 w-4 text-neutral-500 transition group-hover:translate-x-0.5 group-hover:text-blue-300" />
                </div>
                <p className="mt-2 text-sm leading-5 text-neutral-400">{description}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-amber-300/80">Preview <ExternalLink aria-hidden="true" className="h-3 w-3" /></span>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
