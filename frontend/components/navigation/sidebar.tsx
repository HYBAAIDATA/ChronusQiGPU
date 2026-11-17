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
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { label: 'Run & inspect workloads', href: '/workloads', icon: Cpu, preview: false },
  { label: 'Service overview', href: '/', icon: LayoutDashboard, preview: false },
  { label: 'Execution fabric', href: '/fabric', icon: Layers, preview: true },
  { label: 'Storage', href: '/storage', icon: Database, preview: true },
  { label: 'Math explorer', href: '/math', icon: Binary, preview: true },
  { label: 'Governance', href: '/governance', icon: ShieldCheck, preview: true },
  { label: 'Tenant operations', href: '/ciaas', icon: Users, preview: true },
  { label: 'Connectors', href: '/connectors', icon: Link2, preview: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-neutral-800 bg-neutral-950 md:sticky md:top-0 md:h-screen md:w-64 md:border-b-0 md:border-r">
      <Link href="/" className="flex h-16 items-center gap-3 border-b border-neutral-800 px-4" aria-label="Chronus overview">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-base font-semibold text-neutral-950">χ</span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold tracking-wide text-white">CHRONUS</span>
          <span className="block text-[10px] uppercase tracking-[0.18em] text-neutral-400">HYBA Data</span>
        </span>
      </Link>

      <nav aria-label="Primary navigation" className="flex gap-1 overflow-x-auto px-2 py-3 md:block md:flex-1 md:space-y-1 md:overflow-y-auto">
        <p className="hidden px-3 pb-2 text-xs font-semibold uppercase tracking-widest text-neutral-400 md:block">Workspace</p>
        {NAV_ITEMS.map(({ label, href, icon: Icon, preview }) => {
          const active = href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? 'page' : undefined}
              aria-label={`${label}${preview ? ' — exploratory preview' : ''}`}
              title={`${label}${preview ? ' · preview module' : ''}`}
              className={cn(
                'flex min-h-11 shrink-0 items-center gap-3 whitespace-nowrap rounded-lg px-3 text-sm transition-colors',
                active
                  ? 'bg-neutral-800 text-white'
                  : 'text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100'
              )}
            >
              <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{label}</span>
              {preview && <span className="sr-only">Preview module; content may be illustrative.</span>}
              {preview && <span aria-hidden="true" className="hidden h-1.5 w-1.5 rounded-full bg-amber-400/70 md:block" />}
            </Link>
          );
        })}

      </nav>

      <div className="hidden border-t border-neutral-800 p-3 md:block">
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
