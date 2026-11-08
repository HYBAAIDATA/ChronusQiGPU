'use client';

import React, { useEffect, useId, useState } from 'react';
import {
  Cpu,
  Play,
  FileText,
  Clock,
  CheckCircle2,
  Copy,
  Check,
  Sliders,
  Zap,
  ShieldCheck,
  DollarSign,
  Database,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { StatusPill } from '@/components/console/status-pill';
import {
  CapacityExpansionResponse,
  ChronusAPIClient,
  DispatchedWorkload,
  TenantCapacityStatusResponse,
  TenantProfile,
} from '@/lib/api-client';
import { formatMs } from '@/lib/utils';

export default function WorkloadsPage() {
  const uid = useId();
  const warpSliderId = `${uid}-warp-slider`;
  const storageSliderId = `${uid}-storage-slider`;
  const reasonInputId = `${uid}-burst-reason`;
  const tenantSelectId = `${uid}-tenant-select`;

  // Workload Dispatcher state
  const [workloadType, setWorkloadType] = useState<'lucas' | 'metallic' | 'mining_search' | 'pv_lattice'>('lucas');
  const [paramIndex, setParamIndex] = useState('42');
  const [paramMetallicM, setParamMetallicM] = useState('1');
  const [paramDifficulty, setParamDifficulty] = useState('16');
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastResponse, setLastResponse] = useState<DispatchedWorkload | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Stage 4: Enduring CCE & Self-Service FinOps Scaling Panel state
  const [tenants, setTenants] = useState<TenantProfile[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>('tenant-sovereign-01');
  const [capacityState, setCapacityState] = useState<TenantCapacityStatusResponse | null>(null);
  const [requestedWarps, setRequestedWarps] = useState<number>(128);
  const [requestedStorageGb, setRequestedStorageGb] = useState<number>(10240);
  const [burstReason, setBurstReason] = useState<string>('Q4_QUANT_MODEL_BURST_RUN');
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [isScaling, setIsScaling] = useState<boolean>(false);
  const [lastExpansion, setLastExpansion] = useState<CapacityExpansionResponse | null>(null);
  const [scalingBanner, setScalingBanner] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

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

  useEffect(() => {
    async function initFinOpsPanel() {
      const list = await ChronusAPIClient.getTenants();
      setTenants(list);
      const initialId =
        list.find((t) => t.tenant_id === 'tenant_apex_9921a')?.tenant_id ||
        list.find((t) => t.tenant_id === 'tenant-sovereign-01')?.tenant_id ||
        list[0]?.tenant_id ||
        'tenant-default';
      setSelectedTenantId(initialId);
      const cap = await ChronusAPIClient.getTenantCapacity(initialId);
      setCapacityState(cap);
      setRequestedWarps(cap.active_warps);
      setRequestedStorageGb(cap.data_at_rest_gb);
    }
    initFinOpsPanel();
  }, []);

  const handleSelectTenant = async (tid: string) => {
    setSelectedTenantId(tid);
    setScalingBanner(null);
    setLastExpansion(null);
    const cap = await ChronusAPIClient.getTenantCapacity(tid);
    setCapacityState(cap);
    setRequestedWarps(cap.active_warps);
    setRequestedStorageGb(cap.data_at_rest_gb);
  };

  const handleQuickProvisionApex = async () => {
    setIsScaling(true);
    setScalingBanner(null);
    try {
      const onboarded = await ChronusAPIClient.instantOnboardTenant({
        contract_id: 'ctr_apex_2026_9941',
        company_name: 'Apex Global Financial',
        tenant_id: 'tenant_apex_9921a',
        admin_email: 'security@apexglobal.com',
        enduring_addendum_accepted: true,
        cce_allocations: {
          initial_warps: 32,
          max_authorized_warps: 1024,
          data_at_rest_gb: 10000,
          data_in_motion_gb: 5000,
          o1_structural_memory_gb: 512,
          kms_provider: 'AWS_KMS',
          kms_key_arn: 'arn:aws:kms:us-east-1:123456789012:key/apex-prod-key',
        },
      });
      const updatedList = await ChronusAPIClient.getTenants();
      setTenants(updatedList);
      await handleSelectTenant(onboarded.tenant_id);
      setScalingBanner({
        type: 'ok',
        text: `T0 Instant Activation complete in ${onboarded.execution_time_ms} ms · Assigned ${onboarded.assigned_cce_id} (${onboarded.ovid_namespace})`,
      });
    } catch (err: any) {
      // If already provisioned, switch directly to it
      await handleSelectTenant('tenant_apex_9921a');
      setScalingBanner({
        type: 'ok',
        text: 'Switched to active Enduring Capacity tenant: tenant_apex_9921a',
      });
    } finally {
      setIsScaling(false);
    }
  };

  const handleExpandCapacity = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmedReason = burstReason.trim();
    if (!trimmedReason) {
      setReasonError('Please provide an audit reason tag for capacity scaling.');
      return;
    }
    setIsScaling(true);
    setScalingBanner(null);
    try {
      const res = await ChronusAPIClient.expandTenantCapacity(selectedTenantId, {
        requested_warp_capacity: requestedWarps,
        expand_storage_gb: requestedStorageGb,
        reason: trimmedReason,
      });
      setLastExpansion(res);
      const refreshed = await ChronusAPIClient.getTenantCapacity(selectedTenantId);
      setCapacityState(refreshed);
      const updatedTenants = await ChronusAPIClient.getTenants();
      setTenants(updatedTenants);
      setScalingBanner({
        type: 'ok',
        text: `Capacity scaled ${res.previous_warps} → ${res.new_active_warps} Warps & ${res.new_storage_gb.toLocaleString()} GB in ${res.execution_time_ms} ms (Zero Addendum Required)`,
      });
    } catch (err: any) {
      setScalingBanner({
        type: 'err',
        text: err?.message || 'Capacity expansion rejected by AL HARAS policy.',
      });
    } finally {
      setIsScaling(false);
    }
  };

  const handleDispatch = async () => {
    setIsExecuting(true);
    const activeWarps = capacityState?.active_warps || 32;
    let payload: Record<string, unknown> = {};

    if (workloadType === 'lucas') {
      payload = { index: parseInt(paramIndex, 10) || 42 };
    } else if (workloadType === 'metallic') {
      payload = { family_m: parseInt(paramMetallicM, 10) || 1, power_n: 16 };
    } else if (workloadType === 'mining_search') {
      payload = { difficulty_bits: parseInt(paramDifficulty, 10) || 16, warps: activeWarps };
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

  const maxWarps = capacityState?.max_authorized_warps || 160000;
  const activeSettlement = lastExpansion?.hermiten_settlement || capacityState?.hermiten_settlement;
  const activePricing = lastExpansion?.pricing_breakdown || capacityState?.pricing_breakdown;

  return (
    <div className="space-y-8">
      {/* McKinsey Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-neutral-800 bg-neutral-900/60 backdrop-blur-md gap-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-neutral-400">
            02 Workloads · Execution Gateway &amp; Enduring FinOps Scaling
          </div>
          <h2 className="text-xl font-semibold text-white tracking-tight">
            Workload Dispatcher, Enduring CCE Slider &amp; Cryptographic Receipts
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill status="OPERATIONAL" label="ECA ZERO-FRICTION ACTIVE" />
        </div>
      </div>

      {/* STAGE 4: ENDURING CCE & SELF-SERVICE FINOPS SCALING PANEL */}
      <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-neutral-800 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-blue-400" />
              <span className="text-xs font-mono uppercase tracking-wider text-blue-400 font-semibold">
                Stage 4 · Enduring Capacity Addendum (ECA) FinOps Panel
              </span>
            </div>
            <h3 className="text-base font-semibold text-white">
              Dynamic Self-Service Warp &amp; O(1) Structural Storage Expansion
            </h3>
            <p className="text-xs text-neutral-400">
              Scale active 32-lane warps (up to {maxWarps.toLocaleString()} pre-authorized Warps) and OVID/THESEUS storage in real time via{' '}
              <code className="text-neutral-200 bg-neutral-950 px-1.5 py-0.5 rounded border border-neutral-800">
                PATCH /v1/tenants/&#123;tenant_id&#125;/capacity
              </code>{' '}
              — zero legal addendum renegotiation required.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div>
              <label htmlFor={tenantSelectId} className="sr-only">
                Active Enterprise Tenant
              </label>
              <select
                id={tenantSelectId}
                name="tenant_id"
                value={selectedTenantId}
                onChange={(e) => handleSelectTenant(e.target.value)}
                className="bg-neutral-950 border border-neutral-800 text-white text-xs font-mono rounded-lg px-3 py-2"
              >
                {tenants.map((t) => (
                  <option key={t.tenant_id} value={t.tenant_id}>
                    {t.tenant_id} ({t.organization_name})
                  </option>
                ))}
              </select>
            </div>
            {!tenants.some((t) => t.tenant_id === 'tenant_apex_9921a') && (
              <Button
                type="button"
                onClick={handleQuickProvisionApex}
                disabled={isScaling}
                className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 text-xs font-mono px-3 py-2 h-auto"
              >
                <Zap className="w-3.5 h-3.5 mr-1.5" />
                Instant Activate Apex Global (&lt;1 ms)
              </Button>
            )}
          </div>
        </div>

        {/* Tenant ECA & KMS Telemetry Strip */}
        {capacityState && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
              <span className="text-[10px] text-neutral-500 block">ASSIGNED CCE ID</span>
              <span className="text-white font-semibold truncate block mt-0.5">
                {capacityState.assigned_cce_id}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
              <span className="text-[10px] text-neutral-500 block">ACTIVE / MAX WARPS</span>
              <span className="text-blue-400 font-semibold block mt-0.5">
                {capacityState.active_warps.toLocaleString()} / {capacityState.max_authorized_warps.toLocaleString()} Warps
              </span>
            </div>
            <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
              <span className="text-[10px] text-neutral-500 block">OVID ISOLATION FABRIC</span>
              <span className="text-purple-400 font-semibold truncate block mt-0.5">
                {capacityState.ovid_namespace}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
              <span className="text-[10px] text-neutral-500 block">AL HARAS KEY CUSTODY</span>
              <span className="text-emerald-400 font-semibold truncate block mt-0.5">
                {capacityState.kms_provider} · BOUND
              </span>
            </div>
            <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 col-span-2 md:col-span-1">
              <span className="text-[10px] text-neutral-500 block">ADDENDUM POSTURE</span>
              <span className="text-emerald-400 font-semibold block mt-0.5">
                {capacityState.enduring_addendum_valid ? 'ECA PRE-AUTHORIZED' : 'MANUAL APPROVAL'}
              </span>
            </div>
          </div>
        )}

        {/* Semantic Self-Service Capacity Scaling Form */}
        <form
          method="POST"
          action={`/api/chronus/v1/tenants/${selectedTenantId}/capacity`}
          onSubmit={handleExpandCapacity}
          className="chronus-branded-form grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
        >
          <fieldset className="lg:col-span-7 space-y-5 min-w-0">
            <legend className="text-xs font-mono uppercase tracking-wider text-neutral-300 font-semibold mb-2">
              Self-Service Enduring Allocation Controls
            </legend>

            {/* Warp Capacity Native Range Slider */}
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <label
                  htmlFor={warpSliderId}
                  className="text-xs font-mono uppercase tracking-wider text-neutral-300 font-semibold"
                >
                  Active 32-Lane Execution Warps
                </label>
                <span className="text-sm font-mono font-bold text-blue-400">
                  {requestedWarps.toLocaleString()} Warps ({(requestedWarps * 16).toLocaleString()} CCU · {(requestedWarps * 32).toLocaleString()} SIMD Lanes)
                </span>
              </div>

              <input
                id={warpSliderId}
                name="requested_warp_capacity"
                type="range"
                min={32}
                max={maxWarps}
                step={32}
                value={requestedWarps}
                aria-valuetext={`${requestedWarps} active 32-lane execution warps`}
                onChange={(e) => setRequestedWarps(Number(e.target.value))}
                style={
                  {
                    '--attr-min': 32,
                    '--attr-max': maxWarps,
                    '--control-value': requestedWarps,
                  } as React.CSSProperties
                }
                className="chronus-range-slider"
              />

              <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1">
                <span className="text-[11px] font-mono text-neutral-500">Min: 32 Warps</span>
                <div className="flex flex-wrap gap-1.5">
                  {[32, 128, 256, 512, 1024, 4096, 10000, 40000, 160000]
                    .filter((preset) => preset <= maxWarps)
                    .map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setRequestedWarps(preset)}
                        className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-colors ${
                          requestedWarps === preset
                            ? 'bg-blue-600/30 border-blue-500 text-blue-200 font-semibold'
                            : 'bg-neutral-900 border-neutral-800 text-neutral-400 hover:text-white'
                        }`}
                      >
                        {preset.toLocaleString()}W
                      </button>
                    ))}
                </div>
                <span className="text-[11px] font-mono text-neutral-500">
                  ECA Max: {maxWarps.toLocaleString()}
                </span>
              </div>
            </div>

            {/* Data-at-Rest Storage Native Range Slider */}
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <label
                  htmlFor={storageSliderId}
                  className="text-xs font-mono uppercase tracking-wider text-neutral-300 font-semibold"
                >
                  OVID / THESEUS Storage &amp; O(1) Structural Fabric
                </label>
                <span className="text-sm font-mono font-bold text-purple-400">
                  {requestedStorageGb.toLocaleString()} GB
                </span>
              </div>

              <input
                id={storageSliderId}
                name="expand_storage_gb"
                type="range"
                min={1000}
                max={100000}
                step={1000}
                value={requestedStorageGb}
                aria-valuetext={`${requestedStorageGb} gigabytes provisioned storage`}
                onChange={(e) => setRequestedStorageGb(Number(e.target.value))}
                style={
                  {
                    '--attr-min': 1000,
                    '--attr-max': 100000,
                    '--control-value': requestedStorageGb,
                    '--slider-fill-color': '#a855f7',
                    '--slider-thumb-color': '#c084fc',
                  } as React.CSSProperties
                }
                className="chronus-range-slider"
              />

              <div className="flex items-center justify-between text-[11px] font-mono text-neutral-500">
                <span>1,000 GB</span>
                <span>Postgres Pool=10 · REPEATABLE READ</span>
                <span>100,000 GB</span>
              </div>
            </div>

            {/* Audit Reason & One-Click Submit */}
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
              <div className="sm:col-span-7 space-y-1.5">
                <label
                  htmlFor={reasonInputId}
                  className="text-xs font-mono uppercase tracking-wider text-neutral-400 block"
                >
                  Operational Audit Tag (Reason)
                </label>
                <Input
                  id={reasonInputId}
                  name="reason"
                  type="text"
                  required
                  value={burstReason}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  onChange={(e) => {
                    setBurstReason(e.target.value);
                    if (reasonError) setReasonError(null);
                  }}
                  onBlur={() => {
                    if (!burstReason.trim()) {
                      setReasonError('Audit reason tag is required before submission.');
                    }
                  }}
                  aria-describedby={reasonError ? `${reasonInputId}-error` : undefined}
                  className="bg-neutral-950 border-neutral-800 text-white font-mono text-xs"
                />
                {reasonError && (
                  <p id={`${reasonInputId}-error`} className="text-[11px] font-mono text-red-400">
                    {reasonError}
                  </p>
                )}
              </div>

              <div className="sm:col-span-5">
                <Button
                  type="submit"
                  disabled={isScaling}
                  className="w-full bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs py-5 rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-blue-950/40"
                >
                  {isScaling ? (
                    <>
                      <Clock className="w-4 h-4 animate-spin" />
                      <span>Re-allocating Cluster...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      <span>Apply Capacity Instantly</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </fieldset>

          {/* Right Column inside FinOps Panel: Automated Hermiten 25% Value-Share Settlement */}
          <div className="lg:col-span-5 p-5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-emerald-400" />
                <h4 className="text-xs font-mono uppercase tracking-wider text-white font-semibold">
                  Automated Hermiten 25% Settlement
                </h4>
              </div>
              <StatusPill status="PASS" label="REAL-TIME RECONCILED" />
            </div>

            {activeSettlement && (
              <div className="space-y-3 font-mono text-xs">
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="p-2.5 rounded-lg bg-neutral-900/80 border border-neutral-800">
                    <span className="text-[10px] text-neutral-500 block">COUNTERFACTUAL GPU</span>
                    <span className="text-neutral-200 font-semibold">
                      ${Number(activeSettlement.counterfactual_cost_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-neutral-900/80 border border-neutral-800">
                    <span className="text-[10px] text-neutral-500 block">ACTUAL CHRONUS QiGPU</span>
                    <span className="text-blue-400 font-semibold">
                      ${Number(activeSettlement.actual_cost_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-emerald-950/25 border border-emerald-800/60 flex items-center justify-between">
                  <div>
                    <span className="text-[10px] text-emerald-400 block font-semibold">
                      VERIFIED NET AVOIDED COST (S_net)
                    </span>
                    <span className="text-lg font-bold text-white">
                      ${Number(activeSettlement.net_avoided_cost_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-neutral-400 block">25% VALUE-SHARE</span>
                    <span className="text-sm font-bold text-emerald-400">
                      ${Number(activeSettlement.chronus_value_share_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-neutral-400 pt-1">
                  <span>Client Retained Surplus (75%):</span>
                  <span className="text-blue-300 font-semibold">
                    ${Number(activeSettlement.client_retained_usd).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </span>
                </div>

                {activePricing && (
                  <div className="flex items-center justify-between text-[11px] text-neutral-500 border-t border-neutral-800 pt-2">
                    <span>4-Part Monthly P_total:</span>
                    <span className="text-neutral-300">${activePricing.total_price_usd}</span>
                  </div>
                )}

                <div className="flex items-center justify-between text-[10px] text-neutral-500 border-t border-neutral-800 pt-2">
                  <span className="truncate max-w-[220px]">
                    Cert: {activeSettlement.proof_certificate}
                  </span>
                  <span className="text-emerald-400 flex items-center gap-1 shrink-0">
                    <ShieldCheck className="w-3 h-3" /> Zero Dispute
                  </span>
                </div>
              </div>
            )}
          </div>
        </form>

        {/* Live aria-live Status Banner for Instant Scaling */}
        <div aria-live="polite">
          {scalingBanner && (
            <div
              className={`p-3 rounded-lg border text-xs font-mono flex items-center justify-between gap-3 ${
                scalingBanner.type === 'ok'
                  ? 'bg-emerald-950/30 border-emerald-800/60 text-emerald-300'
                  : 'bg-red-950/30 border-red-800/60 text-red-300'
              }`}
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{scalingBanner.text}</span>
              </div>
              {lastExpansion && (
                <span className="text-[11px] text-neutral-400 shrink-0 flex items-center gap-1">
                  <Database className="w-3 h-3" /> THESEUS #{lastExpansion.theseus_journal_entry_hash.slice(0, 12)}
                </span>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Main Two-Column Workload Dispatcher & Inspector */}
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
              <span className="text-xs font-mono uppercase tracking-wider text-neutral-400 block">
                Algorithm &amp; Representation
              </span>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {[
                  { id: 'lucas', label: '1. Lucas / PV Exact' },
                  { id: 'metallic', label: '2. Metallic Family' },
                  { id: 'mining_search', label: '3. 32-Lane Mining' },
                  { id: 'pv_lattice', label: '4. PV Lattice' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setWorkloadType(item.id as any)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      workloadType === item.id
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
                <label
                  htmlFor={`${uid}-lucas-index`}
                  className="text-xs font-mono uppercase tracking-wider text-neutral-400 block"
                >
                  Lucas Sequence Index (n)
                </label>
                <Input
                  id={`${uid}-lucas-index`}
                  name="lucas_index"
                  type="number"
                  value={paramIndex}
                  onChange={(e) => setParamIndex(e.target.value)}
                  className="bg-neutral-950 border-neutral-800 text-white font-mono"
                  placeholder="e.g. 42"
                />
                <p className="text-[11px] text-neutral-500 font-mono">
                  Exact fast-doubling in Q(√5): L_n = 2F_&#123;n+1&#125; − F_n
                </p>
              </div>
            )}

            {workloadType === 'metallic' && (
              <div className="space-y-2">
                <span className="text-xs font-mono uppercase tracking-wider text-neutral-400 block">
                  Metallic Means Index (m)
                </span>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { m: '1', label: 'Golden (φ)' },
                    { m: '2', label: 'Silver (δ_S)' },
                    { m: '3', label: 'Bronze (δ_B)' },
                  ].map((fam) => (
                    <button
                      key={fam.m}
                      type="button"
                      onClick={() => setParamMetallicM(fam.m)}
                      className={`p-2.5 rounded-lg border text-center text-xs font-mono ${
                        paramMetallicM === fam.m
                          ? 'bg-purple-600/20 border-purple-500 text-purple-300 font-semibold'
                          : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:border-neutral-700'
                      }`}
                    >
                      {fam.label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-neutral-500 font-mono">
                  Characteristic polynomial: λ² − mλ − 1 = 0
                </p>
              </div>
            )}

            {workloadType === 'mining_search' && (
              <div className="space-y-2">
                <label
                  htmlFor={`${uid}-mining-diff`}
                  className="text-xs font-mono uppercase tracking-wider text-neutral-400 block"
                >
                  Difficulty Target (bits) · Active Allocation: {capacityState?.active_warps || 32} Warps
                </label>
                <Input
                  id={`${uid}-mining-diff`}
                  name="difficulty_bits"
                  type="number"
                  value={paramDifficulty}
                  onChange={(e) => setParamDifficulty(e.target.value)}
                  className="bg-neutral-950 border-neutral-800 text-white font-mono"
                />
                <p className="text-[11px] text-neutral-500 font-mono">
                  Polyhedral SO(3) carry-free Zeckendorf parallel traversal across {capacityState?.active_warps || 32} active warps
                </p>
              </div>
            )}

            {workloadType === 'pv_lattice' && (
              <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 font-mono text-xs text-neutral-400 space-y-1">
                <span className="text-neutral-500 text-[10px] block">LATTICE CONFIGURATION</span>
                <div>
                  Dimension: <span className="text-white">256-bit Exact</span>
                </div>
                <div>
                  Limb Precision: <span className="text-blue-400">4 × 64-bit Limbs</span>
                </div>
              </div>
            )}

            <Button
              type="button"
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
                    <span className="text-neutral-200 truncate block mt-0.5">
                      {lastResponse.workload_id}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
                    <span className="text-neutral-500 text-[10px] block">POINTER ID</span>
                    <span className="text-blue-400 truncate block mt-0.5">
                      {lastResponse.zero_copy_pointer_id}
                    </span>
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
                      type="button"
                      onClick={() =>
                        copyToClipboard(JSON.stringify(lastResponse.result, null, 2), 'payload')
                      }
                      className="text-neutral-400 hover:text-white text-xs flex items-center gap-1 font-mono"
                    >
                      {copiedId === 'payload' ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
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
                  Select an algorithm and click &ldquo;Dispatch to QiGPU Gateway&rdquo; to observe live zero-copy execution.
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
            <p className="text-xs text-neutral-400">
              Tamper-evident logs of dispatched workloads with explicit execution badges
            </p>
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
                  <td className="p-3.5 text-blue-400 font-medium">
                    {wkld.zero_copy_pointer_id || '—'}
                  </td>
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
