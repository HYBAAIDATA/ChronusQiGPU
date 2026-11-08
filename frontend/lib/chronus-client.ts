export type SystemStatusCode = 'CHECKING' | 'READY' | 'NOT_READY' | 'UNAVAILABLE' | 'UNCONFIGURED';

export interface SystemStatus {
  status: SystemStatusCode;
  service?: string;
  version?: string;
  execution_mode?: string;
  checked_at: string;
  message?: string;
}

/** Reads the service's actual readiness probe; it does not infer hardware or release qualification. */
export async function fetchSystemStatus(): Promise<SystemStatus> {
  const checked_at = new Date().toISOString();
  try {
    const response = await fetch('/api/chronus/health/ready', { cache: 'no-store' });
    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload?.status === 'ready') {
      return {
        status: 'READY',
        service: payload.service,
        version: payload.version,
        execution_mode: payload.execution_mode,
        checked_at,
      };
    }
    const code = payload?.status === 'unconfigured' ? 'UNCONFIGURED' : 'NOT_READY';
    return {
      status: code,
      checked_at,
      message: payload?.error || payload?.detail?.reason || 'The readiness probe did not return ready.',
    };
  } catch {
    return {
      status: 'UNAVAILABLE',
      checked_at,
      message: 'The Chronus API could not be reached.',
    };
  }
}
