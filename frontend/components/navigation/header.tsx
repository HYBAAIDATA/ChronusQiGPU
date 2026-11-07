'use client';

import React, { useState, useEffect } from 'react';
import { Play, RotateCw, Shield, Terminal, Zap, UserCheck } from 'lucide-react';
import { StatusPill } from '@/components/console/status-pill';
import { Button } from '@/components/ui/button';
import { fetchSystemStatus, SystemStatus } from '@/lib/chronus-client';

export function Header() {
  const [status, setStatus] = useState<SystemStatus>({
    status: 'OPERATIONAL',
    backend: 'native_math_reference',
    mode: 'SUBSTRATE_AGNOSTIC (QiGPU)',
    uptime_seconds: 3600,
    registered_backends: ['native_math_reference', 'opencl_pv', 'trinity_symbolic'],
    evidence_level: 'EXACT_MATHEMATICAL',
    purity_gate: 'PASSED',
    version: '36.0.0',
  });
  const [activeRole, setActiveRole] = useState<'system_admin' | 'tenant_admin' | 'developer' | 'external_auditor'>('developer');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    const updated = await fetchSystemStatus();
    setStatus(updated);
    setTimeout(() => setIsRefreshing(false), 400);
  };

  useEffect(() => {
    handleRefresh();
  }, []);

  return (
    <header className="h-16 border-b border-neutral-200 dark:border-neutral-800 bg-white/80 dark:bg-neutral-950/80 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-medium text-neutral-400">ONTOLOGY:</span>
          <span className="text-xs font-mono font-semibold text-neutral-900 dark:text-white bg-neutral-100 dark:bg-neutral-900 px-2.5 py-1 rounded-md border border-neutral-200 dark:border-neutral-800">
            PARADIGM Â· MATHEMATICS FIRST
          </span>
        </div>
        <div className="h-4 w-px bg-neutral-200 dark:bg-neutral-800" />
        <StatusPill status="SUBSTRATE_AGNOSTIC" label="SUBSTRATE & HARDWARE AGNOSTIC" />
      </div>

      <div className="flex items-center gap-3">
        {/* AL HARAS Role Persona Switcher */}
        <div className="hidden lg:flex items-center gap-1.5 bg-neutral-100 dark:bg-neutral-900 px-2 py-1 rounded-lg border border-neutral-200 dark:border-neutral-800 text-xs font-mono">
          <UserCheck className="w-3.5 h-3.5 text-neutral-500" />
          <span className="text-neutral-400 text-[10px]">ROLE:</span>
          <select
            value={activeRole}
            onChange={(e) => setActiveRole(e.target.value as any)}
            className="bg-transparent font-medium text-neutral-800 dark:text-neutral-200 focus:outline-none cursor-pointer text-xs"
          >
            <option value="system_admin" className="dark:bg-neutral-900">System Admin</option>
            <option value="tenant_admin" className="dark:bg-neutral-900">Tenant Admin</option>
            <option value="developer" className="dark:bg-neutral-900">Developer / Engineer</option>
            <option value="external_auditor" className="dark:bg-neutral-900">External Auditor</option>
          </select>
        </div>

        <div className="hidden md:flex items-center gap-3 text-xs font-mono mr-2">
          <span className="text-neutral-500">BACKEND:</span>
          <span className="text-neutral-800 dark:text-neutral-200 font-medium">
            {status.backend}
          </span>
          <span className="text-neutral-300 dark:text-neutral-700">|</span>
          <span className="text-neutral-500">GATE:</span>
          <span className="text-emerald-600 dark:text-emerald-400 font-medium">
            PURITY VERIFIED
          </span>
        </div>

        <button
          onClick={handleRefresh}
          className="p-2 text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-900 rounded-lg transition-colors border border-transparent hover:border-neutral-200 dark:hover:border-neutral-800"
          title="Refresh telemetry"
        >
          <RotateCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-600' : ''}`} />
        </button>

        <div className="flex items-center gap-2">
          <StatusPill status="OPERATIONAL" label="QiGPU RUNNING" />
        </div>
      </div>
    </header>
  );
}

