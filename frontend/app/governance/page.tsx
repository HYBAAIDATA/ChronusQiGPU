'use client';

import React, { FormEvent, useState } from 'react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import { ChronusAPIClient, type VerifyReceiptResponse, type ApiRecord } from '@/lib/api-client';

export default function GovernancePage() {
  const [receiptId, setReceiptId] = useState('');
  const [result, setResult] = useState<VerifyReceiptResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // Future 5 Applications State
  const [appBusy, setAppBusy] = useState<string | null>(null);
  const [appOutput, setAppOutput] = useState<{ id: string; data: ApiRecord } | null>(null);
  const [appError, setAppError] = useState<string | null>(null);

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setResult(null); setError(''); setBusy(true);
    try { setResult(await ChronusAPIClient.verifyReceipt(receiptId.trim())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Receipt verification failed.'); }
    finally { setBusy(false); }
  }

  async function runApplication(appId: string, action: () => Promise<ApiRecord>) {
    setAppBusy(appId);
    setAppError(null);
    setAppOutput(null);
    try {
      const data = await action();
      setAppOutput({ id: appId, data });
    } catch (cause) {
      setAppError(cause instanceof Error ? cause.message : 'Application execution failed.');
    } finally {
      setAppBusy(null);
    }
  }

  const boolLabel = (value: unknown) => value === true ? 'Yes' : value === false ? 'No' : 'Not reported';

  return <div className="space-y-7">
    <header className="space-y-2 border-b border-neutral-800 pb-6">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Trust / Evidence & Sovereign Systems</p>
      <h1 className="text-3xl font-semibold tracking-tight text-white">Receipt Verification & Strategic Applications</h1>
      <p className="max-w-3xl text-sm leading-6 text-neutral-400">
        Verify cryptographic execution receipts and execute production-ready operations across the Five Future Sovereign Applications:
        Agentic Sheaf Immune System, Orbital Defense Mesh, Line-Rate zk-ML, Sovereign CBDC Settlement, and Topological Hardware T-ISA.
      </p>
    </header>

    <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
      <form onSubmit={verify} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex-1 space-y-1.5 text-sm text-neutral-300">
          <span>Receipt identifier</span>
          <input
            value={receiptId}
            onChange={(e) => setReceiptId(e.target.value)}
            required
            className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 font-mono text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
            placeholder="Paste a receipt ID"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !receiptId.trim()}
          className="rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-400 disabled:opacity-50"
        >
          {busy ? 'Verifying…' : 'Verify receipt'}
        </button>
      </form>
      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">{error}</p>}
    </Card>

    {result && <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-neutral-500">Observed receipt result</p>
          <h2 className="mt-1 font-semibold text-white">Signature verification response</h2>
        </div>
        <StatusPill status={String(result.qualification_status || 'NOT_REPORTED')} label={String(result.qualification_status || 'Not reported')} showDot={false} />
      </div>
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div><dt className="text-xs text-neutral-500">Receipt ID</dt><dd className="mt-1 break-all font-mono text-xs text-neutral-200">{result.receipt_id || receiptId}</dd></div>
        <div><dt className="text-xs text-neutral-500">Ed25519 signature valid</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.ed25519_verified)}</dd></div>
        <div><dt className="text-xs text-neutral-500">ML-DSA verification</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.ml_dsa_verified)}</dd></div>
        <div><dt className="text-xs text-neutral-500">STARK quotient verification</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.stark_quotient_verified)}</dd></div>
        <div><dt className="text-xs text-neutral-500">Release gates evaluated</dt><dd className="mt-1 text-sm text-neutral-200">{typeof result.total_release_gates_evaluated === 'number' ? result.total_release_gates_evaluated : 'Not reported'}</dd></div>
        <div><dt className="text-xs text-neutral-500">Summary</dt><dd className="mt-1 text-sm text-neutral-200">{result.invariant_summary || 'Not reported'}</dd></div>
      </dl>
      <p className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2.5 text-xs leading-5 text-amber-100/80">
        This response reports the verifier's result only. It is not evidence of NCSC, FedRAMP, DoD, FIPS module, or any other certification unless independently documented and validated.
      </p>
    </Card>}

    {/* FIVE FUTURE STRATEGIC APPLICATION ENGINES */}
    <Card className="border-neutral-800 bg-neutral-900/60 p-5 sm:p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-neutral-800 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-400">Zero-Door Strategic Matrix</p>
          <h2 className="text-lg font-semibold text-white">Five Production Application Engines</h2>
        </div>
        <span className="self-start sm:self-auto rounded bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-400 border border-emerald-500/20">
          Live Substrate Simulation Active
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* App 1: Agentic Sheaf */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-4 space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-indigo-400">01. Agentic Sheaf Immune System</span>
              <span className="font-mono text-[10px] text-neutral-500">H¹(X; F)</span>
            </div>
            <p className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              Multi-agent execution DAG with Stiefel restriction morphisms and 1-cycle DSW instanton cobordism repair.
            </p>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('sheaf_clean', () => ChronusAPIClient.executeAgenticSheafTurn())}
              className="flex-1 rounded bg-indigo-500/20 px-2.5 py-1.5 text-[11px] font-medium text-indigo-300 hover:bg-indigo-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'sheaf_clean' ? 'Executing…' : 'Harmonic Consensus'}
            </button>
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('sheaf_inj', () => ChronusAPIClient.executeAgenticSheafTurn({
                Planner: [1.0, 0.0, 0.0, 1.0],
                Coder: [99.0, -88.0, 77.0, 66.0],
                Executor: [1.0, 0.0, 0.0, 1.0],
                Tool: [1.0, 0.0, 0.0, 1.0],
              }))}
              className="flex-1 rounded bg-rose-500/20 px-2.5 py-1.5 text-[11px] font-medium text-rose-300 hover:bg-rose-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'sheaf_inj' ? 'Healing…' : 'Inject & Heal'}
            </button>
          </div>
        </div>

        {/* App 2: Orbital Mesh */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-4 space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-blue-400">02. Orbital Satellite Mesh</span>
              <span className="font-mono text-[10px] text-neutral-500">PSL₂(F₂₅₇)</span>
            </div>
            <p className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              SDA PWSA constellation telemetry encoded into exact ℤ[ζ₅] anyon braid knots across Ramanujan expander.
            </p>
          </div>
          <div className="pt-2">
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('orbital', () => ChronusAPIClient.transmitOrbitalTelemetry())}
              className="w-full rounded bg-blue-500/20 px-2.5 py-1.5 text-[11px] font-medium text-blue-300 hover:bg-blue-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'orbital' ? 'Transmitting…' : 'Transmit Zero-Stall Telemetry'}
            </button>
          </div>
        </div>

        {/* App 3: Line-Rate zk-ML */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-4 space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-purple-400">03. Line-Rate zk-ML Inference</span>
              <span className="font-mono text-[10px] text-neutral-500">P(x)/Z_H(x)</span>
            </div>
            <p className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              Sub-millisecond forward pass trace verification via exact polynomial quotient long division over F₂₅₇.
            </p>
          </div>
          <div className="pt-2">
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('zkml', () => ChronusAPIClient.executeZkNeuralProveAndVerify())}
              className="w-full rounded bg-purple-500/20 px-2.5 py-1.5 text-[11px] font-medium text-purple-300 hover:bg-purple-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'zkml' ? 'Proving…' : 'Generate & Verify STARK Proof'}
            </button>
          </div>
        </div>

        {/* App 4: Sovereign CBDC Settlement */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-4 space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-emerald-400">04. Sovereign CBDC Rails</span>
              <span className="font-mono text-[10px] text-neutral-500">∂₁(γ) = 0</span>
            </div>
            <p className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              Homological boundary conservation law for RTGS cross-border liquidity and Hecke eigenform Weil bound.
            </p>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('cbdc_valid', () => ChronusAPIClient.processCBDCCrossBorderSettlement())}
              className="flex-1 rounded bg-emerald-500/20 px-2.5 py-1.5 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'cbdc_valid' ? 'Settling…' : 'Valid RTGS Commit'}
            </button>
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('cbdc_double', () => ChronusAPIClient.processCBDCCrossBorderSettlement('FEDERAL_RESERVE', 'BANK_OF_ENGLAND', 10000000, true))}
              className="flex-1 rounded bg-rose-500/20 px-2.5 py-1.5 text-[11px] font-medium text-rose-300 hover:bg-rose-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'cbdc_double' ? 'Checking…' : 'Double-Spend Test'}
            </button>
          </div>
        </div>

        {/* App 5: Hardware T-ISA Coprocessor */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-4 space-y-3 flex flex-col justify-between md:col-span-2 lg:col-span-2">
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-amber-400">05. Topological Hardware ISA (T-ISA)</span>
              <span className="font-mono text-[10px] text-neutral-500">RoCC ALU · 0x0B</span>
            </div>
            <p className="text-xs text-neutral-400 mt-1.5 leading-relaxed">
              Cycle-accurate RISC-V RoCC silicon ALU executing T_CYCLO_MUL mod Φ₅(x) and gate-level T_SHEAF_INSPECT with instant memory bus egress suppression.
            </p>
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('tisa_mul', () => ChronusAPIClient.executeTISAMicrocode(0x02))}
              className="flex-1 rounded bg-amber-500/20 px-2.5 py-1.5 text-[11px] font-medium text-amber-300 hover:bg-amber-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'tisa_mul' ? 'Running…' : 'Run T_CYCLO_MUL'}
            </button>
            <button
              type="button"
              disabled={appBusy !== null}
              onClick={() => runApplication('tisa_trap', () => ChronusAPIClient.executeTISAMicrocode(0x03, [10, 0, 0, 0], [0, 10, 0, 0]))}
              className="flex-1 rounded bg-rose-500/20 px-2.5 py-1.5 text-[11px] font-medium text-rose-300 hover:bg-rose-500/30 transition disabled:opacity-50"
            >
              {appBusy === 'tisa_trap' ? 'Trapping…' : 'Test Sheaf Gate Trap'}
            </button>
          </div>
        </div>
      </div>

      {appError && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-200">
          <p className="font-semibold">Application Fault Detected:</p>
          <p className="font-mono mt-1 text-[11px]">{appError}</p>
        </div>
      )}

      {appOutput && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-white">Execution Telemetry Stream ({appOutput.id})</span>
            <span className="font-mono text-[10px] text-neutral-400">Response Code: 200 OK</span>
          </div>
          <pre className="max-h-60 overflow-auto rounded bg-neutral-900/90 p-3 font-mono text-[11px] text-emerald-300 leading-relaxed border border-neutral-800">
            {JSON.stringify(appOutput.data, null, 2)}
          </pre>
        </div>
      )}
    </Card>
  </div>;
}
