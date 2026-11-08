'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  Binary,
  Cpu,
  Database,
  LayoutDashboard,
  Layers,
  Link2,
  ShieldCheck,
  Users,
  ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { label: 'Overview', href: '/', icon: LayoutDashboard, preview: false },
  { label: 'Workloads', href: '/workloads', icon: Cpu, preview: true },
  { label: 'Execution fabric', href: '/fabric', icon: Layers, preview: true },
  { label: 'Mining Intelligence', href: '/mining', icon: Activity, preview: true },
  { label: 'Storage', href: '/storage', icon: Database, preview: true },
  { label: 'Math explorer', href: '/math', icon: Binary, preview: true },
  { label: 'Governance', href: '/governance', icon: ShieldCheck, preview: true },
  { label: 'Tenant operations', href: '/ciaas', icon: Users, preview: true },
  { label: 'Connectors', href: '/connectors', icon: Link2, preview: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-screen w-[4.25rem] shrink-0 flex-col border-r border-neutral-800 bg-neutral-950 md:w-64">
      <Link href="/" className="flex h-16 items-center gap-3 border-b border-neutral-800 px-4" aria-label="Chronus overview">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-base font-semibold text-neutral-950">χ</span>
        <span className="hidden min-w-0 md:block">
          <span className="block text-sm font-semibold tracking-wide text-white">CHRONUS</span>
          <span className="block text-[10px] uppercase tracking-[0.18em] text-neutral-500">Operations</span>
        </span>
      </Link>

      <nav aria-label="Primary navigation" className="flex-1 space-y-1 px-2 py-4">
        <p className="hidden px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-600 md:block">Workspace</p>
        {NAV_ITEMS.map(({ label, href, icon: Icon, preview }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? 'page' : undefined}
              title={`${label}${preview ? ' · preview module' : ''}`}
              className={cn(
                'flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors',
                active
                  ? 'bg-neutral-800 text-white'
                  : 'text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100'
              )}
            >
              <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
              <span className="hidden min-w-0 flex-1 truncate md:block">{label}</span>
              {preview && <span className="sr-only">Preview module; content may be illustrative.</span>}
              {preview && <span aria-hidden="true" className="hidden h-1.5 w-1.5 rounded-full bg-amber-400/70 md:block" />}
            </Link>
          );
        })}

        <div className="mt-4 pt-3 border-t border-neutral-800/60">
          <p className="hidden px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-600 md:block">Interactive Studios</p>
          <a
            href="/sovereign-dashboard.html"
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm text-neutral-400 hover:bg-neutral-900 hover:text-cyan-300 transition-colors"
          >
            <ShieldCheck className="h-4 w-4 shrink-0 text-cyan-400" />
            <span className="hidden min-w-0 flex-1 truncate md:block">Sovereign Simulator</span>
            <ExternalLink className="hidden h-3 w-3 opacity-60 md:block" />
          </a>
          <a
            href="/chronus-observatory.html"
            target="_blank"
            rel="noopener noreferrer"
            className="flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm text-neutral-400 hover:bg-neutral-900 hover:text-amber-300 transition-colors"
          >
            <Activity className="h-4 w-4 shrink-0 text-amber-400" />
            <span className="hidden min-w-0 flex-1 truncate md:block">Hashrate Observatory</span>
            <ExternalLink className="hidden h-3 w-3 opacity-60 md:block" />
          </a>
        </div>
      </nav>

      <div className="border-t border-neutral-800 p-3">
        <div className="flex items-start gap-2 rounded-lg bg-neutral-900/70 p-2.5 text-neutral-400">
          <Activity aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
          <p className="hidden text-[11px] leading-relaxed md:block">
            Preview modules are not release-qualified. Confirm outputs against source evidence before operational use.
          </p>
          <span className="sr-only md:hidden">Preview modules are not release-qualified.</span>
        </div>
      </div>
    </aside>
  );
}
