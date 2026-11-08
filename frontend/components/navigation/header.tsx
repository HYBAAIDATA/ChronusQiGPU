'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { RotateCw } from 'lucide-react';
import { StatusPill } from '@/components/console/status-pill';
import { fetchSystemStatus, type SystemStatus } from '@/lib/chronus-client';

const initialStatus: SystemStatus = {
  status: 'CHECKING',
  checked_at: '',
  message: 'Checking the configured Chronus API.',
};

export function Header() {
  const [status, setStatus] = useState<SystemStatus>(initialStatus);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    setStatus(await fetchSystemStatus());
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const statusLabel: Record<SystemStatus['status'], string> = {
    CHECKING: 'Checking API',
    READY: 'API ready',
    NOT_READY: 'API not ready',
    UNAVAILABLE: 'API unavailable',
    UNCONFIGURED: 'API not configured',
  };

  return (
    <header className="sticky top-0 z-40 flex min-h-16 items-center justify-between gap-4 border-b border-neutral-800 bg-neutral-950/95 px-4 backdrop-blur md:px-8">
      <div className="min-w-0">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-neutral-500">Chronus · product preview</p>
        <p className="truncate text-sm font-medium text-neutral-200">Compute operations console</p>
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <StatusPill status={status.status} label={statusLabel[status.status]} />
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={isRefreshing}
          aria-label="Refresh Chronus API readiness"
          title="Refresh readiness"
          className="rounded-lg border border-neutral-800 p-2 text-neutral-400 transition hover:border-neutral-700 hover:bg-neutral-900 hover:text-white disabled:opacity-50"
        >
          <RotateCw aria-hidden="true" className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </header>
  );
}
