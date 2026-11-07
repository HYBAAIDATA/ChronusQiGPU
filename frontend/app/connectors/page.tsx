'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Binary,
  CheckCircle2,
  ChevronDown,
  Database,
  FileCode2,
  HardDrive,
  Link2,
  Lock,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import {
  ChronusAPIClient,
  ConnectorSpecsResponse,
  DataMovementPlaneSpec,
  DiscoveredDatasetItem,
  PointerExecutionResponse,
  PrebuiltConnectorSpec,
  RegisteredConnectorItem,
  ZeroCopyAccessClass,
  ZeroCopyConnectorType,
  ZeroCopyIngestFormat,
  ZeroCopyIngestResponse,
} from '@/lib/api-client';

const CONNECTOR_OPTIONS: Array<{
  value: ZeroCopyConnectorType;
  label: string;
  group: string;
  sampleUri: string;
}> = [
  {
    value: 'AWS_S3',
    label: 'AWS S3 (Cloud Object Store)',
    group: 'Cloud Object Stores',
    sampleUri: 's3://enterprise-quant-lake-eu-west-2/curated/orders/',
  },
  {
    value: 'AZURE_BLOB',
    label: 'Azure Blob / ADLS Gen2 (Cloud Object Store)',
    group: 'Cloud Object Stores',
    sampleUri: 'abfss://curated@enterprisedatalake.dfs.core.windows.net/ledger/',
  },
  {
    value: 'GCP_GCS',
    label: 'Google Cloud Storage (Cloud Object Store)',
    group: 'Cloud Object Stores',
    sampleUri: 'gs://enterprise-sovereign-bucket-eu/parquet-events/',
  },
  {
    value: 'SNOWFLAKE',
    label: 'Snowflake (Enterprise Data Warehouse)',
    group: 'Enterprise Data Warehouses',
    sampleUri: 'snowflake://acme_finops.eu-west-2/CORE_DW/SETTLEMENT',
  },
  {
    value: 'DATABRICKS',
    label: 'Databricks Unity Catalog (Enterprise Data Warehouse)',
    group: 'Enterprise Data Warehouses',
    sampleUri: 'databricks://adb-sovereign-01/main_catalog/risk_delta',
  },
  {
    value: 'BIGQUERY',
    label: 'Google BigQuery (Enterprise Data Warehouse)',
    group: 'Enterprise Data Warehouses',
    sampleUri: 'bigquery://enterprise-prod-01/treasury_analytics',
  },
  {
    value: 'POSTGRESQL',
    label: 'PostgreSQL (Legacy On-Premises)',
    group: 'Legacy On-Premises Storage',
    sampleUri: 'postgresql://pg-core.internal:5432/clearing_house',
  },
  {
    value: 'SAN',
    label: 'Co-Located NVMe-oF SAN (Legacy On-Premises)',
    group: 'Legacy On-Premises Storage',
    sampleUri: 'san://nvme-rack-ldn-04/ns-zero-copy-01',
  },
  {
    value: 'HDFS',
    label: 'Apache HDFS (Legacy On-Premises)',
    group: 'Legacy On-Premises Storage',
    sampleUri: 'hdfs://namenode.dc1.internal:8020/data/historical_ticks',
  },
];

const SAMPLE_INGEST_PAYLOADS: Record<
  ZeroCopyIngestFormat,
  { objectPath: string; payloadText: string; desc: string }
> = {
  PARQUET: {
    objectPath: 'part-00042-trades.parquet',
    payloadText: 'PAR1' + 'CHRONUS_COLUMNAR_PAGE_ROWGROUP_EXACT_Q5_'.repeat(32) + 'PAR1',
    desc: 'Columnar Apache Parquet RowGroup with PAR1 magic header/footer',
  },
  DELTA_LAKE: {
    objectPath: 'positions/_delta_log/00000000000000000012.json',
    payloadText: JSON.stringify({
      protocol: { minReaderVersion: 1, minWriterVersion: 2 },
      metaData: {
        id: 'delta-ledger-01',
        schemaString: JSON.stringify({
          fields: [
            { name: 'position_id', type: 'long' },
            { name: 'notional_q5', type: 'decimal' },
            { name: 'book_code', type: 'string' },
          ],
        }),
      },
    }),
    desc: 'Delta Lake transaction log protocol & schema descriptor',
  },
  ORC: {
    objectPath: 'stripe-risk-000.orc',
    payloadText: 'ORC' + 'STRIPE_FOOTER_INDEX_ZECKENDORF_'.repeat(32),
    desc: 'Apache ORC stripe stream with ORC magic header',
  },
  GZIP: {
    objectPath: 'archive-2026-q4.json.gz',
    payloadText: '{"batch":108,"compression":"gzip_stream","exact_ring":"Q(sqrt(5))"}'.repeat(20),
    desc: 'Compressed telemetry stream folded into Pisot-Lucas L_n state',
  },
  JSON: {
    objectPath: 'events/settlement_feed.ndjson',
    payloadText: JSON.stringify({
      event_id: 90421,
      counterparty: 'SOVEREIGN_CLEARING_LDN',
      settled_cents: 482500000,
      verified: true,
    }).repeat(16),
    desc: 'Structured JSON / NDJSON operational record stream',
  },
  RAW_BINARY: {
    objectPath: 'nvme_lba_extent_0008.bin',
    payloadText: 'BIN_EXTENT_64B_ALIGNED_FRAME_0001_'.repeat(32),
    desc: 'Raw binary host NVMe / SAN block stream',
  },
};

export default function ZeroCopyConnectorsPage() {
  const [specsData, setSpecsData] = useState<ConnectorSpecsResponse | null>(null);
  const [connectors, setConnectors] = useState<RegisteredConnectorItem[]>([]);
  const [datasets, setDatasets] = useState<DiscoveredDatasetItem[]>([]);
  const [activePointersCount, setActivePointersCount] = useState<number>(0);

  // Day-1 Connector Binding Form State
  const [tenantId, setTenantId] = useState('tenant-default');
  const [connectorName, setConnectorName] = useState('Snowflake Global Treasury Zero-Copy');
  const [connectorType, setConnectorType] = useState<ZeroCopyConnectorType>('SNOWFLAKE');
  const [endpointUri, setEndpointUri] = useState(
    'snowflake://acme_finops.eu-west-2/CORE_DW/SETTLEMENT'
  );
  const [sourceRegion, setSourceRegion] = useState('eu-west-2');
  const [podRegion, setPodRegion] = useState('eu-west-2');
  const [kmsProvider, setKmsProvider] = useState('AWS_KMS');
  const [kmsKeyArn, setKmsKeyArn] = useState(
    'arn:aws:kms:eu-west-2:000000000001:key/chronus-ref-root'
  );
  const [coLocated, setCoLocated] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [bindFeedback, setBindFeedback] = useState<string | null>(null);

  // Interactive Binet-Zeckendorf Ingress & Pointer Execution State
  const [selectedConnectorId, setSelectedConnectorId] = useState<string>('');
  const [selectedFormat, setSelectedFormat] = useState<ZeroCopyIngestFormat>('PARQUET');
  const [objectPath, setObjectPath] = useState(SAMPLE_INGEST_PAYLOADS.PARQUET.objectPath);
  const [ingestPayloadText, setIngestPayloadText] = useState(
    SAMPLE_INGEST_PAYLOADS.PARQUET.payloadText
  );
  const [encryptWithKms, setEncryptWithKms] = useState(true);
  const [simulateAdversarial, setSimulateAdversarial] = useState(false);
  const [ingestResult, setIngestResult] = useState<ZeroCopyIngestResponse | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // Pointer Execution State
  const [pointerIdInput, setPointerIdInput] = useState<string>('');
  const [pointerOp, setPointerOp] = useState<string>('PV_LATTICE_FOLD');
  const [scaleOrder, setScaleOrder] = useState<number>(12);
  const [pointerExecResult, setPointerExecResult] = useState<PointerExecutionResponse | null>(null);
  const [pointerExecError, setPointerExecError] = useState<string | null>(null);

  // Automated Schema Discovery Middleware State
  const [newTableToDiscover, setNewTableToDiscover] = useState('TREASURY_INTRADAY_POSITIONS');
  const [discoveryStatus, setDiscoveryStatus] = useState<string | null>(null);

  useEffect(() => {
    async function loadAll() {
      const [specs, connRes, catalogRes] = await Promise.all([
        ChronusAPIClient.getConnectorSpecs(),
        ChronusAPIClient.getConnectors(),
        ChronusAPIClient.getDiscoveredCatalog(),
      ]);
      setSpecsData(specs);
      setConnectors(connRes.connectors);
      setActivePointersCount(connRes.active_pointers);
      setDatasets(catalogRes.datasets);
      if (connRes.connectors.length > 0) {
        setSelectedConnectorId(connRes.connectors[0].connector_id);
      }
      if (catalogRes.datasets.length > 0) {
        setPointerIdInput(catalogRes.datasets[0].pointer_id);
      }
    }
    loadAll();
  }, []);

  const validateField = (field: string, value: string): string => {
    const trimmed = value.trim();
    if (field === 'tenantId' && trimmed.length < 2) {
      return 'Enter a valid tenant identifier (at least 2 characters).';
    }
    if (field === 'connectorName' && trimmed.length < 3) {
      return 'Provide a descriptive connector name (at least 3 characters).';
    }
    if (field === 'endpointUri' && !trimmed.includes('://')) {
      return 'Endpoint URI must include scheme (e.g., s3://, snowflake://, san://).';
    }
    return '';
  };

  const handleFieldBlur = (field: string, value: string) => {
    const err = validateField(field, value);
    if (err) {
      setFormErrors((prev) => ({ ...prev, [field]: err }));
    }
  };

  const clearFieldError = (field: string) => {
    if (formErrors[field]) {
      setFormErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const handleConnectorTypeChange = (nextType: ZeroCopyConnectorType) => {
    setConnectorType(nextType);
    const preset = CONNECTOR_OPTIONS.find((opt) => opt.value === nextType);
    if (preset) {
      setEndpointUri(preset.sampleUri);
      setConnectorName(`${nextType.replace('_', ' ')} Zero-Copy Binding`);
      clearFieldError('endpointUri');
    }
    if (nextType === 'SAN') {
      setCoLocated(true);
      setKmsProvider('PKCS11_HSM');
    }
  };

  const handleBindConnector = async (e: React.FormEvent) => {
    e.preventDefault();
    const nextErrors: Record<string, string> = {};
    const tErr = validateField('tenantId', tenantId);
    const nErr = validateField('connectorName', connectorName);
    const uErr = validateField('endpointUri', endpointUri);
    if (tErr) nextErrors.tenantId = tErr;
    if (nErr) nextErrors.connectorName = nErr;
    if (uErr) nextErrors.endpointUri = uErr;

    if (Object.keys(nextErrors).length > 0) {
      setFormErrors(nextErrors);
      return;
    }

    const created = await ChronusAPIClient.registerConnector({
      tenant_id: tenantId.trim(),
      name: connectorName.trim(),
      connector_type: connectorType,
      endpoint_uri: endpointUri.trim(),
      source_region: sourceRegion.trim(),
      pod_region: podRegion.trim(),
      kms_provider: kmsProvider,
      kms_key_arn: kmsKeyArn.trim() || undefined,
      co_located: coLocated,
      auto_discover: true,
    });

    const [connRes, catRes] = await Promise.all([
      ChronusAPIClient.getConnectors(),
      ChronusAPIClient.getDiscoveredCatalog(),
    ]);
    setConnectors(connRes.connectors);
    setActivePointersCount(connRes.active_pointers);
    setDatasets(catRes.datasets);
    setSelectedConnectorId(created.connector_id);
    setBindFeedback(
      `Bound ${created.name} (${created.access_class}) under ECA ${created.eca_id} — 0 bytes migrated.`
    );
  };

  const handleFormatPresetSelect = (fmt: ZeroCopyIngestFormat) => {
    setSelectedFormat(fmt);
    setObjectPath(SAMPLE_INGEST_PAYLOADS[fmt].objectPath);
    setIngestPayloadText(SAMPLE_INGEST_PAYLOADS[fmt].payloadText);
    setIngestError(null);
  };

  const handleRunIngest = async () => {
    if (!selectedConnectorId) return;
    setIngestError(null);
    try {
      const res = await ChronusAPIClient.ingestConnectorBlock(selectedConnectorId, {
        payload_text: ingestPayloadText,
        object_path: objectPath,
        format_hint: selectedFormat,
        encrypt_with_customer_kms: encryptWithKms,
        simulate_adversarial: simulateAdversarial,
      });
      setIngestResult(res);
      setPointerIdInput(res.pointer.pointer_id);
      setActivePointersCount((prev) => prev + 1);
    } catch (err: any) {
      setIngestResult(null);
      setIngestError(err?.message || 'AL HARAS blocked connector ingress');
    }
  };

  const handleExecutePointer = async () => {
    if (!pointerIdInput.trim().startsWith('ptr_ovid_')) {
      setPointerExecError('Enter a valid content-addressed ptr_ovid_<hash> pointer.');
      return;
    }
    setPointerExecError(null);
    try {
      const res = await ChronusAPIClient.executeZeroCopyPointer(pointerIdInput.trim(), {
        operation: pointerOp,
        scale_order: scaleOrder,
        metallic_m: 1,
      });
      setPointerExecResult(res);
    } catch (err: any) {
      setPointerExecError(err?.message || 'Pointer execution failed');
    }
  };

  const handleRunSchemaDiscovery = async () => {
    if (!selectedConnectorId) return;
    const extra = newTableToDiscover.trim() ? [newTableToDiscover.trim()] : undefined;
    const res = await ChronusAPIClient.discoverConnectorSchemas(selectedConnectorId, extra);
    const cat = await ChronusAPIClient.getDiscoveredCatalog();
    setDatasets(cat.datasets);
    setDiscoveryStatus(
      `ECA Schema Discovery indexed ${res.newly_indexed_count} new dataset(s) (${res.total_indexed_datasets} total on connector).`
    );
  };

  const planeList: DataMovementPlaneSpec[] = specsData
    ? Object.values(specsData.data_movement_plane)
    : [];
  const prebuiltList: PrebuiltConnectorSpec[] = specsData
    ? Object.values(specsData.prebuilt_connectors)
    : [];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* Executive Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono font-medium text-neutral-400">
              08 // ZERO-ETL DATA INGRESS &amp; T3–T5 MOVEMENT PLANE
            </span>
            <span className="text-neutral-300 dark:text-neutral-700">·</span>
            <span className="text-xs font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
              DATA STAYS AT REST
            </span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 dark:text-white">
            Zero-Copy Native Representation Connectors
          </h1>
          <p className="text-sm text-neutral-500 mt-1 max-w-3xl">
            Bind Chronus CIaaS directly to enterprise data at rest across AWS S3, Azure Blob, GCP
            GCS, Snowflake, Databricks, BigQuery, PostgreSQL, SAN, and HDFS — zero custom ETL
            pipelines, zero bulk staging copies, and zero cloud egress invoices.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill status="PASS" label="ZERO EGRESS ($0.00)" />
          <Link
            href="/ciaas"
            className="inline-flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-700 dark:text-neutral-200 hover:border-neutral-400 transition-colors"
          >
            ECA Governance <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
          </Link>
        </div>
      </div>

      {/* 4 Core Engineering Primitives KPI Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 bg-white/70 dark:bg-neutral-900/50 border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>1. ZERO-COPY POINTERS</span>
            <Link2 className="w-4 h-4 text-blue-500" aria-hidden="true" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white font-mono">
            {activePointersCount} <span className="text-xs font-normal text-blue-500">ptr_ovid_*</span>
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            0 B bulk staging · Data stays at rest
          </div>
        </Card>

        <Card className="p-4 bg-white/70 dark:bg-neutral-900/50 border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>2. BINET-ZECKENDORF FOLD</span>
            <Binary className="w-4 h-4 text-purple-500" aria-hidden="true" />
          </div>
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400 font-mono">
            Up to 99.9%
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            Exact Q(√5) &amp; Pisot-Lucas L_n fidelity
          </div>
        </Card>

        <Card className="p-4 bg-white/70 dark:bg-neutral-900/50 border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>3. T3–T5 MOVEMENT PLANE</span>
            <Activity className="w-4 h-4 text-emerald-500" aria-hidden="true" />
          </div>
          <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 font-mono">
            0 Stalls / 100%
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            1-cycle NVMe mmap &amp; DEC Lie-Poisson stream
          </div>
        </Card>

        <Card className="p-4 bg-white/70 dark:bg-neutral-900/50 border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-xs font-mono text-neutral-500 mb-2">
            <span>4. AL HARAS + KMS CUSTODY</span>
            <ShieldCheck className="w-4 h-4 text-amber-500" aria-hidden="true" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white font-mono">
            H¹(X; F) = 0
          </div>
          <div className="text-xs text-neutral-400 mt-1 font-mono">
            Cloud KMS / PKCS#11 RAM-only decrypt
          </div>
        </Card>
      </div>

      {/* SECTION 1: Explicit Memory Access Classes (T3-T5 Data Movement Plane) */}
      <section aria-labelledby="movement-plane-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-neutral-700 dark:text-neutral-300" aria-hidden="true" />
            <h2
              id="movement-plane-heading"
              className="text-lg font-semibold text-neutral-900 dark:text-white"
            >
              1. Explicit Memory Access Classes (T3–T5 Data Movement Plane)
            </h2>
          </div>
          <span className="text-xs font-mono text-neutral-400">
            Zero Network Bottlenecks · Zero Bulk Staging
          </span>
        </div>

        <Card className="border-neutral-200 dark:border-neutral-800 overflow-hidden bg-white/70 dark:bg-neutral-950/70">
          <div
            className="chronus-table-region"
            tabIndex={0}
            role="region"
            aria-labelledby="movement-plane-heading"
          >
            <table className="chronus-data-table text-xs font-mono">
              <caption className="px-4 py-2.5 text-[11px] text-neutral-500 border-b border-neutral-200 dark:border-neutral-800">
                Operational classification of external enterprise storage topologies across T3–T5
                memory planes.
              </caption>
              <thead className="bg-neutral-100 dark:bg-neutral-900 text-neutral-600 dark:text-neutral-300 border-b border-neutral-200 dark:border-neutral-800">
                <tr>
                  <th scope="col" className="p-3 text-left">
                    ACCESS CLASS
                  </th>
                  <th scope="col" className="p-3 text-left">
                    TIER
                  </th>
                  <th scope="col" className="p-3 text-left">
                    STORAGE TOPOLOGY
                  </th>
                  <th scope="col" className="p-3 text-left">
                    EXECUTION &amp; ROUTING STRATEGY
                  </th>
                  <th scope="col" className="p-3 text-left">
                    BUS / STALLS
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-900">
                {planeList.map((plane) => (
                  <tr
                    key={plane.access_class}
                    className="hover:bg-neutral-50 dark:hover:bg-neutral-900/40"
                  >
                    <th
                      scope="row"
                      className="p-3 text-left font-semibold text-blue-600 dark:text-blue-400 whitespace-nowrap"
                    >
                      {plane.access_class}
                    </th>
                    <td data-label="Tier" className="p-3 text-neutral-700 dark:text-neutral-300">
                      {plane.plane_tier}
                    </td>
                    <td
                      data-label="Storage Topology"
                      className="p-3 text-neutral-700 dark:text-neutral-300"
                    >
                      {plane.storage_topology}
                    </td>
                    <td
                      data-label="Execution Strategy"
                      className="p-3 text-neutral-600 dark:text-neutral-400"
                    >
                      {plane.execution_routing_strategy}
                    </td>
                    <td
                      data-label="Bus / Stalls"
                      className="p-3 text-emerald-600 dark:text-emerald-400 font-semibold whitespace-nowrap"
                    >
                      {plane.bus_saturation_pct}% / {plane.packet_stalls} stalls
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* SECTION 2: Day-1 Zero-Copy Connector Binding & Active Connectors Table */}
      <section aria-labelledby="day1-binding-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-neutral-700 dark:text-neutral-300" aria-hidden="true" />
            <h2
              id="day1-binding-heading"
              className="text-lg font-semibold text-neutral-900 dark:text-white"
            >
              2. Day-1 Zero-Copy Connector Binding &amp; ECA Schema Catalog
            </h2>
          </div>
          <span className="text-xs font-mono text-neutral-400">
            Connect S3, Snowflake, or On-Premises in Minutes
          </span>
        </div>

        <Card className="p-6 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70">
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-white mb-4">
            Bind External Storage Source (Customer-Held Key Custody)
          </h3>

          <form onSubmit={handleBindConnector} noValidate className="space-y-4 text-xs font-mono">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label
                  htmlFor="conn-tenant-id"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  TENANT ID (ECA AUTHORIZED)
                </label>
                <input
                  id="conn-tenant-id"
                  name="tenant_id"
                  type="text"
                  value={tenantId}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  onChange={(e) => {
                    setTenantId(e.target.value);
                    clearFieldError('tenantId');
                  }}
                  onBlur={(e) => handleFieldBlur('tenantId', e.target.value)}
                  aria-invalid={Boolean(formErrors.tenantId)}
                  className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                />
                {formErrors.tenantId && (
                  <p className="text-[11px] text-red-500 mt-1">{formErrors.tenantId}</p>
                )}
              </div>

              <div>
                <label
                  htmlFor="conn-type"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  CONNECTOR PLATFORM
                </label>
                <select
                  id="conn-type"
                  name="connector_type"
                  value={connectorType}
                  onChange={(e) =>
                    handleConnectorTypeChange(e.target.value as ZeroCopyConnectorType)
                  }
                  className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                >
                  {CONNECTOR_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="conn-name"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  CONNECTOR DISPLAY NAME
                </label>
                <input
                  id="conn-name"
                  name="name"
                  type="text"
                  value={connectorName}
                  onChange={(e) => {
                    setConnectorName(e.target.value);
                    clearFieldError('connectorName');
                  }}
                  onBlur={(e) => handleFieldBlur('connectorName', e.target.value)}
                  aria-invalid={Boolean(formErrors.connectorName)}
                  className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                />
                {formErrors.connectorName && (
                  <p className="text-[11px] text-red-500 mt-1">{formErrors.connectorName}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <label
                  htmlFor="conn-endpoint-uri"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  AT-REST ENDPOINT URI (NO DATA REPLICATION)
                </label>
                <input
                  id="conn-endpoint-uri"
                  name="endpoint_uri"
                  type="text"
                  value={endpointUri}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  onChange={(e) => {
                    setEndpointUri(e.target.value);
                    clearFieldError('endpointUri');
                  }}
                  onBlur={(e) => handleFieldBlur('endpointUri', e.target.value)}
                  aria-invalid={Boolean(formErrors.endpointUri)}
                  className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                />
                {formErrors.endpointUri && (
                  <p className="text-[11px] text-red-500 mt-1">{formErrors.endpointUri}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label
                    htmlFor="conn-source-region"
                    className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                  >
                    DATA REGION
                  </label>
                  <input
                    id="conn-source-region"
                    name="source_region"
                    type="text"
                    value={sourceRegion}
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    onChange={(e) => setSourceRegion(e.target.value)}
                    className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                  />
                </div>
                <div>
                  <label
                    htmlFor="conn-pod-region"
                    className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                  >
                    CHRONUS POD
                  </label>
                  <input
                    id="conn-pod-region"
                    name="pod_region"
                    type="text"
                    value={podRegion}
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    onChange={(e) => setPodRegion(e.target.value)}
                    className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div>
                <label
                  htmlFor="conn-kms-provider"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  CUSTOMER KEY CUSTODY PROVIDER
                </label>
                <select
                  id="conn-kms-provider"
                  name="kms_provider"
                  value={kmsProvider}
                  onChange={(e) => setKmsProvider(e.target.value)}
                  className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                >
                  <option value="AWS_KMS">AWS Cloud KMS (CMK)</option>
                  <option value="PKCS11_HSM">Hardware Security Module (PKCS#11 HSM)</option>
                  <option value="AZURE_KEY_VAULT">Azure Key Vault Managed HSM</option>
                  <option value="GCP_KMS">Google Cloud KMS / EKM</option>
                  <option value="HASHICORP_VAULT">HashiCorp Vault Transit</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="conn-kms-arn"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  CUSTOMER KMS KEY ARN OR PKCS#11 URI
                </label>
                <input
                  id="conn-kms-arn"
                  name="kms_key_arn"
                  type="text"
                  value={kmsKeyArn}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  onChange={(e) => setKmsKeyArn(e.target.value)}
                  className="w-full p-2.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
                />
              </div>

              <div className="flex items-center justify-between gap-3">
                <label
                  htmlFor="conn-colocated"
                  className="inline-flex items-center gap-2 text-neutral-700 dark:text-neutral-300 cursor-pointer"
                >
                  <input
                    id="conn-colocated"
                    name="co_located"
                    type="checkbox"
                    checked={coLocated}
                    onChange={(e) => setCoLocated(e.target.checked)}
                    className="rounded border-neutral-300"
                  />
                  <span>Co-Located 1-Cycle SAN/NVMe</span>
                </label>

                <button
                  type="submit"
                  className="bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 px-4 py-2.5 rounded-lg font-semibold hover:opacity-90 transition-opacity shrink-0"
                >
                  Bind Zero-Copy Connector
                </button>
              </div>
            </div>
          </form>

          <div aria-live="polite" className="mt-3">
            {bindFeedback && (
              <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs font-mono text-emerald-700 dark:text-emerald-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
                <span>{bindFeedback}</span>
              </div>
            )}
          </div>
        </Card>

        {/* Automated Schema Discovery Dataset Catalog Table */}
        <Card className="border-neutral-200 dark:border-neutral-800 overflow-hidden bg-white/70 dark:bg-neutral-950/70">
          <div className="p-4 border-b border-neutral-200 dark:border-neutral-800 flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h3
                id="schema-catalog-heading"
                className="text-sm font-semibold text-neutral-900 dark:text-white"
              >
                Automated Schema Discovery Middleware Catalog (ECA Indexed)
              </h3>
              <p className="text-xs text-neutral-500">
                Tables and object prefixes automatically discovered and mapped to{' '}
                <code className="font-mono">ptr_ovid_&lt;hash&gt;</code> pointers without ETL.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono">
              <label htmlFor="discover-table-name" className="sr-only">
                New dataset or table name to index
              </label>
              <input
                id="discover-table-name"
                name="discover_table"
                type="text"
                value={newTableToDiscover}
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
                onChange={(e) => setNewTableToDiscover(e.target.value)}
                placeholder="NEW_WAREHOUSE_TABLE"
                className="px-2.5 py-1.5 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white"
              />
              <button
                type="button"
                onClick={handleRunSchemaDiscovery}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
                Auto-Index Table
              </button>
            </div>
          </div>

          <div aria-live="polite">
            {discoveryStatus && (
              <div className="px-4 py-2 bg-blue-50 dark:bg-blue-950/30 border-b border-blue-200 dark:border-blue-900 text-xs font-mono text-blue-700 dark:text-blue-300">
                {discoveryStatus}
              </div>
            )}
          </div>

          <div
            className="chronus-table-region"
            tabIndex={0}
            role="region"
            aria-labelledby="schema-catalog-heading"
          >
            <table className="chronus-data-table text-xs font-mono">
              <caption className="sr-only">
                Zero-copy datasets and tables indexed under Enduring Capacity Addendum
              </caption>
              <thead className="bg-neutral-100 dark:bg-neutral-900 text-neutral-600 dark:text-neutral-300 border-b border-neutral-200 dark:border-neutral-800">
                <tr>
                  <th scope="col" className="p-3 text-left">
                    DATASET / TABLE
                  </th>
                  <th scope="col" className="p-3 text-left">
                    FORMAT
                  </th>
                  <th scope="col" className="p-3 text-left">
                    ACCESS CLASS
                  </th>
                  <th scope="col" className="p-3 text-left">
                    ZERO-COPY OVID POINTER
                  </th>
                  <th scope="col" className="p-3 text-left">
                    COLLAPSE
                  </th>
                  <th scope="col" className="p-3 text-left">
                    ACTION
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100 dark:divide-neutral-900">
                {datasets.slice(0, 10).map((ds) => (
                  <tr
                    key={ds.dataset_id}
                    className="hover:bg-neutral-50 dark:hover:bg-neutral-900/40"
                  >
                    <th
                      scope="row"
                      className="p-3 text-left font-semibold text-neutral-900 dark:text-white"
                    >
                      <div>{ds.name}</div>
                      <div className="text-[10px] text-neutral-400 font-normal truncate max-w-xs">
                        {ds.source_uri}
                      </div>
                    </th>
                    <td data-label="Format" className="p-3">
                      <span className="px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 text-[10px]">
                        {ds.detected_format}
                      </span>
                    </td>
                    <td data-label="Access Class" className="p-3 text-blue-600 dark:text-blue-400">
                      {ds.access_class}
                    </td>
                    <td
                      data-label="OVID Pointer"
                      className="p-3 text-neutral-600 dark:text-neutral-300 max-w-[240px] truncate"
                      title={ds.pointer_id}
                    >
                      {ds.pointer_id}
                    </td>
                    <td
                      data-label="Collapse"
                      className="p-3 text-emerald-600 dark:text-emerald-400 font-semibold"
                    >
                      {ds.footprint_collapse_pct}
                    </td>
                    <td data-label="Action" className="p-3">
                      <button
                        type="button"
                        onClick={() => setPointerIdInput(ds.pointer_id)}
                        className="px-2.5 py-1 rounded border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-800 dark:text-neutral-200"
                      >
                        Select Pointer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* SECTION 3: Interactive Binet-Zeckendorf Ingress & In-Place Pointer Execution Workbench */}
      <section aria-labelledby="workbench-heading" className="space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-neutral-700 dark:text-neutral-300" aria-hidden="true" />
          <h2
            id="workbench-heading"
            className="text-lg font-semibold text-neutral-900 dark:text-white"
          >
            3. Binet-Zeckendorf Ingress &amp; In-Place OVID Pointer Execution Workbench
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Format-Agnostic Structural Ingestion + AL HARAS Edge */}
          <Card className="p-6 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                  Format-Agnostic Binet-Zeckendorf Ingress
                </h3>
                <p className="text-xs text-neutral-500">
                  Folds raw bytes into Q(√5) &amp; Pisot-Lucas L_n under AL HARAS H¹(X; F) security
                </p>
              </div>
              <Lock className="w-4 h-4 text-emerald-500" aria-hidden="true" />
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div>
                <label
                  htmlFor="ingest-connector-select"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  BOUND CONNECTOR
                </label>
                <select
                  id="ingest-connector-select"
                  name="ingest_connector"
                  value={selectedConnectorId}
                  onChange={(e) => setSelectedConnectorId(e.target.value)}
                  className="w-full p-2 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900"
                >
                  {connectors.map((c) => (
                    <option key={c.connector_id} value={c.connector_id}>
                      {c.name} [{c.connector_type} · {c.access_class}]
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <span className="block text-[11px] text-neutral-500 mb-1 font-semibold">
                  AUTO-INGEST PAYLOAD FORMAT PRESET
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {(
                    ['PARQUET', 'DELTA_LAKE', 'ORC', 'GZIP', 'JSON', 'RAW_BINARY'] as const
                  ).map((fmt) => (
                    <button
                      key={fmt}
                      type="button"
                      onClick={() => handleFormatPresetSelect(fmt)}
                      className={`px-2.5 py-1 rounded text-[11px] border transition-colors ${
                        selectedFormat === fmt
                          ? 'bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 border-neutral-900 dark:border-white font-semibold'
                          : 'bg-neutral-100 dark:bg-neutral-900 text-neutral-600 dark:text-neutral-400 border-neutral-200 dark:border-neutral-800'
                      }`}
                    >
                      {fmt}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label
                  htmlFor="ingest-object-path"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  EXTERNAL OBJECT / PARTITION PATH
                </label>
                <input
                  id="ingest-object-path"
                  name="object_path"
                  type="text"
                  value={objectPath}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  onChange={(e) => setObjectPath(e.target.value)}
                  className="w-full p-2 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900"
                />
              </div>

              <div className="flex flex-wrap items-center gap-4 pt-1">
                <label
                  htmlFor="ingest-kms-toggle"
                  className="inline-flex items-center gap-2 cursor-pointer text-neutral-700 dark:text-neutral-300"
                >
                  <input
                    id="ingest-kms-toggle"
                    name="encrypt_kms"
                    type="checkbox"
                    checked={encryptWithKms}
                    onChange={(e) => setEncryptWithKms(e.target.checked)}
                  />
                  <span>Customer KMS/PKCS#11 RAM Decrypt</span>
                </label>

                <label
                  htmlFor="ingest-adv-toggle"
                  className="inline-flex items-center gap-2 cursor-pointer text-amber-700 dark:text-amber-400"
                >
                  <input
                    id="ingest-adv-toggle"
                    name="simulate_adversarial"
                    type="checkbox"
                    checked={simulateAdversarial}
                    onChange={(e) => setSimulateAdversarial(e.target.checked)}
                  />
                  <span>Simulate H¹(X; F) ≠ 0 Injection</span>
                </label>
              </div>

              <button
                type="button"
                onClick={handleRunIngest}
                className="w-full py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-semibold transition-colors"
              >
                Fold &amp; Mint Zero-Copy Pointer (ptr_ovid_...)
              </button>
            </div>

            <div aria-live="polite">
              {ingestError && (
                <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-300 dark:border-red-800 text-xs font-mono text-red-700 dark:text-red-300 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <div>
                    <div className="font-bold">AL HARAS ZERO-TRUST EDGE BLOCKED INGRESS</div>
                    <div className="mt-0.5">{ingestError}</div>
                  </div>
                </div>
              )}

              {ingestResult && (
                <div className="p-4 rounded-lg bg-neutral-950 text-neutral-200 border border-neutral-800 text-[11px] font-mono space-y-1.5">
                  <div className="text-emerald-400 font-semibold">
                    ✓ ZERO-COPY POINTER MINTED · 100% EXACT ROUND-TRIP VERIFIED
                  </div>
                  <div className="truncate">
                    <span className="text-neutral-400">Pointer: </span>
                    <span className="text-blue-400">{ingestResult.pointer.pointer_id}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div>
                      <span className="text-neutral-400">Format: </span>
                      {ingestResult.algebraic_ingestion.detected_format}
                    </div>
                    <div>
                      <span className="text-neutral-400">Collapse: </span>
                      <span className="text-purple-400 font-semibold">
                        {ingestResult.algebraic_ingestion.footprint_collapse_pct}
                      </span>{' '}
                      ({ingestResult.algebraic_ingestion.raw_size_bytes}B →{' '}
                      {ingestResult.algebraic_ingestion.folded_descriptor_bytes}B)
                    </div>
                    <div>
                      <span className="text-neutral-400">Lucas L_n: </span>
                      {ingestResult.algebraic_ingestion.pisot_lucas_state.lucas_L_n}
                    </div>
                    <div>
                      <span className="text-neutral-400">Disk Written: </span>
                      <span className="text-emerald-400">
                        {ingestResult.al_haras_security.key_custody.persistent_disk_bytes_written}{' '}
                        bytes
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Right: In-Place Zero-Copy Pointer Computation */}
          <Card className="p-6 border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70 space-y-4">
            <div className="flex items-center justify-between border-b border-neutral-200 dark:border-neutral-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-neutral-900 dark:text-white">
                  Execute Computation Against ptr_ovid_&lt;hash&gt;
                </h3>
                <p className="text-xs text-neutral-500">
                  Evaluates mathematical pointers directly in place without staging file copies
                </p>
              </div>
              <Play className="w-4 h-4 text-blue-500" aria-hidden="true" />
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div>
                <label
                  htmlFor="exec-pointer-id"
                  className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                >
                  TARGET OVID ZERO-COPY POINTER
                </label>
                <input
                  id="exec-pointer-id"
                  name="pointer_id"
                  type="text"
                  value={pointerIdInput}
                  autoCorrect="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  onChange={(e) => {
                    setPointerIdInput(e.target.value);
                    setPointerExecError(null);
                  }}
                  placeholder="ptr_ovid_<64-char-sha256>"
                  className="w-full p-2 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="exec-operation"
                    className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                  >
                    ALGEBRAIC KERNEL
                  </label>
                  <select
                    id="exec-operation"
                    name="operation"
                    value={pointerOp}
                    onChange={(e) => setPointerOp(e.target.value)}
                    className="w-full p-2 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900"
                  >
                    <option value="PV_LATTICE_FOLD">PV_LATTICE_FOLD (φ^k Scaling)</option>
                    <option value="LUCAS_PV_SCALING">LUCAS_PV_SCALING (Exact L_n)</option>
                    <option value="METALLIC_SCALE">METALLIC_SCALE (σ_m^k)</option>
                    <option value="EXACT_RECONSTRUCT_VERIFY">
                      EXACT_RECONSTRUCT_VERIFY (SHA-256)
                    </option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="exec-scale-order"
                    className="block text-[11px] text-neutral-500 mb-1 font-semibold"
                  >
                    LATTICE SCALE ORDER (k)
                  </label>
                  <input
                    id="exec-scale-order"
                    name="scale_order"
                    type="number"
                    min={0}
                    max={256}
                    value={scaleOrder}
                    onChange={(e) => setScaleOrder(Number(e.target.value))}
                    className="w-full p-2 rounded border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900"
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={handleExecutePointer}
                className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-colors"
              >
                Execute In-Place Against Pointer (0 Bytes Moved)
              </button>
            </div>

            <div aria-live="polite">
              {pointerExecError && (
                <p className="text-xs font-mono text-red-600 dark:text-red-400">
                  {pointerExecError}
                </p>
              )}

              {pointerExecResult && (
                <div className="p-4 rounded-lg bg-neutral-950 text-neutral-200 border border-neutral-800 text-[11px] font-mono space-y-1.5">
                  <div className="flex items-center justify-between text-emerald-400 font-semibold">
                    <span>✓ IN-PLACE EXECUTION COMPLETE</span>
                    <span>Egress: {pointerExecResult.egress_bytes_transferred} B</span>
                  </div>
                  <div>
                    <span className="text-neutral-400">Bulk Staging: </span>
                    {pointerExecResult.bulk_staging_bytes} B ·{' '}
                    <span className="text-neutral-400">Data Stays at Rest: </span>
                    {String(pointerExecResult.data_stays_at_rest)}
                  </div>
                  <div className="p-2 rounded bg-neutral-900 border border-neutral-800 overflow-x-auto">
                    {JSON.stringify(pointerExecResult.computation)}
                  </div>
                  <div className="truncate text-neutral-400">
                    ML-DSA-87 Receipt: {pointerExecResult.fips_204_mldsa_signature}
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </section>

      {/* SECTION 4: Pre-Built Connector Technical Specifications (Searchable Exclusive Accordions) */}
      <section aria-labelledby="specs-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCode2
              className="w-5 h-5 text-neutral-700 dark:text-neutral-300"
              aria-hidden="true"
            />
            <h2
              id="specs-heading"
              className="text-lg font-semibold text-neutral-900 dark:text-white"
            >
              4. Pre-Built Zero-Copy Connector Technical Specifications (S3, Snowflake &amp; Enterprise)
            </h2>
          </div>
          <span className="text-xs font-mono text-neutral-400">
            Find-in-Page Searchable Specifications
          </span>
        </div>

        <div className="space-y-2">
          {prebuiltList.map((spec, idx) => (
            <details
              key={spec.connector_type}
              name="connector-specs"
              open={idx === 0}
              className="chronus-spec-accordion rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white/70 dark:bg-neutral-950/70 overflow-hidden group"
            >
              <summary className="p-4 flex items-center justify-between gap-4 hover:bg-neutral-50 dark:hover:bg-neutral-900/50 select-none">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="px-2 py-0.5 rounded bg-neutral-900 text-white dark:bg-white dark:text-neutral-950 text-[11px] font-mono font-bold">
                    {spec.connector_type}
                  </span>
                  <span className="text-sm font-semibold text-neutral-900 dark:text-white">
                    {spec.title}
                  </span>
                  <span className="text-xs font-mono text-emerald-600 dark:text-emerald-400">
                    Day-1 Ready: ~{spec.day_1_readiness_minutes} min
                  </span>
                </div>
                <ChevronDown
                  className="w-4 h-4 text-neutral-400 transition-transform group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>

              <div className="p-4 pt-0 border-t border-neutral-100 dark:border-neutral-800/80 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                <div className="space-y-2 pt-3">
                  <div>
                    <span className="text-neutral-400 block text-[10px]">URI SCHEME &amp; DEFAULT PLANE</span>
                    <span className="text-neutral-800 dark:text-neutral-200">
                      {spec.uri_scheme} ({spec.default_access_class})
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-400 block text-[10px]">POINTER ARCHITECTURE</span>
                    <span className="text-neutral-700 dark:text-neutral-300">
                      {spec.pointer_architecture}
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-400 block text-[10px]">TRANSPORT PROTOCOL</span>
                    <span className="text-neutral-700 dark:text-neutral-300">
                      {spec.transport_protocol}
                    </span>
                  </div>
                </div>
                <div className="space-y-2 pt-3">
                  <div>
                    <span className="text-neutral-400 block text-[10px]">
                      AL HARAS &amp; CUSTOMER KMS / PKCS#11 CUSTODY
                    </span>
                    <span className="text-neutral-700 dark:text-neutral-300">
                      {spec.kms_custody_flow}
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-400 block text-[10px]">EGRESS &amp; ETL ELIMINATION</span>
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                      {spec.egress_elimination}
                    </span>
                  </div>
                  <div>
                    <span className="text-neutral-400 block text-[10px]">AUTO-INGEST FORMATS</span>
                    <span className="text-purple-600 dark:text-purple-400">
                      {spec.supported_formats.join(' · ')}
                    </span>
                  </div>
                </div>
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}
