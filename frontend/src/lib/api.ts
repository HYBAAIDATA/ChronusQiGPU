/** Canonical frontend-to-Python control API boundary. */

const API_BASE = (import.meta.env.VITE_PYTHIA_PYTHON_API_URL || "").replace(/\/$/, "");
const OPERATOR_KEY = "pythia.operatorKey";
const OPERATOR_PRINCIPAL = "pythia.operatorPrincipal";
const SUBSCRIPTION_TOKEN = "pythia.subscriptionToken";
const HYBA_TENANT = "pythia.hybaTenant";
const HYBA_ACTOR = "pythia.hybaActor";
// Cancelled credential prompts are remembered for the session — otherwise
// every denied poll would re-ask forever.
const OPERATOR_KEY_DECLINED = "pythia.operatorKeyDeclined";
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

/** The operator key for this browser session only (never localStorage). */
export function operatorKey(): string | null {
  return sessionGet(OPERATOR_KEY);
}

export function setOperatorKey(key: string | null): void {
  sessionSet(OPERATOR_KEY, key);
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

async function controlError(response: Response): Promise<string | null> {
  try {
    const body = (await response.clone().json()) as { error?: string };
    return typeof body.error === "string" ? body.error : null;
  } catch {
    return null;
  }
}

/**
 * Unrelated public reads pass through. Console reads and state-changing requests carry the operator credential
 * and, when configured, its server-mapped principal id — or, on
 * guardian-mediated routes, the subscription boundary (X-HYBA headers +
 * subscription bearer, and the POST body's `observation`). On the matching
 * denial the operator is asked for the missing credential once and the
 * request is retried with it. Cancelling the prompt declines for the rest of
 * the session — denied responses then surface honestly without re-asking.
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
    const response = await fetch(target, { ...sendInit, headers });
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
    return fetch(target, { ...retryInit, headers });
  }

  const consoleRead = /^\/api\/v1\/(?:mla1517\/status|status|control\/session|config|audit\/tail|stratum\/status|telemetry\/(?:summary|history|causal|events|ops|session|stream))$/.test(requestPath(input));
  const key = mutating || consoleRead ? operatorKey() : null;
  const principal = mutating || consoleRead ? operatorPrincipal() : null;
  if (key) headers.set("Authorization", `Bearer ${key}`);
  if (principal) headers.set("X-PYTHIA-Principal", principal);
  const response = await fetch(target, { ...init, headers });
  if (
    options.interactive === false ||
    !mutating ||
    response.status !== 401 ||
    typeof window.prompt !== "function" ||
    sessionGet(OPERATOR_KEY_DECLINED) === "1"
  ) {
    return response;
  }
  const error = await controlError(response);
  let enteredPrincipal = principal;
  if (error === "operator principal required") {
    enteredPrincipal = window.prompt("Operator principal id (X-PYTHIA-Principal)")?.trim() || null;
    if (!enteredPrincipal) {
      sessionSet(OPERATOR_KEY_DECLINED, "1");
      return response;
    }
    setOperatorPrincipal(enteredPrincipal);
  }
  let enteredKey = key;
  if (!enteredKey || error !== "operator principal required") {
    if (key) setOperatorKey(null); // the stored key was refused
    enteredKey = window.prompt("Operator credential")?.trim() || null;
  }
  if (!enteredKey) {
    sessionSet(OPERATOR_KEY_DECLINED, "1");
    return response;
  }
  sessionSet(OPERATOR_KEY_DECLINED, null);
  setOperatorKey(enteredKey);
  headers.set("Authorization", `Bearer ${enteredKey}`);
  if (enteredPrincipal) headers.set("X-PYTHIA-Principal", enteredPrincipal);
  return fetch(target, { ...init, headers });
}
