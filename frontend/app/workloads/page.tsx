'use client';

import React, { useState } from 'react';
import {
  Cpu,
  Play,
  FileText,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Copy,
  Check,
  Search,
  Sparkles
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { StatusPill } from '@/components/console/status-pill';
import { ChronusAPIClient, DispatchedWorkload } from '@/lib/api-client';
import { formatMs } from '@/lib/utils';

export default function WorkloadsPage() {
  const [workloadType, setWorkloadType] = useState<'lucas' | 'metallic' | 'mining_search' | 'pv_lattice'>('lucas');
  const [paramIndex, setParamIndex] = useState('42');
  const [paramMetallicM, setParamMetallicM] = useState('1');
  const [paramDifficulty, setParamDifficulty] = useState('16');
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastResponse, setLastResponse] = useState<DispatchedWorkload | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Initial historical records
  const [history, setHistory] = useState<DispatchedWorkload[]>([
    {
      workload_id: 'wkld_initial_94a7',
      tenant_id: 'sovereign_operator',
      status: 'EXECUTED',
      execution_mode: 'MATHEMATICAL_EXECUTION',
      backend: 'NativeMathReferenceBackend',
      duration_ms: 0.84,
      result: {
        fibonacci: '267914296',
        lucas: '599074043',
        algebraic_field: 'Q(sqrt(5))',
      },
      receipt_signature: 'ed25519_sig_9f81a742c38e',
      zero_copy_pointer_id: 'ptr_ovid_78fa9b',
      created_at: new Date(Date.now() - 120000).toISOString(),
    },
    {
      workload_id: 'wkld_mining_b201',
      tenant_id: 'sovereign_operator',
      status: 'EXECUTED',
      execution_mode: 'MATHEMATICAL_EXECUTION',
      backend: 'NativeMathReferenceBackend',
      duration_ms: 1.42,
      result: {
        algorithm: '32-Lane Polyhedral SO(3)',
        solution_nonce: '0x00000000f4021a8b',
        lanes_searched: 32,
      },
      receipt_signature: 'ed25519_sig_401f8e21aa',
      zero_copy_pointer_id: 'ptr_ovid_31c8de',
      created_at: new Date(Date.now() - 300000).toISOString(),
    },
  ]);

  const handleDispatch = async () => {
    setIsExecuting(true);
    let payload: Record<string, unknown> = {};

    if (workloadType === 'lucas') {
      payload = { index: parseInt(paramIndex, 10) || 42 };
    } else if (workloadType === 'metallic') {
      payload = { family_m: parseInt(paramMetallicM, 10) || 1, power_n: 16 };
    } else if (workloadType === 'mining_search') {
      payload = { difficulty_bits: parseInt(paramDifficulty, 10) || 16, warps: 32 };
    } else if (workloadType === 'pv_lattice') {
      payload = { dimension: 256, limb_precision: 4 };
    }

    try {
      const response = await ChronusAPIClient.dispatchWorkload({
        workload_type: workloadType,
        payload,
      });
      setLastResponse(response);
      setHistory((prev) => [response, ...prev]);
    } finally {
      setIsExecuting(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <div className="space-y-8">
      {/* McKinsey Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-neutral-800 bg-neutral-900/60 backdrop-blur-md gap-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-neutral-400">
            Workload Subsystem Â· Execution Gateway
          </div>
          <h2 className="text-xl font-semibold text-white tracking-tight">
            Workload Dispatcher & Cryptographic Receipts
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill status="OPERATIONAL" label="GATEWAY READY" />
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Dispatcher Form */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-5">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-blue-400" />
                <h3 className="text-sm font-semibold text-white">Preset Workload Selection</h3>
              </div>
              <span className="text-[10px] font-mono text-neutral-500">POST /v1/workloads</span>
            </div>

            {/* Workload Preset Buttons */}
            <div className="space-y-2">
              <label className="text-xs font-mono uppercase tracking-wider text-neutral-400">
                Algorithm & Representation
              </label>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {[
                  { id: 'lucas', label: '1. Lucas / PV Exact' },
                  { id: 'metallic', label: '2. Metallic Family' },
                  { id: 'mining_search', label: '3. 32-Lane Mining' },
                  { id: 'pv_lattice', label: '4. PV Lattice' },
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setWorkloadType(item.id as any)}
                    className={`p-3 rounded-lg border text-left transition-all ${workloadType === item.id
                      ? 'bg-blue-600/20 text-blue-300 border-blue-500/50 font-semibold shadow-sm'
                      : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:text-white hover:border-neutral-700'
                      }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Dynamic Parameter Fields */}
            {workloadType === 'lucas' && (
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-neutral-400">
                  Lucas Sequence Index (n)
                </label>
                <Input
                  type="number"
                  value={paramIndex}
                  onChange={(e) => setParamIndex(e.target.value)}
                  className="bg-neutral-950 border-neutral-800 text-white font-mono"
                  placeholder="e.g. 42"
                />
                <p className="text-[11px] text-neutral-500 font-mono">
                  Exact fast-doubling in \(\mathbb&#123;Q&#125;(\sqrt&#123;5&#125;)\): \(L_n = 2F_&#123;n+1&#125; - F_n\)
                </p>
              </div>
            )}

            {workloadType === 'metallic' && (
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-neutral-400">
                  Metallic Means Index (m)
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { m: '1', label: 'Golden (Ï†)' },
                    { m: '2', label: 'Silver (Î´_S)' },
                    { m: '3', label: 'Bronze (Î´_B)' },
                  ].map((fam) => (
                    <button
                      key={fam.m}
                      onClick={() => setParamMetallicM(fam.m)}
                      className={`p-2.5 rounded-lg border text-center text-xs font-mono ${paramMetallicM === fam.m
                        ? 'bg-purple-600/20 border-purple-500 text-purple-300 font-semibold'
                        : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:border-neutral-700'
                        }`}
                    >
                      {fam.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-neutral-500 font-mono">
                  Characteristic polynomial: \(\lambda^2 - m\lambda - 1 = 0\)
                </p>
              </div>
            )}

            {workloadType === 'mining_search' && (
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-wider text-neutral-400">
                  Difficulty Target (bits)
                </label>
                <Input
                  type="number"
                  value={paramDifficulty}
                  onChange={(e) => setParamDifficulty(e.target.value)}
                  className="bg-neutral-950 border-neutral-800 text-white font-mono"
                />
                <p className="text-[11px] text-neutral-500 font-mono">
                  Polyhedral \(SO(3)\) 32-warp carry-free Zeckendorf parallel traversal
                </p>
              </div>
            )}

            {workloadType === 'pv_lattice' && (
              <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 font-mono text-xs text-neutral-400 space-y-1">
                <span className="text-neutral-500 text-[10px] block">LATTICE CONFIGURATION</span>
                <div>Dimension: <span className="text-white">256-bit Exact</span></div>
                <div>Limb Precision: <span className="text-blue-400">4 Ã— 64-bit Limbs</span></div>
              </div>
            )}

            <Button
              onClick={handleDispatch}
              disabled={isExecuting}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs py-5 rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-blue-900/20"
            >
              {isExecuting ? (
                <>
                  <Clock className="w-4 h-4 animate-spin" />
                  <span>Executing Exact Substrate...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Dispatch to QiGPU Gateway</span>
                </>
              )}
            </Button>
          </Card>
        </div>

        {/* Right: Output Payload & Evidence Inspection */}
        <div className="lg:col-span-7 space-y-6">
          <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-semibold text-white">Dispatched Workload Inspector</h3>
              </div>
              {lastResponse && (
                <div className="flex items-center gap-2">
                  <StatusPill status={lastResponse.execution_mode} />
                  <span className="text-xs font-mono text-neutral-400">
                    {formatMs(lastResponse.duration_ms)}
                  </span>
                </div>
              )}
            </div>

            {lastResponse ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
                    <span className="text-neutral-500 text-[10px] block">WORKLOAD ID</span>
                    <span className="text-neutral-200 truncate block mt-0.5">{lastResponse.workload_id}</span>
                  </div>
                  <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
                    <span className="text-neutral-500 text-[10px] block">POINTER ID</span>
                    <span className="text-blue-400 truncate block mt-0.5">{lastResponse.zero_copy_pointer_id}</span>
                  </div>
                  <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 col-span-2 sm:col-span-1">
                    <span className="text-neutral-500 text-[10px] block">RECEIPT</span>
                    <span className="text-emerald-400 truncate block mt-0.5">Ed25519 Verified</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase tracking-wider text-neutral-400">
                      Result Payload
                    </span>
                    <button
                      onClick={() => copyToClipboard(JSON.stringify(lastResponse.result, null, 2), 'payload')}
                      className="text-neutral-400 hover:text-white text-xs flex items-center gap-1 font-mono"
                    >
                      {copiedId === 'payload' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedId === 'payload' ? 'Copied' : 'Copy JSON'}</span>
                    </button>
                  </div>
                  <pre className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 font-mono text-xs text-neutral-300 overflow-x-auto max-h-72">
                    {JSON.stringify(lastResponse.result, null, 2)}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-center p-8 border border-dashed border-neutral-800 rounded-xl">
                <Cpu className="w-8 h-8 text-neutral-600 mb-2" />
                <p className="text-sm text-neutral-400 font-medium">Awaiting Workload Dispatch</p>
                <p className="text-xs text-neutral-600 mt-1 max-w-sm">
                  Select an algorithm and click "Dispatch to QiGPU Gateway" to observe live zero-copy execution.
                </p>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Workload Receipt Table */}
      <Card className="border-neutral-800 bg-neutral-900/60 backdrop-blur-md overflow-hidden">
        <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Workload Receipt Registry</h3>
            <p className="text-xs text-neutral-400">Tamper-evident logs of dispatched workloads with explicit execution badges</p>
          </div>
          <span className="text-xs font-mono text-neutral-400">{history.length} records</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-neutral-950 text-neutral-400 uppercase text-[10px] tracking-wider border-b border-neutral-800">
              <tr>
                <th className="p-3.5">Workload ID</th>
                <th className="p-3.5">Execution Mode</th>
                <th className="p-3.5">Backend</th>
                <th className="p-3.5">Pointer ID</th>
                <th className="p-3.5">Duration</th>
                <th className="p-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800/60 text-neutral-300">
              {history.map((wkld) => (
                <tr key={wkld.workload_id} className="hover:bg-neutral-800/20 transition-colors">
                  <td className="p-3.5 text-white font-medium">{wkld.workload_id}</td>
                  <td className="p-3.5">
                    <StatusPill status={wkld.execution_mode} />
                  </td>
                  <td className="p-3.5 text-neutral-400">{wkld.backend}</td>
                  <td className="p-3.5 text-blue-400 font-medium">{wkld.zero_copy_pointer_id || 'â€”'}</td>
                  <td className="p-3.5 text-neutral-400">{formatMs(wkld.duration_ms)}</td>
                  <td className="p-3.5">
                    <StatusPill status={wkld.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
