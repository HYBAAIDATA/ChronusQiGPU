import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';

export default function FabricPage() {
  return <div className="space-y-7">
    <header className="space-y-2 border-b border-neutral-800 pb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Compute / Execution fabric</p><h1 className="text-3xl font-semibold tracking-tight text-white">Execution fabric</h1><p className="max-w-3xl text-sm leading-6 text-neutral-400">A repository-level view of software and RTL work—not a live hardware inventory or performance console.</p></header>
    <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold text-white">What can be established from this UI</h2><StatusPill status="UNVERIFIED" label="Hardware not observed" showDot={false} /></div><div className="mt-5 grid gap-4 md:grid-cols-2"><div className="rounded-lg border border-neutral-800 bg-neutral-950/70 p-4"><h3 className="text-sm font-medium text-neutral-200">Software reference</h3><p className="mt-2 text-sm leading-6 text-neutral-400">The API may report registered execution backends. Registration alone does not prove hardware execution, throughput, or parity outside tested cases.</p></div><div className="rounded-lg border border-neutral-800 bg-neutral-950/70 p-4"><h3 className="text-sm font-medium text-neutral-200">RTL evidence</h3><p className="mt-2 text-sm leading-6 text-neutral-400">Repository CI contains testbench and synthesis jobs. Review the current run artifacts for pass/fail evidence; synthesis is not physical silicon validation or deployed accelerator availability.</p></div></div></Card>
  </div>;
}
