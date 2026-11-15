import Link from 'next/link';
import { ArrowRight, CircleAlert } from 'lucide-react';
import { Card } from '@/components/ui/card';

type AccountFactProps = {
  label: string;
  value: string;
  source: string;
  window: string;
  detail: string;
};

function AccountFact({ label, value, source, window, detail }: AccountFactProps) {
  return (
    <div className="border-b border-neutral-800 py-4 last:border-b-0">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <dt className="text-sm font-medium text-neutral-200">{label}</dt>
        <dd className="text-sm font-semibold text-neutral-100">{value}</dd>
      </div>
      <p className="mt-2 text-xs leading-5 text-neutral-400">Source: {source}. Window: {window}. Last verified: not available.</p>
      <p className="mt-1 text-xs leading-5 text-neutral-500">{detail}</p>
    </div>
  );
}

function UnavailableAction({ title, explanation }: { title: string; explanation: string }) {
  return (
    <li className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-4">
      <p className="text-sm font-medium text-neutral-200">{title} — unavailable</p>
      <p className="mt-1 text-xs leading-5 text-neutral-500">{explanation}</p>
    </li>
  );
}

export default function CustomerAccountPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-8 py-2 sm:py-8">
      <header className="max-w-3xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Customer workspace / Account</p>
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">What is your account doing right now?</h1>
        <p className="max-w-2xl text-sm leading-6 text-neutral-400">This account view will show verified tier, capacity, value, settlement, and health data. The current repository has no verified customer account feed connected to this screen.</p>
      </header>

      <div role="status" className="flex gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] p-4 text-sm leading-6 text-amber-100/85">
        <CircleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
        <p><span className="font-semibold">Account data unavailable.</span> No authenticated tenant session or verified tenant-scoped source is connected. The values below are intentionally withheld.</p>
      </div>

      <div role="status" className="space-y-1 rounded-xl border border-neutral-700 p-4 text-sm text-neutral-200">
        <p>Settlement and benchmark data are not available in this deployment. Contact the platform operator.</p>
        <p>Live account feeds are not available in this deployment. Contact the platform operator.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <Card className="border-neutral-800 bg-neutral-900/55 p-5 sm:p-6">
          <h2 className="text-base font-semibold text-white">Account summary</h2>
          <dl className="mt-2">
            <AccountFact
              label="Tier"
              value="Not available"
              source="customer provisioning record"
              window="current account state"
              detail="No authenticated account record is available to identify tier inclusions."
            />
            <AccountFact
              label="Provisioned capacity and utilization"
              value="Not available"
              source="tenant provisioning and usage records"
              window="current allocation and current period"
              detail="Capacity and utilization are not inferred from local simulations or service readiness."
            />
            <AccountFact
              label="Avoided capex to date"
              value="Not computed"
              source="tenant settlement ledger and benchmark artifacts"
              window="account lifetime to date"
              detail="Counterfactual spend − actual spend − incremental spend = avoided capex; the required tenant inputs are not connected."
            />
            <AccountFact
              label="Next invoice"
              value="Not available"
              source="tenant settlement engine"
              window="current billing period to date"
              detail="The settlement window, line-item arithmetic, total, and charge date cannot be verified here."
            />
          </dl>
        </Card>

        <div className="space-y-4">
          <Card className="border-neutral-800 bg-neutral-900/55 p-5 sm:p-6">
            <h2 className="text-base font-semibold text-white">Capacity health</h2>
            <p className="mt-3 text-lg font-semibold text-amber-200">Unverified</p>
            <p className="mt-2 text-xs leading-5 text-neutral-400">Source: tenant-scoped capacity health feed. Window: current account state. Last verified: not available.</p>
            <p className="mt-2 text-xs leading-5 text-neutral-500">The platform readiness probe is not evidence of this account’s capacity health.</p>
          </Card>
          <Card className="border-neutral-800 bg-neutral-900/55 p-5 sm:p-6">
            <h2 className="text-base font-semibold text-white">Self-service actions</h2>
            <Link href="/ciaas/provision" className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-blue-300 underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">View provisioning availability</Link>
            <ul className="mt-3 space-y-2">
              <UnavailableAction title="Settlement history" explanation="No tenant settlement history is connected to this preview." />
              <UnavailableAction title="Export data" explanation="A tenant-scoped export source and delivery flow are not configured." />
              <UnavailableAction title="Contact support" explanation="A named support contact is not configured; no support queue or person is fabricated." />
            </ul>
          </Card>
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-neutral-800 pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-5 text-neutral-500">Current state: tenant data integration is unavailable. No upgrade, downgrade, billing, or cancellation action is enabled from this preview.</p>
        <Link
          href="/"
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-neutral-700 px-5 py-3 text-sm font-semibold text-neutral-100 transition hover:border-neutral-500 hover:bg-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300"
        >
          Investigate service status <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
