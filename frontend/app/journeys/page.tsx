import type { Metadata } from 'next';
import Link from 'next/link';
import journeyConfig from '@/data/customer-journeys.json';

type Phase = {
  id: string;
  name: string;
  gates: string[];
  decisionQuestion: string;
  evidence: string[];
  exitCriteria: string;
};

type CustomerJourney = {
  id: string;
  audience: string;
  summary: string;
  roles: string[];
  mandatoryGates: string[];
  customerRefusals: string[];
  phases: Phase[];
};

type ProductScope = {
  id: string;
  name: string;
  scope: string;
  evidenceStatus: string;
  requiredEvidence: string;
  notClaimed: string[];
};

type TrustArtifact = {
  name: string;
  currentStatus: string;
  requiredEvidence: string;
};

type JourneyConfig = {
  releaseStatus: string;
  overview: string;
  products: ProductScope[];
  journeys: CustomerJourney[];
  trustArtifacts: TrustArtifact[];
};

const content = journeyConfig as JourneyConfig;

export const metadata: Metadata = {
  title: 'Customer journeys | Chronus',
  description: 'Evidence-gated evaluation paths for government, enterprise, and hyperscaler buyers.',
};

function GateBadge({ gate }: { gate: string }) {
  const label = gate.replaceAll('_', ' ');
  return <span className="rounded-full border border-neutral-700 bg-neutral-950 px-2.5 py-1 text-[11px] capitalize text-neutral-300">{label}</span>;
}

export default function CustomerJourneysPage() {
  return (
    <div className="space-y-10 pb-10">
      <header className="space-y-4 border-b border-neutral-800 pb-7">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Customer pathways</p>
        <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">Three buying journeys. One evidence standard.</h1>
        <p className="max-w-3xl text-sm leading-6 text-neutral-300">{content.overview}</p>
        <div role="note" aria-label="Current product evidence boundary" className="rounded-xl border border-amber-500/30 bg-amber-500/[0.07] p-4 sm:p-5">
          <p className="text-sm font-semibold text-amber-100">{content.releaseStatus.replaceAll('-', ' ')}</p>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-amber-100/80">This page defines evaluation gates. It does not offer or certify the four product concepts below. No customer deployment, authorization, service-level commitment, or measured performance advantage is established here.</p>
        </div>
        <div className="flex flex-wrap gap-3 pt-1">
          <a className="inline-flex items-center rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300" href="#audiences">Explore buyer journeys</a>
          <a className="inline-flex items-center rounded-lg border border-neutral-700 px-4 py-2.5 text-sm font-medium text-neutral-200 transition hover:bg-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-300" href="https://github.com/hybadatadevops1/Chronusv2/blob/main/docs/claim-audit.md" target="_blank" rel="noreferrer">Read the repository claim audit</a>
        </div>
      </header>

      <section aria-labelledby="products-heading" className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Scope before sales</p>
          <h2 id="products-heading" className="mt-1 text-xl font-semibold text-white">Product concepts and evidence required</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">A proposed evaluation is not proof of availability. Use the status and evidence boundary on each card before discussing a customer test.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {content.products.map((product) => (
            <article key={product.id} className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-5">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-semibold text-white">{product.name}</h3>
                <span className="shrink-0 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-200">Evidence gap</span>
              </div>
              <p className="mt-3 text-sm leading-6 text-neutral-300">{product.scope}</p>
              <p className="mt-3 text-sm leading-6 text-neutral-400"><span className="font-medium text-neutral-200">Current evidence:</span> {product.evidenceStatus}</p>
              <p className="mt-3 border-t border-neutral-800 pt-3 text-sm leading-6 text-neutral-400"><span className="font-medium text-neutral-200">Required before a claim:</span> {product.requiredEvidence}</p>
              <div className="mt-3 border-t border-neutral-800 pt-3">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-amber-200">Not currently claimed</h4>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-5 text-neutral-400">
                  {product.notClaimed.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="audiences" aria-labelledby="audiences-heading" className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Choose a buyer path</p>
          <h2 id="audiences-heading" className="mt-1 text-xl font-semibold text-white">Different approval routes, shared evidence gates</h2>
        </div>
        <nav aria-label="Customer type" className="grid gap-3 sm:grid-cols-3">
          {content.journeys.map((journey) => (
            <a key={journey.id} href={`#${journey.id}`} className="group rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 transition hover:border-neutral-600 hover:bg-neutral-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-300">
              <span className="text-xs font-semibold uppercase tracking-wide text-blue-300">{journey.audience}</span>
              <span className="mt-2 block text-sm leading-5 text-neutral-300">{journey.summary}</span>
              <span className="mt-3 block text-xs text-neutral-500">{journey.phases.length} evaluation phases</span>
            </a>
          ))}
        </nav>
      </section>

      <div className="space-y-8">
        {content.journeys.map((journey) => (
          <section key={journey.id} id={journey.id} aria-labelledby={`${journey.id}-heading`} className="scroll-mt-6 space-y-5 rounded-2xl border border-neutral-800 bg-neutral-900/30 p-5 sm:p-7">
            <div className="flex flex-col gap-4 border-b border-neutral-800 pb-5 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-3xl space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-300">Buyer path</p>
                <h2 id={`${journey.id}-heading`} className="text-2xl font-semibold text-white">{journey.audience}</h2>
                <p className="text-sm leading-6 text-neutral-400">{journey.summary}</p>
              </div>
              <div className="max-w-xl">
                <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Decision roles</p>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {journey.roles.map((role) => <li key={role} className="rounded-full border border-neutral-800 bg-neutral-950 px-2.5 py-1 text-xs text-neutral-300">{role}</li>)}
                </ul>
              </div>
            </div>
            <div role="group" aria-label="Required approval gates" className="flex flex-wrap items-center gap-2">
              <span className="mr-1 text-xs font-medium text-neutral-500">Required gates:</span>
              {journey.mandatoryGates.map((gate) => <GateBadge key={gate} gate={gate} />)}
            </div>
            <aside aria-label={`${journey.audience} explicit limitations`} className="rounded-xl border border-amber-500/20 bg-amber-500/[0.04] p-4">
              <h3 className="text-sm font-semibold text-amber-100">Explicit limitations and refusals</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-5 text-neutral-300">
                {journey.customerRefusals.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </aside>
            <ol className="grid gap-3 lg:grid-cols-2">
              {journey.phases.map((phase, index) => (
                <li key={phase.id} className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-4 sm:p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Phase {index + 1}</p>
                      <h3 className="mt-1 text-base font-semibold text-white">{phase.name}</h3>
                    </div>
                    <div className="flex max-w-[60%] flex-wrap justify-end gap-1.5">
                      {phase.gates.map((gate) => <GateBadge key={gate} gate={gate} />)}
                    </div>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-neutral-300"><span className="font-semibold text-neutral-100">Decision question:</span> {phase.decisionQuestion}</p>
                  <div className="mt-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Evidence to present</p>
                    <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-5 text-neutral-400">
                      {phase.evidence.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                  <p className="mt-4 border-t border-neutral-800 pt-3 text-sm leading-6 text-neutral-300"><span className="font-semibold text-neutral-100">Exit gate:</span> {phase.exitCriteria}</p>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>

      <section aria-labelledby="trust-heading" className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Shared trust artifacts</p>
          <h2 id="trust-heading" className="mt-1 text-xl font-semibold text-white">What buyers can verify today—and what remains to build</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">Do not present a planned artifact as a published control, live service, or customer proof.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {content.trustArtifacts.map((artifact) => (
            <article key={artifact.name} className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
              <h3 className="text-sm font-semibold text-white">{artifact.name}</h3>
              <p className="mt-2 text-sm leading-5 text-neutral-400">{artifact.currentStatus}</p>
              <p className="mt-3 border-t border-neutral-800 pt-3 text-xs leading-5 text-neutral-500"><span className="font-semibold text-neutral-300">Evidence needed:</span> {artifact.requiredEvidence}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
        <h2 className="text-base font-semibold text-white">Claim release checklist</h2>
        <ul className="mt-3 grid gap-2 text-sm leading-6 text-neutral-400 md:grid-cols-2">
          <li>Performance: attach the workload, baseline, hardware, software commit, method, and raw artifact.</li>
          <li>Capacity: state the ceiling, source of supply, measured provisioning time, and behavior at the limit.</li>
          <li>Compression: report the tested data class, ratio, verification method, and error bound where applicable.</li>
          <li>Memory: show the baseline failure, successful run, correctness, latency delta, and throughput delta.</li>
          <li>Security and compliance: name the exact scope and evidence; do not infer authorization from code or a questionnaire.</li>
          <li>Every buyer path must preserve its procurement, security, and technical evaluation gates.</li>
        </ul>
        <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 border-t border-neutral-800 pt-4 text-sm">
          <Link className="text-blue-300 underline decoration-blue-300/40 underline-offset-4 hover:text-blue-200" href="/">Back to operations overview</Link>
          <a className="text-blue-300 underline decoration-blue-300/40 underline-offset-4 hover:text-blue-200" href="https://github.com/hybadatadevops1/Chronusv2/blob/main/docs/claim-audit.md" target="_blank" rel="noreferrer">Current repository claim audit</a>
          <a className="text-blue-300 underline decoration-blue-300/40 underline-offset-4 hover:text-blue-200" href="https://github.com/hybadatadevops1/Chronusv2/blob/main/docs/HYPERSCALER_DATA_CONNECTOR_AND_USER_JOURNEYS.md" target="_blank" rel="noreferrer">Journey implementation details</a>
        </div>
      </footer>
    </div>
  );
}
