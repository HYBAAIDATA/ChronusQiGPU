// Typed REST client for the Python control_api.py backend.
// Relative calls go through the Node proxy (server.ts) which forwards
// /api/v1/*, /healthz, /readyz, /metrics to the Python backend.
// Override with VITE_PYTHIA_API_URL for standalone dev.

const API_BASE = ((import.meta.env as Record<string, string>)["VITE_PYTHIA_API_URL"] ?? "").replace(/\/$/, "");

// ---- Types (matching control_api.py / src/lib/status.ts) -----------------

export type BackendHealth = { ok: boolean; error?: string };

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

export type CanonicalEngine = {
  product: string;
  path: string;
  backend: string;
  ladder: number[];
  execution: string;
  hashrate: string;
  fallback: boolean;
};

export type MlaStatus = {
  schema_version?: string;
  generated_at?: string;
  product?: string;
  backend?: string;
  canonicalEngine?: CanonicalEngine;
  host?: { profile?: string | null; stratum?: { host: string; port: number } | null };
  workers?: Record<string, WorkerPublic>;
  stratum?: { connected?: boolean; status?: string };
  measurement?: string;
};

export type IntelligenceStatus = {
  state?: string;
  started_at?: number | null;
  finished_at?: number | null;
  error?: string | null;
  summary?: {
    passed?: boolean;
    checks?: { passed: number; total: number };
    failures?: string[];
  };
};

export type AgenticStatus = {
  state?: string;
  started_at?: number | null;
};

export type FabricSubsystem = {
  key: string;
  name: string;
  module: string;
  wired: string;
  present: boolean;
  detail?: string;
};

export type FabricMap = {
  subsystems?: FabricSubsystem[];
  summary?: Record<string, number>;
  generated_at?: number;
};

export type TelemetrySummary = {
  hashrate?: number | string;
  shares_accepted?: number;
  shares_rejected?: number;
  pool_latency_ms?: number | null;
  uptime_s?: number;
  [key: string]: unknown;
};

// ---- HTTP helper ---------------------------------------------------------

async function apiFetch<T>(path: string, signal?: AbortSignal): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      signal,
      headers: { accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ---- Read endpoints ------------------------------------------------------

export async function fetchHealth(signal?: AbortSignal): Promise<BackendHealth> {
  const data = await apiFetch<{ status?: string }>("/healthz", signal);
  return data !== null ? { ok: true } : { ok: false, error: "unreachable" };
}

export async function fetchStatus(signal?: AbortSignal): Promise<MlaStatus | null> {
  return apiFetch<MlaStatus>("/api/v1/mla1517/status", signal);
}

export async function fetchIntelligenceStatus(signal?: AbortSignal): Promise<IntelligenceStatus | null> {
  return apiFetch<IntelligenceStatus>("/api/v1/intelligence/status", signal);
}

export async function fetchAgenticStatus(signal?: AbortSignal): Promise<AgenticStatus | null> {
  return apiFetch<AgenticStatus>("/api/v1/agentic/start", signal);
}

export async function fetchFabricMap(signal?: AbortSignal): Promise<FabricMap | null> {
  return apiFetch<FabricMap>("/api/v1/system/map", signal);
}

export async function fetchTelemetry(signal?: AbortSignal): Promise<TelemetrySummary | null> {
  return apiFetch<TelemetrySummary>("/api/v1/telemetry/summary", signal);
}

// ---- Control endpoints (POST) --------------------------------------------

async function apiPost(path: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal,
      headers: { accept: "application/json", "content-type": "application/json" },
    });
    return res.ok;
  } catch {
    return false;
  }
}

export const postMiningControl = (
  action: "start" | "stop" | "switch" | "elevate" | "escalate",
  signal?: AbortSignal,
) => apiPost(`/api/v1/mining/${action}`, signal);

export const postAgenticControl = (
  action: "start" | "stop",
  signal?: AbortSignal,
) => apiPost(`/api/v1/agentic/${action}`, signal);

export const postIntelSelfTest = (signal?: AbortSignal) =>
  apiPost("/api/v1/intelligence/selftest", signal);
