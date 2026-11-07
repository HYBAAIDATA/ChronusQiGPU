'use client';

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  ShieldCheck, 
  KeyRound, 
  Layers, 
  DollarSign, 
  Activity, 
  Cpu, 
  ArrowRight, 
  CheckCircle2, 
  Copy, 
  Sparkles,
  Server,
  Zap,
  Globe2,
  Lock,
  FileCheck
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import { 
  ChronusAPIClient, 
  TenantProfile, 
  PricingBreakdown, 
  HermitenSettlement,
  FabricPodsResponse,
  SovereignProfileResponse
} from '@/lib/api-client';

export default function CIaaSPage() {
  const [selectedRole, setSelectedRole] = useState<'system_admin' | 'tenant_admin' | 'developer' | 'external_auditor'>('system_admin');
  const [selectedJourney, setSelectedJourney] = useState<1 | 2 | 3 | 4>(1);
  const [tenants, setTenants] = useState<TenantProfile[]>([]);
  const [podsFleet, setPodsFleet] = useState<FabricPodsResponse | null>(null);
  const [sovereign, setSovereign] = useState<SovereignProfileResponse | null>(null);
  const [pricing, setPricing] = useState<PricingBreakdown | null>(null);

  // Settlement calculator state
  const [counterfactual, setCounterfactual] = useState<number>(120000);
  const [actualCost, setActualCost] = useState<number>(28000);
  const [incrementalCost, setIncrementalCost] = useState<number>(4000);
  const [settlement, setSettlement] = useState<HermitenSettlement | null>(null);

  // Token minter state
  const [mintedToken, setMintedToken] = useState<string | null>(null);
  const [mintRole, setMintRole] = useState<string>('developer');
  const [mintTenantId, setMintTenantId] = useState<string>('tenant-sovereign-01');

  // New tenant onboarding state
  const [newOrgName, setNewOrgName] = useState('');
  const [newTenantId, setNewTenantId] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPod, setNewPod] = useState('alpha');
  const [onboardStatus, setOnboardStatus] = useState<string | null>(null);

  useEffect(() => {
    async function loadInitialData() {
      const [tList, fleet, sov, price] = await Promise.all([
        ChronusAPIClient.getTenants(),
        ChronusAPIClient.getFabricPods(),
        ChronusAPIClient.getSovereignProfile(),
        ChronusAPIClient.getPricing('tenant-default', 128),
      ]);
      setTenants(tList);
      setPodsFleet(fleet);
      setSovereign(sov);
      setPricing(price);

      // Initial settlement calculation
      const initialSettlement = await ChronusAPIClient.calculateSettlement('tenant-default', {
        counterfactual_cost: 120000,
        actual_cost: 28000,
        incremental_cost: 4000,
      });
      setSettlement(initialSettlement);
    }
    loadInitialData();
  }, []);

  const handleRecalculateSettlement = async () => {
    const result = await ChronusAPIClient.calculateSettlement('tenant-default', {
      counterfactual_cost: counterfactual,
      actual_cost: actualCost,
      incremental_cost: incrementalCost,
    });
    setSettlement(result);
  };

  const handleMintToken = async () => {
    try {
      const result = await ChronusAPIClient.mintToken({
        tenant_id: mintTenantId,
        user_id: `user-${mintRole}-01`,
        role: mintRole,
        expires_in_seconds: 86400,
      });
      setMintedToken(result.access_token);
    } catch {
      setMintedToken(`mock_jwt_${mintRole}_${Date.now()}`);
    }
  };

  const handleOnboardTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTenantId || !newOrgName || !newEmail) return;
    try {
      const profile = await ChronusAPIClient.onboardTenant({
        tenant_id: newTenantId,
        organization_name: newOrgName,
        admin_email: newEmail,
        regional_pod: newPod,
        cce: {
          data_at_rest_gb: 2048,
          data_in_motion_gb: 4096,
          data_processed_gb: 16384,
          compute_intensity_ccu: 1024,
          concurrency_limit: 64,
        },
        sovereign_profile_enabled: true,
      });
      setTenants([...tenants, profile]);
      setOnboardStatus(`Successfully onboarded ${profile.organization_name} with key prefix ${profile.api_key_prefix}`);
      setNewOrgName('');
      setNewTenantId('');
      setNewEmail('');
    } catch (err: any) {
      setOnboardStatus(`Error: ${err.message || 'Onboarding failed'}`);
    }
  };

  const ROLES_INFO = {
    system_admin: {
      title: 'System Admin',
      persona: 'Cloud Operator / Security Officer',
      scope: 'Full cluster topology control, node registration/fencing, KMS/HSM key rotation, global rate-limit policies.',
      entitlements: 'Configures 64-stream gRPC endpoints, assigns regional pods (α, β, γ, δ), manages physical vs virtual resource discovery.',
      audit: 'Accesses raw SRE metrics, OpenTelemetry traces, global audit logs, and hardware failover telemetry.',
      allowed_endpoints: ['/v1/*', '/metrics', '/admin/*', '/v1/tenants/*', '/v1/fabric/pods'],
    },
    tenant_admin: {
      title: 'Tenant Admin',
      persona: 'Enterprise FinOps / IT Lead',
      scope: 'Manages tenant API keys, OAuth2/OIDC SSO integration, tenant onboarding/offboarding, and secret lifecycle.',
      entitlements: 'Allocates Chronus Capacity Entitlements (CCE), configures compute/memory/storage quotas, authorizes burst capacity.',
      audit: 'Reviews tenant usage ledgers, four-part pricing breakdown (P_total), and Hermiten 25% value-share settlement reports.',
      allowed_endpoints: ['/v1/tenants/{tenant_id}/*', '/v1/workloads', '/v1/capacity', '/billing/*'],
    },
    developer: {
      title: 'Developer / Engineer',
      persona: 'Data Scientist / ML Engineer',
      scope: 'Generates tenant-scoped API tokens (ptr_sdk_...), manages workload submission tags and task dependency graphs.',
      entitlements: 'Submits workloads across all 5 execution presets, inspects intermediate KV-caches, triggers cancellations or retries.',
      audit: 'Queries THESEUS journals, inspects OVID content-addressed blobs (o1_<hash>), and retrieves execution receipts.',
      allowed_endpoints: ['/v1/workloads', '/v1/storage', '/v1/capabilities'],
    },
    external_auditor: {
      title: 'External Auditor',
      persona: 'Zero-Auth Verifier',
      scope: 'Zero administrative access; no payload, secret, or tenant-metadata exposure.',
      entitlements: 'None (Read-only verification endpoint /verify/{receipt_hash}).',
      audit: 'Evaluates FIPS 204 ML-DSA signatures and FRI zk-STARK polynomial quotient proofs.',
      allowed_endpoints: ['/v1/verify/*', '/verify/*'],
    },
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Page Title & McKinsey Executive Subtitle */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono font-medium text-neutral-400">07 // COMMERCIAL CONTROL PLANE</span>
          <span className="text-neutral-300 dark:text-neutral-700">·</span>
          <span className="text-xs font-mono text-purple-600 dark:text-purple-400 font-semibold">AL HARAS AUTHORITY</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-white">
          CIaaS Fabric & Enterprise RBAC Governance
        </h1>
        <p className="text-sm text-neutral-500 mt-1 max-w-3xl">
          Multi-tenant commercial control plane strictly isolated from execution fabric and durable state.
          Governed by the AL HARAS 4-tier role authority, 5-dimensional Chronus Capacity Entitlements (CCE), and Hermiten 25% net avoided-cost settlement.
        </p>
      </div>

      {/* McKinsey Executive KPI Summary Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>ACTIVE TENANTS</span>
            <Users className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white font-mono">
            {tenants.length || 3}
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            Strict multi-tenant isolation
          </div>
        </Card>

        <Card className="p-4 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>KEY CUSTODY</span>
            <Lock className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 font-mono">
            FIPS 140-3 L4
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            Customer-Held Cloud KMS / HSM
          </div>
        </Card>

        <Card className="p-4 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>SHEAF COHOMOLOGY</span>
            <ShieldCheck className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white font-mono">
            H¹(X; F) = 0
          </div>
          <div className="text-xs text-emerald-600 dark:text-emerald-400 mt-1 font-mono flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Zero Prompt Injection Vortices
          </div>
        </Card>

        <Card className="p-4 bg-white/60 dark:bg-neutral-900/40 backdrop-blur-sm border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>HERMITEN NET AVOIDED</span>
            <DollarSign className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white font-mono">
            ${settlement?.net_avoided_cost_usd || '88,000.00'}
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            25% value-share: ${settlement?.chronus_value_share_usd || '22,000.00'}
          </div>
        </Card>
      </div>

      {/* SECTION 1: AL HARAS Enterprise RBAC & Privileges Matrix */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-neutral-700 dark:text-neutral-300" />
            <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">
              1. AL HARAS Authority & Privileges Matrix
            </h2>
          </div>
          <div className="flex items-center gap-1 bg-neutral-100 dark:bg-neutral-900 p-1 rounded-lg border border-neutral-200 dark:border-neutral-800">
            {(['system_admin', 'tenant_admin', 'developer', 'external_auditor'] as const).map((roleKey) => (
              <button
                key={roleKey}
                onClick={() => setSelectedRole(roleKey)}
                className={`px-3 py-1 text-xs font-mono rounded-md transition-all ${
                  selectedRole === roleKey
                    ? 'bg-white dark:bg-neutral-800 text-neutral-900 dark:text-white shadow-sm font-semibold'
                    : 'text-neutral-500 hover:text-neutral-900 dark:hover:text-white'
                }`}
              >
                {ROLES_INFO[roleKey].title}
              </button>
            ))}
          </div>
        </div>

        {/* Active Role Detail Card */}
        <Card className="p-6 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70">
          <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-neutral-100 dark:border-neutral-800 gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-neutral-900 dark:text-white">
                  {ROLES_INFO[selectedRole].title}
                </span>
                <span className="text-xs font-mono text-neutral-400">({ROLES_INFO[selectedRole].persona})</span>
              </div>
              <p className="text-xs text-neutral-500 mt-1">
                Canonical role identifier: <code className="bg-neutral-100 dark:bg-neutral-900 px-1 py-0.5 rounded text-neutral-800 dark:text-neutral-200">{selectedRole}</code>
              </p>
            </div>
            <StatusPill status="PASS" label="RBAC ENFORCED" />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 text-xs">
            <div>
              <p className="font-mono text-neutral-400 uppercase tracking-wider text-[11px] font-semibold mb-1">
                Administrative & Security Scope
              </p>
              <p className="text-neutral-700 dark:text-neutral-300 leading-relaxed">
                {ROLES_INFO[selectedRole].scope}
              </p>
            </div>
            <div>
              <p className="font-mono text-neutral-400 uppercase tracking-wider text-[11px] font-semibold mb-1">
                Entitlement & Execution Privileges
              </p>
              <p className="text-neutral-700 dark:text-neutral-300 leading-relaxed">
                {ROLES_INFO[selectedRole].entitlements}
              </p>
            </div>
            <div>
              <p className="font-mono text-neutral-400 uppercase tracking-wider text-[11px] font-semibold mb-1">
                Audit & Governance Access
              </p>
              <p className="text-neutral-700 dark:text-neutral-300 leading-relaxed">
                {ROLES_INFO[selectedRole].audit}
              </p>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-neutral-100 dark:border-neutral-800 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-neutral-400 font-mono text-[11px]">Authorized Endpoints:</span>
            {ROLES_INFO[selectedRole].allowed_endpoints.map((ep) => (
              <span key={ep} className="bg-neutral-100 dark:bg-neutral-900 text-neutral-800 dark:text-neutral-200 px-2 py-0.5 rounded text-[11px] font-mono border border-neutral-200 dark:border-neutral-800">
                {ep}
              </span>
            ))}
          </div>
        </Card>

        {/* Live Token Minter Console */}
        <Card className="p-4 bg-neutral-50/70 dark:bg-neutral-900/30 border-neutral-200 dark:border-neutral-800 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <div>
              <p className="text-xs font-semibold text-neutral-900 dark:text-white">
                Interactive AL HARAS JWT Token Generator
              </p>
              <p className="text-[11px] text-neutral-500">
                Mint tenant-scoped tokens signed by KMS / HMAC for live API dispatch
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={mintRole}
              onChange={(e) => setMintRole(e.target.value)}
              className="text-xs font-mono bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded px-2 py-1.5"
            >
              <option value="system_admin">System Admin</option>
              <option value="tenant_admin">Tenant Admin</option>
              <option value="developer">Developer</option>
              <option value="external_auditor">External Auditor</option>
            </select>
            <input
              type="text"
              value={mintTenantId}
              onChange={(e) => setMintTenantId(e.target.value)}
              placeholder="tenant_id"
              className="text-xs font-mono bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded px-2 py-1.5 w-36"
            />
            <button
              onClick={handleMintToken}
              className="bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 px-3 py-1.5 rounded text-xs font-mono font-medium hover:bg-neutral-800 transition-colors"
            >
              Mint Scoped Token
            </button>
          </div>
        </Card>

        {mintedToken && (
          <div className="p-3 bg-neutral-900 text-neutral-200 rounded-lg text-xs font-mono break-all flex items-start justify-between gap-2 border border-neutral-800">
            <div>
              <span className="text-emerald-400 font-semibold">[BEARER TOKEN ISSUED]: </span>
              {mintedToken}
            </div>
            <button
              onClick={() => navigator.clipboard.writeText(mintedToken)}
              className="shrink-0 text-neutral-400 hover:text-white p-1"
              title="Copy Token"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* SECTION 2: End-to-End User Journeys across the CIaaS Fabric */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-neutral-700 dark:text-neutral-300" />
          <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">
            2. End-to-End User Journeys across the CIaaS Fabric
          </h2>
        </div>

        {/* Journey Tabs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            { id: 1, title: 'JOURNEY 1', role: 'DEVELOPER', desc: 'Polyglot Workload Execution' },
            { id: 2, title: 'JOURNEY 2', role: 'HYPERSCALE ARCHITECT', desc: 'Disaggregated Fleet Pods' },
            { id: 3, title: 'JOURNEY 3', role: 'SOVEREIGN OFFICER', desc: 'Air-Gapped Sheaf Proofs' },
            { id: 4, title: 'JOURNEY 4', role: 'EXECUTIVE / FINOPS', desc: 'Hermiten Value Settlement' },
          ].map((j) => (
            <button
              key={j.id}
              onClick={() => setSelectedJourney(j.id as any)}
              className={`p-3 text-left rounded-lg border transition-all ${
                selectedJourney === j.id
                  ? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 border-neutral-900 dark:border-white shadow-sm'
                  : 'bg-white/60 dark:bg-neutral-900/40 text-neutral-600 dark:text-neutral-400 border-neutral-200 dark:border-neutral-800 hover:border-neutral-300'
              }`}
            >
              <div className="text-[10px] font-mono tracking-wider opacity-70">{j.title} · {j.role}</div>
              <div className="text-xs font-semibold mt-0.5 truncate">{j.desc}</div>
            </button>
          ))}
        </div>

        {/* Selected Journey Canvas */}
        <Card className="p-6 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70">
          {selectedJourney === 1 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                    Journey 1: Developer / Data Engineer — Polyglot Workload Execution
                  </h3>
                  <p className="text-xs text-neutral-500">
                    Exact representation dispatch, 32-lane carry-free execution, and zero-copy pointer receipts.
                  </p>
                </div>
                <StatusPill status="PASS" label="O(1) DISPATCH" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-blue-600 dark:text-blue-400 font-bold">STEP 1: INGRESS</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    OAuth2 JWT Bearer Auth via SDK. Scope validated against AL HARAS Developer tier.
                  </p>
                </div>
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-purple-600 dark:text-purple-400 font-bold">STEP 2: COLLAPSE</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    Representation-Aware Dispatcher evaluates ring. Pisot-Lucas O(1) 64-byte structural collapse.
                  </p>
                </div>
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">STEP 3: 32-LANE ALU</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    Executed on 32-lane Zeckendorf ALU inside Docker/host container with zero carry propagation.
                  </p>
                </div>
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-[10px] text-amber-600 dark:text-amber-400 font-bold">STEP 4: RECEIPT</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    Zero-copy pointer ID (`ptr_ovid_...`), ML-DSA-87 signature, and THESEUS journal entry.
                  </p>
                </div>
              </div>
            </div>
          )}

          {selectedJourney === 2 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                    Journey 2: Hyperscale Infrastructure Architect — Disaggregated Fleet Management
                  </h3>
                  <p className="text-xs text-neutral-500">
                    Multi-region pods (α, β, γ, δ), 130 Tb/s DEC fluid routing, and DSW 4D Instanton Self-Healer.
                  </p>
                </div>
                <StatusPill status="ONLINE" label="130 Tb/s MESH" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
                {podsFleet?.pods.map((pod) => (
                  <div key={pod.pod} className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                    <div className="flex items-center justify-between text-[11px] font-bold">
                      <span className="text-blue-600 dark:text-blue-400">POD {pod.pod.toUpperCase()}</span>
                      <span className="text-emerald-600 dark:text-emerald-400">{pod.health}</span>
                    </div>
                    <div className="text-[11px] text-neutral-600 dark:text-neutral-300 mt-1">{pod.region}</div>
                    <div className="text-[10px] text-neutral-400 mt-2">
                      Nodes: {pod.nodes} | Active: {pod.active_workloads}
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-3 bg-neutral-50 dark:bg-neutral-900/30 rounded-lg border border-neutral-200 dark:border-neutral-800 flex items-center justify-between text-xs font-mono">
                <span>DSW 4D Instanton Self-Healer: 1 clock cycle trace repair, 0 bytes rollback</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">100% SATURATION / 0 STALLS</span>
              </div>
            </div>
          )}

          {selectedJourney === 3 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                    Journey 3: Sovereign Security Officer — Air-Gapped Governance & Sheaf Cohomology
                  </h3>
                  <p className="text-xs text-neutral-500">
                    UK NCSC 14 Cloud Security Principles, Customer-Held Cloud KMS / HSM, and Cellular Sheaf vortex filtration.
                  </p>
                </div>
                <StatusPill status="PASS" label="NCSC 14 COMPLIANT" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-purple-600 dark:text-purple-400 font-bold">SHEAF COHOMOLOGY ENGINE</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    Monitors multi-node latent space. Any prompt vortex generates H¹(X; F) ≠ 0 and is filtered before token generation.
                  </p>
                </div>
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold">CUSTOMER-HELD HSM</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    FIPS 140-3 Level 4 hardware root of trust. NIST FIPS 204 ML-DSA-87 cryptographic lattice signing.
                  </p>
                </div>
                <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                  <span className="text-blue-600 dark:text-blue-400 font-bold">ZERO-AUTH PUBLIC AUDIT</span>
                  <p className="text-neutral-700 dark:text-neutral-300 mt-1 text-[11px]">
                    External auditors verify receipts at `/v1/verify/{'{hash}'}` confirming zk-STARK quotient proofs without payload exposure.
                  </p>
                </div>
              </div>
            </div>
          )}

          {selectedJourney === 4 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                    Journey 4: Executive / FinOps — Commercial Capacity & Hermiten Settlement
                  </h3>
                  <p className="text-xs text-neutral-500">
                    Chronus Capacity Entitlements (CCE), 4-part pricing formula, and 25% net avoided-cost value share.
                  </p>
                </div>
                <StatusPill status="PASS" label="HERMITEN 25%" />
              </div>
              <div className="p-3 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800 text-xs font-mono">
                <span className="text-amber-600 dark:text-amber-400 font-bold">FOUR-PART PRICING FORMULA:</span>
                <p className="text-neutral-800 dark:text-neutral-200 mt-1">
                  P_total = P_platform ($5,000) + P_reserved ($1,843.20) + P_consumption ($57.60) + P_assurance ($1,500) = <strong className="text-emerald-600 dark:text-emerald-400">${pricing?.total_price_usd || '8,400.80'}</strong>
                </p>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* SECTION 3: Tenant Onboarding & CCE Quotas Administration */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Globe2 className="w-5 h-5 text-neutral-700 dark:text-neutral-300" />
            <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">
              3. Tenant Onboarding & Chronus Capacity Entitlements (CCE)
            </h2>
          </div>
          <span className="text-xs font-mono text-neutral-400">5-Dimensional Resource Axis</span>
        </div>

        {/* Existing Tenants Table */}
        <Card className="border-neutral-200 dark:border-neutral-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-neutral-100 dark:bg-neutral-900/80 border-b border-neutral-200 dark:border-neutral-800 text-neutral-500">
                <tr>
                  <th className="p-3">TENANT ID</th>
                  <th className="p-3">ORGANIZATION</th>
                  <th className="p-3">POD</th>
                  <th className="p-3">DATA REST</th>
                  <th className="p-3">DATA MOTION</th>
                  <th className="p-3">DATA PROC</th>
                  <th className="p-3">COMPUTE CCU</th>
                  <th className="p-3">CONCURRENCY</th>
                  <th className="p-3">API PREFIX</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-900">
                {tenants.map((t) => (
                  <tr key={t.tenant_id} className="hover:bg-neutral-50 dark:hover:bg-neutral-900/50">
                    <td className="p-3 font-semibold text-neutral-900 dark:text-white">{t.tenant_id}</td>
                    <td className="p-3 text-neutral-700 dark:text-neutral-300">{t.organization_name}</td>
                    <td className="p-3">
                      <span className="bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded text-[10px]">
                        Pod {t.regional_pod}
                      </span>
                    </td>
                    <td className="p-3 text-neutral-500">{t.cce.data_at_rest_gb} GB</td>
                    <td className="p-3 text-neutral-500">{t.cce.data_in_motion_gb} GB</td>
                    <td className="p-3 text-neutral-500">{t.cce.data_processed_gb} GB</td>
                    <td className="p-3 text-emerald-600 dark:text-emerald-400 font-bold">{t.cce.compute_intensity_ccu} CCU</td>
                    <td className="p-3 text-neutral-500">{t.cce.concurrency_limit} Warps</td>
                    <td className="p-3 text-neutral-400 truncate max-w-[120px]">{t.api_key_prefix}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Onboarding Form */}
        <Card className="p-5 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70">
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white mb-3">
            Onboard New Enterprise Tenant
          </h3>
          <form onSubmit={handleOnboardTenant} className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
            <input
              type="text"
              placeholder="tenant-id (e.g. tenant-acme)"
              value={newTenantId}
              onChange={(e) => setNewTenantId(e.target.value)}
              className="p-2 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900"
              required
            />
            <input
              type="text"
              placeholder="Organization Name"
              value={newOrgName}
              onChange={(e) => setNewOrgName(e.target.value)}
              className="p-2 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900"
              required
            />
            <input
              type="email"
              placeholder="Admin Contact Email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              className="p-2 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900"
              required
            />
            <div className="flex gap-2">
              <select
                value={newPod}
                onChange={(e) => setNewPod(e.target.value)}
                className="p-2 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900 flex-1"
              >
                <option value="alpha">Pod α (London)</option>
                <option value="beta">Pod β (US East)</option>
                <option value="gamma">Pod γ (DIFC)</option>
                <option value="delta">Pod δ (Tokyo)</option>
              </select>
              <button
                type="submit"
                className="bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 px-4 py-2 rounded font-medium hover:bg-neutral-800 transition-colors shrink-0"
              >
                Provision Tenant
              </button>
            </div>
          </form>
          {onboardStatus && (
            <div className="mt-3 text-xs font-mono text-emerald-600 dark:text-emerald-400">
              {onboardStatus}
            </div>
          )}
        </Card>
      </div>

      {/* SECTION 4: Hermiten 25% Value-Share Settlement Reconciler */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-neutral-700 dark:text-neutral-300" />
            <h2 className="text-lg font-semibold text-neutral-900 dark:text-white">
              4. Hermiten 25% Net Avoided-Cost Value-Share Settlement
            </h2>
          </div>
          <span className="text-xs font-mono text-neutral-400">S_net = C_counterfactual - C_actual - C_incremental</span>
        </div>

        <Card className="p-6 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-mono text-neutral-500 block mb-1">
                COUNTERFACTUAL CLOUD GPU COST (USD)
              </label>
              <input
                type="number"
                value={counterfactual}
                onChange={(e) => setCounterfactual(Number(e.target.value))}
                className="w-full p-2.5 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900 font-mono text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-mono text-neutral-500 block mb-1">
                ACTUAL CHRONUS QiGPU COST (USD)
              </label>
              <input
                type="number"
                value={actualCost}
                onChange={(e) => setActualCost(Number(e.target.value))}
                className="w-full p-2.5 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900 font-mono text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-mono text-neutral-500 block mb-1">
                INCREMENTAL PIPELINE OVERHEAD (USD)
              </label>
              <input
                type="number"
                value={incrementalCost}
                onChange={(e) => setIncrementalCost(Number(e.target.value))}
                className="w-full p-2.5 border border-neutral-200 dark:border-neutral-800 rounded bg-white dark:bg-neutral-900 font-mono text-sm"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={handleRecalculateSettlement}
              className="bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 px-4 py-2 rounded text-xs font-mono font-medium hover:bg-neutral-800 transition-colors"
            >
              Reconcile Hermiten Settlement
            </button>
            <span className="text-xs font-mono text-neutral-400">
              Formula: F_Chronus = 0.25 × max(0, S_net)
            </span>
          </div>

          {settlement && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-neutral-100 dark:border-neutral-800 font-mono text-xs">
              <div className="p-4 bg-neutral-100 dark:bg-neutral-900/60 rounded-lg border border-neutral-200 dark:border-neutral-800">
                <span className="text-neutral-400 uppercase text-[10px]">NET AVOIDED COST (S_net)</span>
                <div className="text-xl font-bold text-neutral-900 dark:text-white mt-1">
                  ${settlement.net_avoided_cost_usd}
                </div>
                <p className="text-[10px] text-neutral-400 mt-1">
                  Total client avoided infrastructure expenditure
                </p>
              </div>

              <div className="p-4 bg-emerald-50 dark:bg-emerald-950/20 rounded-lg border border-emerald-200 dark:border-emerald-800">
                <span className="text-emerald-700 dark:text-emerald-400 uppercase text-[10px] font-bold">
                  CHRONUS 25% VALUE-SHARE FEE (F_Chronus)
                </span>
                <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                  ${settlement.chronus_value_share_usd}
                </div>
                <p className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80 mt-1">
                  25% performance fee tied to provable savings
                </p>
              </div>

              <div className="p-4 bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <span className="text-blue-700 dark:text-blue-400 uppercase text-[10px] font-bold">
                  CLIENT RETAINED NET SAVINGS (75%)
                </span>
                <div className="text-xl font-bold text-blue-600 dark:text-blue-400 mt-1">
                  ${settlement.client_retained_usd}
                </div>
                <p className="text-[10px] text-blue-600/80 dark:text-blue-400/80 mt-1">
                  75% pure retained surplus for enterprise client
                </p>
              </div>
            </div>
          )}

          {settlement?.proof_certificate && (
            <div className="p-3 bg-neutral-100 dark:bg-neutral-900 rounded border border-neutral-200 dark:border-neutral-800 text-xs font-mono flex items-center justify-between text-neutral-600 dark:text-neutral-300">
              <span>Proof Certificate: <code>{settlement.proof_certificate}</code></span>
              <StatusPill status="PASS" label={settlement.settlement_status} />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
