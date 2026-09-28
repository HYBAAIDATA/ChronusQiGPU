/** Payload contract of the Python control API (mla1517.status/1). */

export type StratumIdentity = {
  profile: string;
  host: string;
  port: number;
  user_redacted: string;
  password_committed: boolean;
  identity_commit: string;
};

export type CanonicalEngine = {
  product: string;
  path: string;
  backend: string;
  ladder: number[];
  execution: string;
  hashrate: string;
  fallback: boolean;
};

export type DeviceInfo = {
  platform: string;
  device: string;
  vendor: string;
  family?: string | null;
  dispatch?: string | null;
  known?: boolean;
  hyba_alias?: string | null;
  is_gpu?: boolean;
};

export type GpuSection = {
  available?: boolean;
  count?: number;
  devices?: DeviceInfo[];
  running_backend?: string;
  running_device?: string;
  hasher?: { backend?: string; device?: string; fallback_reason?: string | null };
  punch?: { use_opencl?: boolean; backend?: string; gpu_error?: string | null };
  vendors?: {
    probes?: Array<{
      vendor: string;
      backend: string;
      present: boolean;
      detail: string;
      devices: string[];
    }>;
    executing_backends?: string[];
    planning_backends?: string[];
    container_hint?: string;
  };
  generated_at?: string;
  error?: string;
};

export type WorkerPublic = {
  state: string;
  since: string;
  attempts_total: number;
  attempts_window: number;
  last_heartbeat: string | null;
  liveness: boolean;
  readiness: boolean;
  effectiveness: { hashrate: number; shares_accepted: number };
  last_error: { kind: string; message: string } | null;
};

export type SolverManifold = {
  arms: number;
  lanes_per_arm: number;
  lane_ceiling: number;
  nonce_partition: string;
  hashrate: string;
};

export type StratumPrimaryStatus = {
  configured?: boolean;
  pool_id?: string;
  transport?: "CONNECTED" | "DISCONNECTED" | string;
  subscribed?: boolean;
  authorized?: boolean;
  endpoint?: string;
  worker?: string;
  connected_at?: number | null;
  last_message_at?: number | null;
  last_error?: string | null;
};

export type StratumJobStatus = {
  active?: boolean;
  generation?: number | null;
  invalidated_generation?: number | null;
  job_id?: string | null;
  fingerprint?: string | null;
  received_at?: number | null;
  age_ms?: number | null;
  clean_jobs?: boolean | null;
  difficulty?: string | number | null;
  difficulty_source?: string | null;
  difficulty_received_at?: number | null;
  share_target?: string | null;
  target_generation?: number;
};

export type StratumSubmissionStatus = {
  state?: "IDLE" | "SUBMITTING" | "ACCEPTED" | "REJECTED" | "OUTCOME_UNKNOWN" | string;
  last_result?: "ACCEPTED" | "REJECTED" | "OUTCOME_UNKNOWN" | null | string;
  last_submit_at?: number | null;
  last_response_at?: number | null;
  generation?: number | null;
  job_id?: string | null;
  job_fingerprint?: string | null;
};

export type StratumStatus = {
  schema?: string;
  state?: string;
  ready?: boolean;
  connected?: boolean;
  status?: string;
  evidence_available?: boolean;
  primary?: StratumPrimaryStatus;
  job?: StratumJobStatus;
  submission?: StratumSubmissionStatus;
  counters?: {
    jobs_received?: number;
    jobs_invalidated?: number;
    disconnects?: number;
    submitted?: number;
    accepted?: number;
    rejected?: number;
    unknown?: number;
  };
};

export type RuntimePool = {
  endpoint: string;
  worker: string;
  /** Read-only marker — whether a password is stored. Absent on writes. */
  password_committed?: boolean;
  enabled: boolean;
  /** Write-only field — the API never returns stored passwords. */
  password?: string;
};

export type RuntimeConfig = {
  updated_at?: number | null;
  pools?: RuntimePool[];
  solvers?: { arms: number; workers: number };
  hashrate?: { target_hs: number; ceiling_hs: number };
  live_submit?: { enabled: boolean; approval_bound: boolean };
  window?: number;
  bounds?: {
    arms?: [number, number];
    workers_per_arm?: [number, number];
    hashrate_ceiling_hs?: number;
    window?: [number, number];
  };
  effective_arms?: number;
  live_arms?: string[];
};

export type MlaStatus = {
  schema_version?: string;
  generated_at?: string;
  product?: string;
  backend?: string;
  canonicalEngine?: CanonicalEngine;
  host?: { profile?: string | null; stratum?: StratumIdentity | null };
  solvers?: SolverManifold;
  runtime?: RuntimeConfig;
  device?: { available?: boolean; count?: number; devices?: DeviceInfo[] };
  workers?: Record<string, WorkerPublic>;
  stratum?: StratumStatus;
  measurement?: string;
};

export type ReadyToMine = {
  ready?: boolean;
  reason?: string;
  details?: Record<string, unknown>;
};

/** Forensic system fabric map (pythia.fabric_map/1). */
export type FabricSubsystem = {
  key: string;
  name: string;
  module: string;
  wired: "production" | "fabric" | "orchestrator" | "idle" | "parked" | "stub";
  gate: string | null;
  gate_state: "open" | "closed" | null;
  present: boolean;
  detail?: string;
};

export type FabricMap = {
  schema?: string;
  generated_at?: number;
  subsystems?: FabricSubsystem[];
  summary?: Record<string, number>;
  gates?: Record<string, unknown>;
};

/** Generic supervised-runner status (system_fabric._Runner.status()). */
export type RunnerStatus = {
  schema?: string;
  state?: "idle" | "running" | "done" | "stopped" | "error";
  started_at?: number | null;
  finished_at?: number | null;
  error?: string | null;
  progress?: Record<string, unknown>;
  result?: unknown;
};

export type VerificationStatus = RunnerStatus & {
  ready?: boolean;
  theorem_proven?: boolean;
  stages?: Record<string, { ok?: boolean; detail?: string }>;
  overlay?: {
    faces_total?: number;
    icosahedral?: number;
    dodecahedral?: number;
    face_pairs?: number;
  };
};

export type SelftestStatus = RunnerStatus & {
  summary?: { passed?: boolean; checks?: { passed: number; total: number }; failures?: string[] };
};

export type AgenticStatus = RunnerStatus;

export type CampaignPhaseRecord = {
  index: number;
  pool: string;
  endpoint?: string;
  worker?: string;
  duration_s?: number;
  target_hs?: number;
  measured_hs_avg?: number | null;
  measured_hs_peak?: number | null;
  shares_accepted?: number;
};

export type CampaignStatus = RunnerStatus & {
  // result.phases is the ordered per-phase record list after a run.
};

/** Live + session telemetry aggregate (telemetry_summary_payload). */
export type TelemetrySummary = {
  schema_version?: string;
  generated_at?: string;
  backend?: string;
  hashrate?: number;
  shares_accepted?: number;
  session?: {
    supervisor_started_at?: string;
    uptime_s?: number;
    attempts_total?: number;
  };
  workers?: Record<string, WorkerPublic>;
};

/** Append-only audit trail record (pythia.audit_tail/1). */
export type AuditEvent = { at?: string; event?: string } & Record<string, unknown>;

export type AuditTail = {
  schema?: string;
  generated_at?: string;
  count?: number;
  records?: AuditEvent[];
};
