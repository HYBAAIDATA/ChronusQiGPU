/** Canonical frontend-to-Python control API boundary. */

const API_BASE = (import.meta.env.VITE_PYTHIA_PYTHON_API_URL || "").replace(/\/$/, "");

export function apiUrl(input: string): string {
  return input.startsWith("/") ? `${API_BASE}${input}` : input;
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const target = typeof input === "string" ? apiUrl(input) : input;
  return fetch(target, { ...init, headers: new Headers(init.headers || {}) });
}
