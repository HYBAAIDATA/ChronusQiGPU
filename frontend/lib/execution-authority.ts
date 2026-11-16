/** Explicit synchronous CPU execution client. Mining-loop integration is separate. */
export interface ExecutionReceipt {
  producer: 'CHRONUS';
  schema_version: number;
  tenant_id: string;
  run_id: string;
  status: 'COMPLETED' | 'FAILED' | 'TIMED_OUT';
  input_sha256: string;
  receipt_object_id: string;
  backend: string;
  result?: Record<string, unknown>;
  error?: string;
}

export class ExecutionAuthorityClient {
  constructor(
    privateBaseUrl: string,
    privateToken: string,
    privateTenant: string,
  ) {
    this.baseUrl = privateBaseUrl.replace(/\/$/, '');
    this.token = privateToken;
    this.tenant = privateTenant;
  }
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly tenant: string;

  private async request(path: string, init: RequestInit): Promise<ExecutionReceipt> {
    const response = await fetch(`${this.baseUrl}/api/v1/execute${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${this.token}` },
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`CHRONUS execution request failed (${response.status})`);
    const receipt = await response.json() as ExecutionReceipt;
    if (receipt.producer !== 'CHRONUS' || receipt.schema_version !== 1 ||
        receipt.tenant_id !== this.tenant || !/^[a-f0-9]{64}$/.test(receipt.receipt_object_id) ||
        !['COMPLETED', 'FAILED', 'TIMED_OUT'].includes(receipt.status)) {
      throw new Error('CHRONUS returned an invalid execution receipt');
    }
    return receipt;
  }

  async execute(payload: Uint8Array, workloadType: string, wallSeconds = 30,
                signal?: AbortSignal): Promise<ExecutionReceipt> {
    let binary = '';
    for (const byte of payload) binary += String.fromCharCode(byte);
    const receipt = await this.request('', {
      method: 'POST', signal,
      body: JSON.stringify({ workload: {
        tenant_id: this.tenant, workload_type: workloadType,
        backend_preference: 'python-math-reference', payload_bytes: `base64:${btoa(binary)}`,
      }, wall_seconds: wallSeconds }),
    });
    const digest = await crypto.subtle.digest('SHA-256', new Uint8Array(payload));
    const expected = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    if (receipt.input_sha256 !== expected) throw new Error('CHRONUS input digest mismatch');
    return receipt;
  }

  status(receiptId: string, signal?: AbortSignal): Promise<ExecutionReceipt> {
    if (!/^[a-f0-9]{64}$/.test(receiptId)) throw new Error('Invalid receipt identifier');
    return this.request(`/status?receipt_object_id=${receiptId}`, { method: 'GET', signal });
  }
}
