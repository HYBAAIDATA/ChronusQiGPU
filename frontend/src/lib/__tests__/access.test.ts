import { beforeEach, describe, expect, it, vi } from "vitest";
import { miningDashboardAccess } from "../access";
import {
  setOperatorKey,
  setOperatorPrincipal,
} from "../api";

describe("miningDashboardAccess", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    setOperatorKey(null);
    setOperatorPrincipal(null);
  });

  it("fails closed when no trusted control credentials are present", async () => {
    const fetchMock = vi.fn();
    const access = await miningDashboardAccess(fetchMock as typeof fetch);
    expect(access.allowed).toBe(false);
    expect(access.reason).toBe("trusted_control_identity_unavailable");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("allows only a server-confirmed CEO bound to the same principal", async () => {
    setOperatorKey("secret");
    setOperatorPrincipal("andre");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      expect(headers.get("Authorization")).toBe("Bearer secret");
      expect(headers.get("X-PYTHIA-Principal")).toBe("andre");
      return new Response(
        JSON.stringify({ principal_id: "andre", role: "ceo" }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    });
    const access = await miningDashboardAccess(fetchMock as typeof fetch);
    expect(access).toEqual({
      allowed: true,
      principalId: "andre",
      role: "ceo",
      reason: "authorized",
    });
  });

  it("denies an authenticated operator and a mismatched CEO identity", async () => {
    setOperatorKey("secret");
    setOperatorPrincipal("andre");

    const operator = vi.fn(async () =>
      new Response(JSON.stringify({ principal_id: "andre", role: "operator" }), {
        status: 200,
      }),
    );
    expect((await miningDashboardAccess(operator as typeof fetch)).reason).toBe(
      "ceo_role_required",
    );

    const mismatch = vi.fn(async () =>
      new Response(JSON.stringify({ principal_id: "someone-else", role: "ceo" }), {
        status: 200,
      }),
    );
    expect((await miningDashboardAccess(mismatch as typeof fetch)).reason).toBe(
      "control_identity_mismatch",
    );
  });

  it("treats a missing control entitlement endpoint as unavailable", async () => {
    setOperatorKey("secret");
    setOperatorPrincipal("andre");
    const fetchMock = vi.fn(async () => new Response("not found", { status: 404 }));
    const access = await miningDashboardAccess(fetchMock as typeof fetch);
    expect(access.allowed).toBe(false);
    expect(access.reason).toBe("control_session_entitlement_unavailable");
  });
});
