import { apiUrl } from "./api";

export interface MiningDashboardAccess {
  allowed: boolean;
  principalId: string | null;
  role: string | null;
  reason: string;
}

/** The HttpOnly session, not browser storage, supplies identity and authority. */
export async function miningDashboardAccess(
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<MiningDashboardAccess> {
  const denied = (reason: string): MiningDashboardAccess => ({
    allowed: false, principalId: null, role: null, reason,
  });
  try {
    const response = await fetchImpl(apiUrl("/api/v1/control/session"), {
      method: "GET", signal, cache: "no-store", credentials: "include",
    });
    if (!response.ok) return denied(response.status === 404
      ? "control_session_entitlement_unavailable" : "control_session_not_authorized");
    const body: unknown = await response.json();
    if (!body || typeof body !== "object" || Array.isArray(body)) return denied("invalid_control_session");
    const session = body as { principal_id?: unknown; role?: unknown };
    const principalId = typeof session.principal_id === "string" ? session.principal_id : null;
    const role = typeof session.role === "string" ? session.role : null;
    if (!principalId?.trim() || !role) return denied("invalid_control_session");
    // control_api maps founder_ceo to this canonical role after authentication.
    if (role !== "ceo") return { allowed: false, principalId, role, reason: "ceo_role_required" };
    return { allowed: true, principalId, role, reason: "authorized" };
  } catch {
    return denied("control_session_unreachable");
  }
}
