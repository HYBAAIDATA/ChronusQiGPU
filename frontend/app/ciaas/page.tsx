import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';

export default function TenantOperationsPage() {
  return <div className="space-y-7">
    <header className="space-y-2 border-b border-neutral-800 pb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Workspace / Tenant operations</p><h1 className="text-3xl font-semibold tracking-tight text-white">Tenant operations</h1><p className="max-w-3xl text-sm leading-6 text-neutral-400">The tenant API exposes application-level records and provisioning workflows. The inspected route implementation does not demonstrate end-to-end cloud resource provisioning, customer identity lifecycle, or a measured activation SLA.</p></header>
    <nav aria-label="Customer self-service preview" className="flex flex-wrap gap-3">
      <Link href="/ciaas/welcome" className="rounded-lg border border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-100 transition hover:border-neutral-500 hover:bg-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">Customer welcome</Link>
      <Link href="/ciaas/account" className="rounded-lg border border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-100 transition hover:border-neutral-500 hover:bg-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">Account overview</Link>
    </nav>
    <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-white">Release posture</h2><p className="mt-1 text-sm text-neutral-400">Operational controls are intentionally withheld from this preview surface.</p></div><StatusPill status="UNVERIFIED" label="Not release-qualified" showDot={false} /></div><ul className="mt-5 list-disc space-y-2 pl-5 text-sm leading-6 text-neutral-400"><li>Tenant onboarding writes through the application tenant store; a successful API response must not be read as proof that cloud resources or external identity systems were provisioned.</li><li>Capacity and settlement fields require an independently reviewed commercial model and persistent, tenant-isolated source of truth.</li><li>Load-test or SLA language must be tied to reproducible test runs, workload definitions, and measured results—not a demonstration screen.</li></ul></Card>
  </div>;
}
