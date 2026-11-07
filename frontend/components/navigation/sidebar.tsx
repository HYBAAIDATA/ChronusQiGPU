'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Cpu,
  Layers,
  HardDrive,
  Binary,
  ShieldCheck,
  Terminal,
  Activity,
  Users
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { StatusPill } from '@/components/console/status-pill';

const NAV_ITEMS = [
  {
    num: '01',
    label: 'Overview',
    desc: 'Executive & Live Telemetry',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    num: '02',
    label: 'Workloads',
    desc: 'Dispatcher & Queue',
    href: '/workloads',
    icon: Cpu,
  },
  {
    num: '03',
    label: 'Execution Fabric',
    desc: 'QiGPU & Substrate Tiers',
    href: '/fabric',
    icon: Layers,
  },
  {
    num: '04',
    label: 'Memory & Storage',
    desc: 'Phyllotaxis & Theseus',
    href: '/storage',
    icon: HardDrive,
  },
  {
    num: '05',
    label: 'Mathematical Engine',
    desc: 'Exact Q(âˆš5) & Zeckendorf',
    href: '/math',
    icon: Binary,
  },
  {
    num: '06',
    label: 'Governance & Evidence',
    desc: 'G1â€“G8 Gates & Receipts',
    href: '/governance',
    icon: ShieldCheck,
  },
  {
    num: '07',
    label: 'CIaaS & RBAC',
    desc: 'AL HARAS Matrix & FinOps',
    href: '/ciaas',
    icon: Users,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-72 shrink-0 border-r border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70 backdrop-blur-md flex flex-col justify-between h-screen sticky top-0">
      <div>
        {/* Brand Header */}
        <div className="p-6 border-b border-neutral-200/80 dark:border-neutral-800/80">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-neutral-900 dark:bg-white text-white dark:text-neutral-950 flex items-center justify-center font-bold text-base shadow-sm">
                Ï‡
              </div>
              <div>
                <h1 className="font-semibold text-neutral-900 dark:text-white tracking-tight leading-none text-base">
                  CHRONUS
                </h1>
                <p className="text-[11px] font-mono text-neutral-500 uppercase tracking-widest mt-0.5">
                  QiGPU Â· v36.0.0
                </p>
              </div>
            </div>
            <StatusPill status="RUNNING" label="ACTIVE" />
          </div>
        </div>

        {/* Navigation list */}
        <div className="p-3">
          <p className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-neutral-400 font-medium">
            Primary Navigation
          </p>
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all group',
                    isActive
                      ? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 font-medium shadow-sm'
                      : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-900/80 hover:text-neutral-900 dark:hover:text-white'
                  )}
                >
                  <span
                    className={cn(
                      'text-[10px] font-mono font-medium',
                      isActive ? 'text-neutral-300 dark:text-neutral-600' : 'text-neutral-400'
                    )}
                  >
                    {item.num}
                  </span>
                  <Icon className="w-4 h-4 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{item.label}</div>
                    <div
                      className={cn(
                        'text-[11px] truncate',
                        isActive
                          ? 'text-neutral-300 dark:text-neutral-500'
                          : 'text-neutral-400 dark:text-neutral-500'
                      )}
                    >
                      {item.desc}
                    </div>
                  </div>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Substrate posture & footer */}
      <div className="p-4 border-t border-neutral-200/80 dark:border-neutral-800/80 bg-neutral-50/50 dark:bg-neutral-900/30">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-500 font-mono text-[11px]">Substrate</span>
            <span className="font-mono text-[11px] text-neutral-900 dark:text-white font-medium">
              Hardware Agnostic
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-500 font-mono text-[11px]">Purity Gate</span>
            <span className="font-mono text-[11px] text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1">
              <Activity className="w-3 h-3" /> PASSED
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-neutral-500 font-mono text-[11px]">Execution</span>
            <span className="font-mono text-[11px] text-purple-600 dark:text-purple-400 font-medium">
              Exact Q(âˆš5)
            </span>
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-neutral-200 dark:border-neutral-800/60 flex items-center justify-between text-[11px] text-neutral-400 font-mono">
          <span>DIFC / London</span>
          <span>Sovereign Tier</span>
        </div>
      </div>
    </aside>
  );
}

