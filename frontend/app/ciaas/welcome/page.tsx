import Link from 'next/link';
import { ArrowRight, CircleAlert } from 'lucide-react';
import { Card } from '@/components/ui/card';

type MetricCardProps = {
  title: string;
  source: string;
  window: string;
  reason: string;
};

function MetricCard({ title, source, window, reason }: MetricCardProps) {
  return (
    <Card className="flex h-full flex-col border-neutral-800 bg-neutral-900/55 p-5 sm:p-6">
      <h2 className="text-sm font-medium text-neutral-300">{title}</h2>
      <p className="mt-5 text-2xl font-semibold tracking-tight text-neutral-100">Not available</p>
      <p className="mt-3 text-xs leading-5 text-neutral-400">
        Source: {source}. Window: {window}. Last verified: not available.
      </p>
      <p className="mt-3 text-xs leading-5 text-amber-100/75">{reason}</p>
    </Card>
  );
}

export default function CustomerWelcomePage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 py-2 sm:py-8">
      <header className="max-w-3xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Customer workspace / Sign in</p>
        <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">Welcome back.</h1>
        <p className="max-w-2xl text-sm leading-6 text-neutral-300 sm:text-base">
          Your account summary belongs here. Until authenticated customer identity and tenant-scoped data sources are connected, values are withheld rather than estimated or substituted with demo data.
        </p>
      </header>

      <div role="status" className="flex gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] p-4 text-sm leading-6 text-amber-100/85">
        <CircleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
        <p><span className="font-semibold">Sign-in is not available in this deployment. Contact the platform operator.</span> No customer session is active; this page does not authenticate or expose account records.</p>
      </div>

      <section aria-label="Account value summary" className="grid gap-4 md:grid-cols-3">
        <MetricCard
          title="Avoided capex this period"
          source="tenant settlement ledger"
          window="current billing period"
          reason="Tenant-scoped settlement records are not connected, so no amount is shown."
        />
        <MetricCard
          title="Speedup delivered"
          source="verified benchmark artifact"
          window="current billing period"
          reason="No customer benchmark artifact is available to verify a measured result."
        />
        <MetricCard
          title="Next invoice estimate"
          source="tenant settlement engine"
          window="current period to date"
          reason="No connected settlement record or verified charge date is available."
        />
      </section>

      <div className="flex flex-col gap-3 border-t border-neutral-800 pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-xs leading-5 text-neutral-500">Each value remains unavailable until its named source can return tenant-scoped data and a verification timestamp.</p>
        <Link
          href="/ciaas/account"
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-blue-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
        >
          View account <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
