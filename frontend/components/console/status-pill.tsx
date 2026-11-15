import React from 'react';
import { cn } from '@/lib/utils';

export type OperationalStatus = string;

interface StatusPillProps {
  status: OperationalStatus;
  label?: string;
  className?: string;
  showDot?: boolean;
}

export function StatusPill({ status, label, className, showDot = true }: StatusPillProps) {
  const displayLabel = label || status.replace(/_/g, ' ');
  // Green is reserved for states returned by a live health/readiness check.
  const colorMap: Record<string, string> = {
    READY: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
    HEALTHY: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
    FAIL: 'bg-rose-500/10 text-rose-300 border-rose-500/25',
    FAILED: 'bg-rose-500/10 text-rose-300 border-rose-500/25',
    NOT_READY: 'bg-rose-500/10 text-rose-300 border-rose-500/25',
    REJECTED: 'bg-rose-500/10 text-rose-300 border-rose-500/25',
    PENDING: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
    CHECKING: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
    DEGRADED: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
    SIMULATED: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
    BLOCKED: 'bg-amber-500/10 text-amber-300 border-amber-500/25',
  };
  const currentStyle = colorMap[status] || 'bg-neutral-500/10 text-neutral-300 border-neutral-500/20';

  return (
    <span className={cn('inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-wide', currentStyle, className)}>
      {showDot && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />}
      {displayLabel}
    </span>
  );
}
