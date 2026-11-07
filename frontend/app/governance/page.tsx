'use client';

import React, { useState } from 'react';
import { ShieldCheck, CheckCircle2, XCircle, AlertTriangle, FileKey, Search, Lock, ShieldAlert, Sparkles, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChronusAPIClient, VerifyReceiptResponse } from '@/lib/api-client';

export default function GovernancePage() {
  const [receiptHash, setReceiptHash] = useState('ed25519_sig_9f81a742c38e94a107bf382a93c7d610fa2e894107bc9812401f8e21aa');
  const [verification, setVerification] = useState<VerifyReceiptResponse | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);

  const handleVerify = async () => {
    setIsVerifying(true);
    try {
      const res = await ChronusAPIClient.verifyReceipt(receiptHash.trim());
      setVerification(res);
    } finally {
      setIsVerifying(false);
    }
  };

  const GATES = [
    {
      gate: 'G1',
      name: 'Scope & Baseline',
      desc: 'Immutable source identity, approved scope, reconciled requirements register',
      status: 'PASS' as const,
      evidence: 'Commit d1f258b, exact algebraic specification',
      authority: 'Product & Tech Lead',
    },
    {
      gate: 'G2',
      name: 'Functional Behavior',
      desc: 'Exact representation arithmetic, deterministic test suite (144+ passing)',
      status: 'PASS' as const,
      evidence: '144/144 unit & integration tests passing',
      authority: 'Verification Lead',
    },
    {
      gate: 'G3',
      name: 'Data Integrity & Recovery',
      desc: 'Durable multi-instance storage, crash recovery, point-in-time backups',
      status: 'BLOCKED' as const,
      evidence: 'PostgreSQL HA with connection pooling & Alembic migrations',
      authority: 'Database / SRE Lead',
    },
    {
      gate: 'G4',
      name: 'Security & Isolation',
      desc: 'OIDC/OAuth2 identity, token rotation, Cloud KMS / HSM key custody',
      status: 'FAIL' as const,
      evidence: 'JWKS token middleware implemented; Cloud KMS migration required',
      authority: 'Security Lead',
    },
    {
      gate: 'G5',
      name: 'Performance & Capacity',
      desc: 'Physical accelerator throughput, measured power efficiency on live fleet',
      status: 'BLOCKED' as const,
      evidence: 'RTL verified in simulation; physical device benchmarks pending',
      authority: 'Hardware / Perf Lead',
    },
    {
      gate: 'G6',
      name: 'Operations & SRE',
      desc: 'Prometheus alert rules, OpenTelemetry, disaster recovery runbooks',
      status: 'BLOCKED' as const,
      evidence: 'Trace spans instrumented; alertmanager rules required',
      authority: 'Operations Lead',
    },
    {
      gate: 'G7',
      name: 'Customer Acceptance',
      desc: 'Customer-observed end-to-end journey on sovereign GCC / London workload',
      status: 'BLOCKED' as const,
      evidence: 'Pilot workload specification defined; execution pending',
      authority: 'Commercial Lead',
    },
    {
      gate: 'G8',
      name: 'Release Decision',
      desc: 'Final release authority sign-off; all gates G1â€“G6 met',
      status: 'FAIL' as const,
      evidence: 'NO-GO: Designated as Working Software Reference Foundation',
      authority: 'Release Authority',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-neutral-800 bg-neutral-900/60 backdrop-blur-md gap-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-neutral-400">
            Governance & Assurance Â· Release Framework
          </div>
          <h2 className="text-xl font-semibold text-white tracking-tight">
            G1â€“G8 Mandatory Release Gates & Cryptographic Receipts
          </h2>
        </div>
        <StatusPill status="FAIL" label="GOVERNANCE: CONDITIONAL FOUNDATION" />
      </div>

      {/* CI Purity Gate Verified Banner */}
      <Card className="p-5 border-emerald-900/40 bg-emerald-950/20 backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">CI Purity Gate: PASSED</h4>
              <p className="text-xs text-neutral-400 mt-0.5 font-mono">
                Scanned: src/chronus/execution, backends, storage, security, quantum
              </p>
            </div>
          </div>
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
            0 THEATRE Â· 0 APPROXIMATION Â· 0 PSEUDORANDOM
          </span>
        </div>
      </Card>

      {/* G1-G8 Mandatory Release Gate Matrix */}
      <Card className="border-neutral-800 bg-neutral-900/60 backdrop-blur-md overflow-hidden">
        <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">
              Mandatory Release Gates (G1â€“G8 Framework)
            </h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Strict governance: docs/system-update/governance-and-acceptance.md
            </p>
          </div>
          <span className="text-xs font-mono text-neutral-400">8 Release Controls</span>
        </div>

        <div className="divide-y divide-neutral-800/80 font-mono text-xs">
          {GATES.map((g) => (
            <div key={g.gate} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-neutral-800/20 transition-colors">
              <div className="flex items-start sm:items-center gap-3.5">
                <span className="px-2.5 py-0.5 rounded bg-neutral-800 text-neutral-200 font-bold text-xs shrink-0">
                  {g.gate}
                </span>
                <div>
                  <div className="font-semibold text-white text-sm">{g.name}</div>
                  <div className="text-neutral-400 text-xs font-sans mt-0.5">{g.desc}</div>
                </div>
              </div>

              <div className="flex items-center gap-4 pl-11 sm:pl-0">
                <span className="text-neutral-400 text-[11px] truncate max-w-xs">{g.evidence}</span>
                <StatusPill status={g.status} />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Cryptographic Receipt Inspector */}
      <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
          <div className="flex items-center gap-2">
            <FileKey className="w-4 h-4 text-purple-400" />
            <h3 className="text-base font-semibold text-white">
              Zero-Auth Cryptographic Receipt Inspector
            </h3>
          </div>
          <span className="text-xs font-mono text-neutral-500">GET /v1/verify/&#123;receipt_hash&#125;</span>
        </div>

        <p className="text-xs text-neutral-300 leading-relaxed font-mono">
          Input any 64-character SHA-256 digest or Ed25519 receipt signature to verify execution authenticity:
        </p>

        <div className="flex gap-2">
          <Input
            value={receiptHash}
            onChange={(e) => setReceiptHash(e.target.value)}
            className="bg-neutral-950 border-neutral-800 font-mono text-xs text-white"
            placeholder="Paste 64-character SHA-256 receipt hash or signature..."
          />
          <Button
            onClick={handleVerify}
            disabled={isVerifying}
            className="bg-purple-600 hover:bg-purple-500 text-white font-medium text-xs px-5"
          >
            {isVerifying ? (
              <Clock className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Search className="w-3.5 h-3.5 mr-1.5" />
            )}
            Verify
          </Button>
        </div>

        {verification && (
          <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 font-mono text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400 font-semibold">Verification Certificate</span>
              <StatusPill status={verification.qualification_status} />
            </div>
            <div className="text-[11px] text-neutral-300">
              {verification.invariant_summary}
            </div>
            {verification.algorithm && (
              <div className="text-[10px] text-neutral-500">
                Algorithm: {verification.algorithm} Â· Verified at: {verification.timestamp}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
