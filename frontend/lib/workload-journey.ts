// Browser workflow state, independent of React and transport. Never retain credentials.
export type JsonRecord = Record<string, unknown>;
export type WorkloadRecord = JsonRecord & {
  workload_id: string;
  tenant_id: string;
  status: string;
  workload_type: string;
  result?: JsonRecord | null;
  verification_receipt?: string | null;
};
export type Observation<T> = { data: T; observedAt: string };
export type JourneyIssue = { title: string; action: string };
export type JourneyState = {
  pending: 'submit' | 'record' | 'history' | 'verify' | null;
  record: Observation<WorkloadRecord> | null;
  history: Observation<{ items: WorkloadRecord[]; total: number; page: number }> | null;
  verification: Observation<JsonRecord> | null;
  submitIssue: JourneyIssue | null;
  recordIssue: JourneyIssue | null;
  historyIssue: JourneyIssue | null;
  verificationIssue: JourneyIssue | null;
};
export type WorkloadTransport = {
  dispatchWorkload(body: unknown, credential: string): Promise<unknown>;
  getWorkload(id: string, credential: string): Promise<unknown>;
  getWorkloads(credential: string, page: number, pageSize: number): Promise<unknown>;
  verifyReceipt(id: string): Promise<unknown>;
};

const lifecycle = ['SUBMITTED', 'QUEUED', 'PROVISIONING', 'EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED', 'RECOVERING'];
export function asObject(value: unknown): JsonRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : null;
}
function checkedRecord(value: unknown, tenant: string, id?: string): WorkloadRecord {
  const record = asObject(value);
  if (!record || typeof record.workload_id !== 'string' || !record.workload_id || record.tenant_id !== tenant ||
      typeof record.workload_type !== 'string' || !lifecycle.includes(String(record.status)) ||
      (id !== undefined && record.workload_id !== id)) {
    throw new Error('Unexpected workload response');
  }
  return record as WorkloadRecord;
}
export function buildWorkloadRequest(tenantId: string, mode: 'guided' | 'json', input: string, workloadType = 'scaling.v1') {
  const tenant = tenantId.trim();
  if (!tenant || tenant.length > 128) throw new Error('Enter a tenant ID of 1–128 characters.');
  let payload: unknown;
  if (mode === 'guided') {
    if (!/^\d+$/.test(input.trim()) || !Number.isSafeInteger(Number(input))) {
      throw new Error('Enter a non-negative whole-number index within the safe integer range.');
    }
    payload = { index: Number(input) };
  } else {
    try { payload = JSON.parse(input); } catch { throw new Error('Enter valid JSON before submitting.'); }
    if (!asObject(payload)) throw new Error('The JSON payload must be an object, not an array or a single value.');
  }
  return { tenant_id: tenant, workload_type: mode === 'guided' ? 'scaling.v1' : workloadType, payload_bytes: JSON.stringify(payload) };
}

export function requestIssue(cause: unknown, submission = false): JourneyIssue {
  const status = asObject(cause)?.status;
  if (status === 401) return { title: 'Authentication required', action: 'Use a valid credential issued by your platform operator. This console cannot sign you in.' };
  if (status === 403) return { title: 'Permission denied', action: 'Confirm your tenant ID and ask the platform operator for the required permission. No access has been inferred from this page.' };
  if (status === 404) return { title: 'Record unavailable', action: 'The record may not exist in this API process or may not be available to your tenant. Refresh history or contact the operator.' };
  if (status === 429) return { title: 'Request rate limited', action: 'Wait before trying again; the service did not accept this request.' };
  if (typeof status === 'number' && status >= 400 && status < 500) return { title: 'Request rejected', action: 'Review the input, tenant and backend limits with the operator before submitting again.' };
  return submission
    ? { title: 'Submission outcome unknown', action: 'The response could not be confirmed. The workload may have run: load history before deciding whether to submit again. Do not automatically retry.' }
    : { title: 'Observation unavailable', action: 'Check the connection and backend configuration with the operator, then retry this read. Any previous snapshot remains visible, not live.' };
}

export function describeExecution(record: WorkloadRecord | null) {
  if (!record) return { title: 'No execution observed', detail: 'Configure a request or inspect a record from your tenant history.' };
  if (record.status === 'COMPLETED') return { title: 'Execution completed', detail: 'The API reports completion. Inspect the returned result and receipt; completion is not release qualification.' };
  if (record.status === 'FAILED') return { title: 'Execution failed', detail: 'The API reports failure. Inspect the response, correct the cause, then configure a new request if appropriate.' };
  if (record.status === 'CANCELLED') return { title: 'Execution cancelled', detail: 'The API reports cancellation. No successful result is implied.' };
  return { title: `Execution ${record.status.toLowerCase()}`, detail: 'This is the last API snapshot, not a progress estimate. Refresh this record to check for a result without resubmitting.' };
}
export function verificationLabel(value: JsonRecord | null) {
  if (value?.reason === 'not_found') return 'Receipt not found in this API process';
  return value?.valid === true ? 'Verifier reports valid' : value?.valid === false ? 'Verifier reports invalid' : 'Validity not established';
}
export function isStale(observedAt: string, now = Date.now()) {
  return !Number.isFinite(Date.parse(observedAt)) || now - Date.parse(observedAt) >= 60_000;
}

const emptyState = (): JourneyState => ({ pending: null, record: null, history: null, verification: null, submitIssue: null, recordIssue: null, historyIssue: null, verificationIssue: null });
export class WorkloadJourney {
  private state = emptyState();
  private listeners = new Set<() => void>();
  private generation = 0;
  private transport: WorkloadTransport;
  private now: () => string;
  constructor(transport: WorkloadTransport, now = () => new Date().toISOString()) {
    this.transport = transport;
    this.now = now;
  }
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private update(patch: Partial<JourneyState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((listener) => listener());
  }
  clear = () => { this.generation += 1; this.state = emptyState(); this.listeners.forEach((listener) => listener()); };
  private async run(pending: NonNullable<JourneyState['pending']>, issue: 'submitIssue' | 'recordIssue' | 'historyIssue' | 'verificationIssue', task: () => Promise<Partial<JourneyState>>) {
    if (this.state.pending) return;
    const generation = this.generation;
    this.update({ pending, [issue]: null, ...(pending === 'submit' ? { record: null, verification: null, recordIssue: null, verificationIssue: null } : {}) });
    try {
      const patch = await task();
      if (generation === this.generation) this.update(patch);
    } catch (cause) {
      if (generation === this.generation) this.update({ [issue]: requestIssue(cause, pending === 'submit') });
    } finally {
      if (generation === this.generation) this.update({ pending: null });
    }
  }
  submit = (body: ReturnType<typeof buildWorkloadRequest>, credential: string) => this.run('submit', 'submitIssue', async () => {
    const data = checkedRecord(await this.transport.dispatchWorkload(body, credential.trim()), body.tenant_id);
    return { record: { data, observedAt: this.now() } };
  });
  inspect = (id: string, tenant: string, credential: string) => this.run('record', 'recordIssue', async () => {
    const data = checkedRecord(await this.transport.getWorkload(id, credential.trim()), tenant.trim(), id);
    const sameReceipt = this.state.record?.data.workload_id === id && this.state.record?.data.verification_receipt === data.verification_receipt;
    return { record: { data, observedAt: this.now() }, verification: sameReceipt ? this.state.verification : null, verificationIssue: null };
  });
  loadHistory = (tenant: string, credential: string, page = 1) => this.run('history', 'historyIssue', async () => {
    const response = asObject(await this.transport.getWorkloads(credential.trim(), page, 20));
    if (!response || !Array.isArray(response.items) || typeof response.total !== 'number' || response.total < 0 || response.page !== page) throw new Error('Unexpected history response');
    const items = response.items.map((item) => checkedRecord(item, tenant.trim()));
    return { history: { data: { items, total: response.total, page }, observedAt: this.now() } };
  });
  verify = () => {
    const receipt = this.state.record?.data.verification_receipt;
    if (!receipt) return Promise.resolve();
    return this.run('verify', 'verificationIssue', async () => {
      const data = asObject(await this.transport.verifyReceipt(receipt));
      const missing = data?.valid === false && data?.reason === 'not_found';
      if (!data || !('valid' in data) || (data.valid !== null && typeof data.valid !== 'boolean') ||
          (!missing && ![data.receipt_id, data.receipt_handle, data.hash_value].includes(receipt))) throw new Error('Unexpected verifier response');
      return { verification: { data, observedAt: this.now() } };
    });
  };
}

/** Explicit allowlist: credentials, input payload, metadata and callbacks are never exported. */
export function evidenceBundle(state: JourneyState) {
  if (!state.record) return null;
  const record = state.record.data;
  const fields = ['workload_id', 'tenant_id', 'workload_type', 'status', 'submitted_at', 'started_at', 'completed_at', 'result', 'verification_receipt', 'tier', 'tier_contract_version', 'qualification_evidence_hash', 'envelope', 'tier_suspended'];
  const verificationFields = ['valid', 'reason', 'receipt_id', 'receipt_handle', 'hash_value', 'timestamp', 'ed25519_verified', 'ml_dsa_verified', 'stark_quotient_verified', 'qualification_status', 'total_release_gates_evaluated', 'release_gates_passed'];
  const pick = (value: JsonRecord, keys: string[]) => Object.fromEntries(keys.filter((key) => key in value).map((key) => [key, value[key]]));
  return {
    schema: 'chronus.console.observation.v1',
    source: 'Chronus API via /api/chronus',
    observed_at: state.record.observedAt,
    scope: 'API observation only; not independent verification, hardware evidence or release qualification.',
    workload: pick(record, fields),
    verification: state.verification ? { observed_at: state.verification.observedAt, response: pick(state.verification.data, verificationFields) } : null,
  };
}

export type WorkloadDraft = {
  tenantId: string;
  credential: string;
  mode: 'guided' | 'json';
  input: string;
  workloadType: string;
};
type ObservationBundle = NonNullable<ReturnType<typeof evidenceBundle>>;
type DownloadEnvironment = {
  createObjectURL(blob: Blob): string;
  revokeObjectURL(url: string): void;
  createLink(): Pick<HTMLAnchorElement, 'href' | 'download' | 'click'>;
  defer(callback: () => void, milliseconds: number): unknown;
};

/** Browser effects are injected in contract tests; no browser success is inferred. */
export function downloadObservation(bundle: ObservationBundle, environment: DownloadEnvironment = {
  createObjectURL: (blob) => URL.createObjectURL(blob),
  revokeObjectURL: (url) => URL.revokeObjectURL(url),
  createLink: () => document.createElement('a'),
  defer: (callback, milliseconds) => window.setTimeout(callback, milliseconds),
}) {
  const blob = new Blob([JSON.stringify(bundle, null, 2) + '\n'], { type: 'application/json' });
  const url = environment.createObjectURL(blob);
  try {
    const link = environment.createLink();
    link.href = url;
    link.download = 'chronus-workload-observation.json';
    link.click();
  } finally {
    environment.defer(() => environment.revokeObjectURL(url), 1_000);
  }
}

/** These are the actual page event handlers, not a parallel test-only workflow. */
export function createWorkloadPageActions(options: {
  journey: WorkloadJourney;
  getDraft(): WorkloadDraft;
  setTenantId(value: string): void;
  setCredential(value: string): void;
  setValidation(value: string): void;
  setDraftChanged(value: boolean): void;
  setDownloaded(value: boolean): void;
  setDownloadError(value: string): void;
  download?: (bundle: ObservationBundle) => void;
}) {
  const { journey, getDraft, setValidation, setDraftChanged, setDownloaded, setDownloadError } = options;
  const busy = () => journey.getSnapshot().pending !== null;
  const changeIdentity = (update: () => void) => {
    journey.clear(); update(); setValidation(''); setDraftChanged(false); setDownloaded(false); setDownloadError('');
  };
  return {
    changeIdentity,
    changeDraft(update: () => void) { update(); setValidation(''); setDraftChanged(Boolean(journey.getSnapshot().record)); },
    clearAccess() { if (!busy()) changeIdentity(() => { options.setCredential(''); options.setTenantId(''); }); },
    async submit(event: { preventDefault(): void }) {
      event.preventDefault();
      const draft = getDraft();
      if (busy() || !draft.tenantId.trim() || !draft.credential.trim()) return;
      setValidation('');
      let body;
      try { body = buildWorkloadRequest(draft.tenantId, draft.mode, draft.input, draft.workloadType); }
      catch (cause) { setValidation(cause instanceof Error ? cause.message : 'Check your inputs.'); return; }
      setDraftChanged(false);
      await journey.submit(body, draft.credential);
    },
    inspect(id: string) {
      const draft = getDraft();
      // A history read cannot establish that this record matches the current draft.
      // In particular, a failed read retains both the old snapshot and its warning.
      return journey.inspect(id, draft.tenantId, draft.credential);
    },
    downloadEvidence() {
      if (busy()) return;
      const bundle = evidenceBundle(journey.getSnapshot());
      if (!bundle) return;
      setDownloaded(false); setDownloadError('');
      try { (options.download || downloadObservation)(bundle); setDownloaded(true); }
      catch { setDownloadError('Download could not be started. Try again or inspect the API response directly.'); }
    },
  };
}
