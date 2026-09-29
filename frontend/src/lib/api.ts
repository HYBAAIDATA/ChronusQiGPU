/** Canonical frontend-to-Python control API boundary. */

const API_BASE = (import.meta.env.VITE_PYTHIA_PYTHON_API_URL || "").replace(/\/$/, "");
const OPERATOR_KEY = "pythia.operatorKey";

export function apiUrl(input: string): string {
  return input.startsWith("/") ? `${API_BASE}${input}` : input;
}

/** The operator key for this browser session only (never localStorage). */
export function operatorKey(): string | null {
  try {
    return window.sessionStorage.getItem(OPERATOR_KEY);
  } catch {
    return null;
  }
}

export function setOperatorKey(key: string | null): void {
  try {
    if (key) window.sessionStorage.setItem(OPERATOR_KEY, key);
    else window.sessionStorage.removeItem(OPERATOR_KEY);
  } catch {
    // Storage unavailable: the operator is asked again next time.
  }
}

/**
 * Reads pass through. A state-changing request carries the operator key
 * (the control API refuses it otherwise); on 401 the operator is asked for
 * the key once and the request is retried with it.
 */
export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const target = typeof input === "string" ? apiUrl(input) : input;
  const headers = new Headers(init.headers || {});
  const method = (init.method || "GET").toUpperCase();
  const mutating = method !== "GET" && method !== "HEAD";
  const key = mutating ? operatorKey() : null;
  if (key) headers.set("Authorization", `Bearer ${key}`);
  const response = await fetch(target, { ...init, headers });
  if (!mutating || response.status !== 401 || typeof window.prompt !== "function") {
    return response;
  }
  if (key) setOperatorKey(null); // the stored key was refused
  const entered = window.prompt("Operator key (EUCLID_ADMIN_API_KEY)")?.trim();
  if (!entered) return response;
  setOperatorKey(entered);
  headers.set("Authorization", `Bearer ${entered}`);
  return fetch(target, { ...init, headers });
}
