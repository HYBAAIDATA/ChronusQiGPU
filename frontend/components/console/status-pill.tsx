import React from 'react';
import { cn } from '@/lib/utils';
import { ExecutionBadge } from '@/lib/api-client';

export type OperationalStatus = 
  | 'PASS' 
  | 'FAIL' 
  | 'BLOCKED' 
  | 'OPERATIONAL' 
  | 'ONLINE'
  | 'RUNNING' 
  | 'DEGRADED'
  | 'UNAVAILABLE'
  | 'SIMULATED'
  | ExecutionBadge;

interface StatusPillProps {
  status: OperationalStatus | string;
  label?: string;
  className?: string;
  showDot?: boolean;
}

export function StatusPill({ status, label, className, showDot = true }: StatusPillProps) {
  const displayLabel = label || status.replace(/_/g, ' ');

  // Strict Operational Colour System:
  // 🟢 Green (#10B981): Verified execution with cryptographic proof receipt
  // 🟡 Amber (#F59E0B): Pending, degraded, or simulated state
  // 🔴 Red (#EF4444): Execution failure or security rejection
  // ⚪ Muted Grey (#71717A): Feature unverified or hardware unavailable
  const colorMap: Record<string, string> = {
    // Verified Green
    PASS: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    OPERATIONAL: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    ONLINE: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    RUNNING: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    VERIFIED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    PHYSICAL_HARDWARE_EXECUTION: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',

    // Mathematical Execution Purple
    MATHEMATICAL_EXECUTION: 'bg-purple-500/10 text-purple-400 border-purple-500/20',

    // Software Execution Blue
    SOFTWARE_EXECUTION: 'bg-blue-500/10 text-blue-400 border-blue-500/20',

    // Amber
    PENDING: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    DEGRADED: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    SIMULATED: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    BLOCKED: 'bg-amber-500/10 text-amber-400 border-amber-500/20',

    // Red
    FAIL: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    FAILED: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    REJECTED: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    REVOKED: 'bg-rose-500/10 text-rose-400 border-rose-500/20',

    // Grey
    UNAVAILABLE: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    UNVERIFIED: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  };

  const currentStyle = colorMap[status] || 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20';

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium border tracking-wide transition-colors',
        currentStyle,
        className
      )}
    >
      {showDot && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />}
      {displayLabel}
    </span>
  );
}
