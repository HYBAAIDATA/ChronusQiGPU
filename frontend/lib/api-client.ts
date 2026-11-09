const API_ROOT = '/api/chronus';

export type ApiRecord = Record<string, any>;
export type WorkloadResponse = ApiRecord;
export type VerifyReceiptResponse = ApiRecord;
export type PaginatedWorkloads = ApiRecord & { items?: ApiRecord[] };

export class ChronusAPIError extends Error {
  constructor(message: string, public readonly status: number, public readonly payload?: unknown) {
    super(message);
    this.name = 'ChronusAPIError';
  }
}

async function request<T = ApiRecord>(path: string, init: RequestInit = {}, authToken?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (authToken?.trim()) headers.set('authorization', `Bearer ${authToken.trim()}`);
  if (init.body && !headers.has('content-type')) headers.set('content-type', 'application/json');
  headers.set('accept', 'application/json');

  let response: Response;
  try {
    response = await fetch(`${API_ROOT}/${path.replace(/^\//, '')}`, {
      ...init,
      headers,
      cache: 'no-store',
    });
  } catch {
    throw new ChronusAPIError('Chronus API is unavailable. Check the backend connection.', 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try { payload = JSON.parse(text); }
    catch { payload = { detail: text }; }
  }
  if (!response.ok) {
    const detail = (payload as any)?.detail ?? (payload as any)?.error ?? response.statusText;
    const message = typeof detail === 'string' ? detail : JSON.stringify(detail);
    throw new ChronusAPIError(message || `Chronus request failed (${response.status}).`, response.status, payload);
  }
  return payload as T;
}

const get = <T = ApiRecord>(path: string, authToken?: string) => request<T>(path, {}, authToken);
const post = <T = ApiRecord>(path: string, body: unknown, authToken?: string) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) }, authToken);
const segment = (value: string) => encodeURIComponent(value);

/** Thin transport for the implemented, reviewed UI routes. Failed requests never become mock success. */
export class ChronusAPIClient {
  static getWorkloads = (authToken: string, page = 1, pageSize = 20) =>
    get<PaginatedWorkloads>(`v1/workloads?page=${page}&page_size=${pageSize}`, authToken);
  static dispatchWorkload = (body: unknown, authToken: string) =>
    post<WorkloadResponse>('v1/workloads', body, authToken);
  static verifyReceipt = (receiptId: string) =>
    get<VerifyReceiptResponse>(`v1/verify/${segment(receiptId)}`);
  static getStorage = () => get<ApiRecord>('v1/storage');

  // Hashrate Intelligence & Mining Administration
  static getMiningStatus = () => get<ApiRecord>('v1/mining/admin/status');
  static startMining = (baseHashrateEhS?: number, activeWarps?: number) =>
    post<ApiRecord>('v1/mining/admin/start', {
      base_hashrate_eh_s: baseHashrateEhS,
      active_warps: activeWarps,
    });
  static stopMining = () => post<ApiRecord>('v1/mining/admin/stop', {});
  static configureMiningCapacity = (
    baseHashrateEhS?: number,
    activeWarps?: number,
    coreVoltageV?: number,
    fanSpeedPct?: number
  ) =>
    post<ApiRecord>('v1/mining/admin/configure', {
      base_hashrate_eh_s: baseHashrateEhS,
      active_warps: activeWarps,
      core_voltage_v: coreVoltageV,
      fan_speed_pct: fanSpeedPct,
    });
  static configureMiningIntelligence = (
    predictive: number,
    causal: number,
    counterfactual: number,
    topological: number,
    geometric: number
  ) =>
    post<ApiRecord>('v1/mining/admin/intelligence', {
      predictive,
      causal,
      counterfactual,
      topological,
      geometric,
    });
  static applyCausalIntervention = (intervention: string) =>
    post<ApiRecord>('v1/mining/admin/intervene', { intervention });
  static getPatroclusTelemetry = () => get<ApiRecord>('v1/mining/admin/patroclus');
  static configureMiningStealth = (
    maxConfiguredEhS?: number,
    stealthTargetEhS?: number,
    neverConsecutiveBlocks?: boolean,
    persistentPresence?: boolean
  ) =>
    post<ApiRecord>('v1/mining/admin/stealth', {
      max_configured_eh_s: maxConfiguredEhS,
      stealth_target_eh_s: stealthTargetEhS,
      never_consecutive_blocks: neverConsecutiveBlocks,
      persistent_presence: persistentPresence,
    });
}
