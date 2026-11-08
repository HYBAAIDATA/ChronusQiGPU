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
}
