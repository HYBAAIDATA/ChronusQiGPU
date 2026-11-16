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

  // Shared mining administration: explicit short-lived operator JWT in memory only.
  // Never infer authorization from a tenant token, URL path or local UI state.
  static getMiningStatus = (operatorJwt?: string) =>
    get<ApiRecord>('v1/mining/admin/status', operatorJwt);
  static startMining = (baseHashrateEhS?: number, activeWarps?: number, operatorJwt?: string) =>
    post<ApiRecord>('v1/mining/admin/start', {
      base_hashrate_eh_s: baseHashrateEhS,
      active_warps: activeWarps,
    }, operatorJwt);
  static stopMining = (operatorJwt?: string) =>
    post<ApiRecord>('v1/mining/admin/stop', {}, operatorJwt);
  static configureMiningCapacity = (
    baseHashrateEhS?: number,
    activeWarps?: number,
    coreVoltageV?: number,
    fanSpeedPct?: number,
    operatorJwt?: string
  ) =>
    post<ApiRecord>('v1/mining/admin/configure', {
      base_hashrate_eh_s: baseHashrateEhS,
      active_warps: activeWarps,
      core_voltage_v: coreVoltageV,
      fan_speed_pct: fanSpeedPct,
    }, operatorJwt);
  static configureMiningIntelligence = (
    predictive: number,
    causal: number,
    counterfactual: number,
    topological: number,
    geometric: number,
    operatorJwt?: string
  ) =>
    post<ApiRecord>('v1/mining/admin/intelligence', {
      predictive,
      causal,
      counterfactual,
      topological,
      geometric,
    }, operatorJwt);
  static applyCausalIntervention = (intervention: string, operatorJwt?: string) =>
    post<ApiRecord>('v1/mining/admin/intervene', { intervention }, operatorJwt);
  static getPatroclusTelemetry = (operatorJwt?: string) =>
    get<ApiRecord>('v1/mining/admin/patroclus', operatorJwt);
  static configureMiningStealth = (
    maxConfiguredEhS?: number,
    stealthTargetEhS?: number,
    neverConsecutiveBlocks?: boolean,
    persistentPresence?: boolean,
    operatorJwt?: string
  ) =>
    post<ApiRecord>('v1/mining/admin/stealth', {
      max_configured_eh_s: maxConfiguredEhS,
      stealth_target_eh_s: stealthTargetEhS,
      never_consecutive_blocks: neverConsecutiveBlocks,
      persistent_presence: persistentPresence,
    }, operatorJwt);

  // AL HARAS (HYBA Security). GET status is public; every POST check needs a tenant bearer token.
  // Response keys are still being revised, so responses stay ApiRecord: render only the keys present.
  static getALHarasStatus = () => get<ApiRecord>('v1/al-haras/status');
  static inspectALHarasWorkload = (authToken: string, body: ALHarasInspectRequest) =>
    post<ApiRecord>('v1/al-haras/inspect', body, authToken);
  static executeAgenticSheafTurn = (authToken: string, states?: Record<string, number[]>, stalkDim = 4) =>
    post<ApiRecord>(
      'v1/al-haras/applications/agentic-sheaf/verify-turn',
      { agent_states: states, stalk_dim: stalkDim },
      authToken
    );
  static transmitOrbitalTelemetry = (
    authToken: string,
    packetPayload?: string,
    sourceSat?: string,
    targetSat?: string,
    constellationSize?: number
  ) =>
    post<ApiRecord>(
      'v1/al-haras/applications/orbital-mesh/transmit',
      {
        packet_payload: packetPayload,
        source_sat: sourceSat,
        target_sat: targetSat,
        constellation_size: constellationSize,
      },
      authToken
    );
  static executeZkNeuralProveAndVerify = (authToken: string, sensorInput?: number[], weightsCommitment?: string) =>
    post<ApiRecord>(
      'v1/al-haras/applications/zk-neural/prove-and-verify',
      { sensor_input: sensorInput, weights_commitment: weightsCommitment },
      authToken
    );
  static processCBDCCrossBorderSettlement = (
    authToken: string,
    senderBank?: string,
    receiverBank?: string,
    amountTokens?: number,
    simulateDoubleSpend?: boolean
  ) =>
    post<ApiRecord>(
      'v1/al-haras/applications/cbdc-settlement/process',
      {
        sender_bank: senderBank,
        receiver_bank: receiverBank,
        amount_tokens: amountTokens,
        simulate_double_spend: simulateDoubleSpend,
      },
      authToken
    );
  static executeTISAMicrocode = (
    authToken: string,
    funct7: number,
    rs1Val?: ALHarasRegisterValue,
    rs2Val?: ALHarasRegisterValue,
    rs1 = 1,
    rs2 = 2,
    rd = 3
  ) =>
    post<ApiRecord>(
      'v1/al-haras/applications/t-isa/execute',
      { funct7, rs1, rs2, rd, rs1_val: rs1Val, rs2_val: rs2Val },
      authToken
    );
}

// AL HARAS (HYBA Security) request bodies. Omitted optional fields fall back to the API defaults.
/** Integer coefficients (c0, c1, c2, c3) of c0 + c1·ζ + c2·ζ² + c3·ζ³ held in one coprocessor-model register. */
export type ALHarasRegisterValue = [number, number, number, number];

export interface ALHarasInspectRequest {
  payload: string;
  /** Numbers or exact strings such as '1/3'. */
  state_vectors?: Array<Array<number | string>>;
  edges?: Array<[string, string]>;
  /** Largest per-edge residual norm accepted as agreement, as an exact string. */
  tolerance?: string;
}
