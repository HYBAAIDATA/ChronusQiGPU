import { apiUrl, operatorKey, operatorPrincipal } from "./api";

export interface MiningDashboardAccess {
  allowed: boolean;
  principalId: string | null;
  role: string | null;
  reason: string;
}

/**
 * Mining telemetry is CEO-only. The browser never infers this entitlement from
 * a locally stored principal name or from possession of an operator key.
 * Authorization must come from the authenticated control-plane session
 * endpoint. Missing/unavailable evidence therefore fails closed.
 */
export async function miningDashboardAccess(
  fetchImpl: typeof fetch = fetch,
): Promise<MiningDashboardAccess> {
  const key = operatorKey();
  const principal = operatorPrincipal();
  if (!key || !principal) {
    return {
      allowed: false,
      principalId: principal,
      role: null,
      reason: "trusted_control_identity_unavailable",
    };
  }

  const headers = new Headers({
    Authorization: `Bearer ${key}`,
    "X-PYTHIA-Principal": principal,
  });

  try {
    const response = await fetchImpl(apiUrl("/api/v1/control/session"), {
      method: "GET",
      headers,
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!response.ok) {
      return {
        allowed: false,
        principalId: principal,
        role: null,
        reason:
          response.status === 404
            ? "control_session_entitlement_unavailable"
            : "control_session_not_authorized",
      };
    }

    const body = (await response.json()) as {
      principal_id?: unknown;
      role?: unknown;
    };
    const principalId =
      typeof body.principal_id === "string" ? body.principal_id : null;
    const role = typeof body.role === "string" ? body.role.toLowerCase() : null;
    if (principalId !== principal || role !== "ceo") {
      return {
        allowed: false,
        principalId,
        role,
        reason: role === "ceo" ? "control_identity_mismatch" : "ceo_role_required",
      };
    }
    return {
      allowed: true,
      principalId,
      role,
      reason: "authorized",
    };
  } catch {
    return {
      allowed: false,
      principalId: principal,
      role: null,
      reason: "control_session_unreachable",
    };
  }
}
