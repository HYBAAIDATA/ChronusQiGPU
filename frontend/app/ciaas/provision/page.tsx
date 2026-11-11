import Link from 'next/link';
import { CircleAlert } from 'lucide-react';
import { Card } from '@/components/ui/card';

const options = ['Small', 'Medium', 'Large', 'Custom'];

export default function CustomerProvisionPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-7 py-2 sm:py-8">
      <header className="max-w-3xl space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Customer workspace / Provisioning</p>
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">What do you need?</h1>
        <p className="text-sm leading-6 text-neutral-300">Choose capacity once sizing, projections and customer provisioning are available for your account.</p>
        <button type="button" disabled aria-describedby="provision-unavailable" className="min-h-11 cursor-not-allowed rounded-lg border border-neutral-700 bg-neutral-800 px-5 py-3 text-sm font-semibold text-neutral-400">Provision — unavailable</button>
      </header>

      <div id="provision-unavailable" role="status" className="flex gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.07] p-4 text-sm leading-6 text-amber-100/85">
        <CircleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">Provisioning is not available in this deployment. Contact the platform operator.</p>
          <p className="mt-1">No authenticated customer session, verified quote, or customer-facing provisioning service is connected to this preview. No capacity will be created.</p>
        </div>
      </div>

      <section aria-labelledby="options-heading">
        <h2 id="options-heading" className="text-base font-semibold text-white">Capacity options</h2>
        <p className="mt-2 text-sm leading-6 text-neutral-400">Customer usage and approved default sizes are unavailable. Options cannot be sized or selected until those sources are connected.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {options.map((option) => (
            <Card key={option} className="border-neutral-800 bg-neutral-900/55 p-5">
              <h3 className="text-sm font-semibold text-neutral-100">{option}</h3>
              <p className="text-sm text-neutral-400">Sizing unavailable</p>
              <p className="text-xs leading-5 text-neutral-400">Source: customer usage or approved default sizing. Window: current account state. Last verified: not available.</p>
            </Card>
          ))}
        </div>
      </section>

      <section aria-labelledby="quote-heading" className="grid gap-3 sm:grid-cols-2">
        <h2 id="quote-heading" className="text-base font-semibold text-white sm:col-span-2">Before you commit</h2>
        <Card className="border-neutral-800 bg-neutral-900/55 p-5">
          <h3 className="text-sm font-semibold text-neutral-100">Projected cost — unavailable</h3>
          <p className="text-xs leading-5 text-neutral-400">Source: tenant settlement projection. Window: not available. Last verified: not available.</p>
          <p className="text-xs leading-5 text-neutral-400">The settlement window and charge date are not connected.</p>
        </Card>
        <Card className="border-neutral-800 bg-neutral-900/55 p-5">
          <h3 className="text-sm font-semibold text-neutral-100">Projected avoided capex — unavailable</h3>
          <p className="text-xs leading-5 text-neutral-400">Source: customer benchmark artifact. Window: not available. Last verified: not available.</p>
          <p className="text-xs leading-5 text-neutral-400">No customer artifact is connected to support a projection.</p>
        </Card>
      </section>
      <Link href="/ciaas/account" className="inline-flex min-h-11 items-center text-sm font-semibold text-blue-300 underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">Back to account</Link>
    </div>
  );
}
