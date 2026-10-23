/** Canonical frontend-to-Python control API boundary. */

const API_BASE = (import.meta.env.VITE_PYTHIA_PYTHON_API_URL || "").replace(/\/$/, "");
const OPERATOR_KEY = "pythia.operatorKey";
const OPERATOR_PRINCIPAL = "pythia.operatorPrincipal";
const SUBSCRIPTION_TOKEN = "pythia.subscriptionToken";
const HYBA_TENANT = "pythia.hybaTenant";
const HYBA_ACTOR = "pythia.hybaActor";
// Cancelled credential prompts are remembered for the session — otherwise
// every denied poll would re-ask forever.
const SUBSCRIPTION_DECLINED = "pythia.subscriptionDeclined";

// Mirrors control_api._PRIVILEGED_PREFIXES: these routes are mediated by the
// subscription guardian — X-HYBA tenant/actor headers plus the subscription
// token as bearer — rather than by the operator key alone.
const PRIVILEGED_RE =
  /^\/api\/v1\/(mining|policy|worker|recovery|admin|toe|quantum|scale|assembly|security|tensor)\//;

export function apiUrl(input: string): string {
  return input.startsWith("/") ? `${API_BASE}${input}` : input;
}

function requestPath(input: RequestInfo | URL): string {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  try {
    return new URL(raw, "http://local").pathname;
  } catch {
    return typeof input === "string" ? input : "";
  }
}

function sessionGet(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function sessionSet(key: string, value: string | null): void {
  try {
    if (value) window.sessionStorage.setItem(key, value);
    else window.sessionStorage.removeItem(key);
  } catch {
    // Storage unavailable: the operator is asked again next time.
  }
}

/** Migration compatibility: operator secrets are no longer JavaScript-readable. */
export function operatorKey(): string | null {
  sessionSet(OPERATOR_KEY, null);
  return null;
}

export function setOperatorKey(key: string | null): void {
  // Bearer migration is server-side only; never persist operator secrets in JS.
  sessionSet(OPERATOR_KEY, null);
  void key;
  window.dispatchEvent(new Event("pythia-credentials-changed"));
}

/** Server-mapped operator identity claimed alongside the session bearer. */
export function operatorPrincipal(): string | null {
  return sessionGet(OPERATOR_PRINCIPAL);
}

export function setOperatorPrincipal(principal: string | null): void {
  sessionSet(OPERATOR_PRINCIPAL, principal);
  window.dispatchEvent(new Event("pythia-credentials-changed"));
}

export interface SubscriptionCreds {
  tenant: string;
  actor: string;
  token: string;
}

/** The subscription boundary identity for this browser session only. */
export function subscriptionCreds(): SubscriptionCreds | null {
  const tenant = sessionGet(HYBA_TENANT);
  const actor = sessionGet(HYBA_ACTOR);
  const token = sessionGet(SUBSCRIPTION_TOKEN);
  return tenant && actor && token ? { tenant, actor, token } : null;
}

export function setSubscriptionCreds(creds: SubscriptionCreds | null): void {
  sessionSet(HYBA_TENANT, creds?.tenant ?? null);
  sessionSet(HYBA_ACTOR, creds?.actor ?? null);
  sessionSet(SUBSCRIPTION_TOKEN, creds?.token ?? null);
  window.dispatchEvent(new Event("pythia-credentials-changed"));
}

/** Ask the operator for the subscription boundary triple; null = cancelled. */
function promptSubscriptionCreds(): SubscriptionCreds | null {
  if (typeof window.prompt !== "function") return null;
  const token = window.prompt("Subscription token (al_haras bearer)")?.trim();
  if (!token) return null;
  const tenant = window.prompt("Tenant id (X-HYBA-Tenant)")?.trim();
  if (!tenant) return null;
  const actor = window.prompt("Actor id (X-HYBA-Actor)")?.trim();
  if (!actor) return null;
  return { tenant, actor, token };
}

function applySubscriptionHeaders(headers: Headers, creds: SubscriptionCreds): void {
  headers.set("X-HYBA-Tenant", creds.tenant);
  headers.set("X-HYBA-Actor", creds.actor);
  headers.set("Authorization", `Bearer ${creds.token}`);
}

/** The observation the guardian hashes into the request's evidence receipt. */
function withObservation(init: RequestInit, actor: string): RequestInit {
  const raw = typeof init.body === "string" ? init.body : "";
  try {
    const parsed = raw ? JSON.parse(raw) : {};
    if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
      if (!("observation" in parsed)) {
        parsed.observation = {
          ui: "operator-console",
          actor,
          at: new Date().toISOString(),
        };
      }
      return { ...init, body: JSON.stringify(parsed) };
    }
  } catch {
    // Non-JSON bodies pass through; the boundary refuses them itself.
  }
  return init;
}

async function reasonIs(response: Response, wanted: string): Promise<boolean> {
  try {
    const body = (await response.clone().json()) as { reason?: string };
    return body.reason === wanted;
  } catch {
    return false;
  }
}

/** HttpOnly operator sessions and independently mediated guardian credentials.
 * No client persona, role claim, or operator bearer fallback grants authority.
 */
export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}, options: { interactive?: boolean } = {}): Promise<Response> {
  const target = typeof input === "string" ? apiUrl(input) : input;
  const headers = new Headers(init.headers || {});
  const method = (init.method || "GET").toUpperCase();
  const mutating = method !== "GET" && method !== "HEAD";

  if (PRIVILEGED_RE.test(requestPath(input))) {
    if (requestPath(input) === "/api/v1/mining/evidence") {
      const controlKey = operatorKey(), controlPrincipal = operatorPrincipal();
      if (controlKey) headers.set("X-PYTHIA-Control-Authorization", `Bearer ${controlKey}`);
      if (controlPrincipal) headers.set("X-PYTHIA-Principal", controlPrincipal);
    }
    const creds = subscriptionCreds();
    if (creds) {
      applySubscriptionHeaders(headers, creds);
    } else {
      const key = operatorKey();
      if (key) headers.set("Authorization", `Bearer ${key}`);
    }
    const sendInit = mutating && creds ? withObservation(init, creds.actor) : init;
    const response = await fetch(target, { ...sendInit, credentials: "include", headers });
    if (options.interactive === false || typeof window.prompt !== "function") return response;
    const retryable =
      response.status === 402 ||
      response.status === 403 ||
      (response.status === 400 && (await reasonIs(response, "TENANT_AND_ACTOR_REQUIRED")));
    if (!retryable || sessionGet(SUBSCRIPTION_DECLINED) === "1") return response;
    if (creds) setSubscriptionCreds(null); // the stored creds were refused
    const entered = promptSubscriptionCreds();
    if (!entered) {
      sessionSet(SUBSCRIPTION_DECLINED, "1");
      return response;
    }
    sessionSet(SUBSCRIPTION_DECLINED, null);
    setSubscriptionCreds(entered);
    applySubscriptionHeaders(headers, entered);
    const retryInit = mutating ? withObservation(init, entered.actor) : init;
    return fetch(target, { ...retryInit, credentials: "include", headers });
  }

  const consoleRead = /^\/api\/v1\/(?:mla1517\/status|status|control\/session|config|audit\/tail|stratum\/status|telemetry\/(?:summary|history|causal|events|ops|session|stream))$/.test(requestPath(input));
  const key = mutating || consoleRead ? operatorKey() : null;
  const principal = mutating || consoleRead ? operatorPrincipal() : null;
  if (key) headers.set("Authorization", `Bearer ${key}`);
  if (principal) headers.set("X-PYTHIA-Principal", principal);
  const response = await fetch(target, { ...init, credentials: "include", headers });
  // Operator login is exclusively the HttpOnly-session form. A denied mutation
  // must not fall back to a JavaScript-readable bearer or client role/persona.
  return response;
}
