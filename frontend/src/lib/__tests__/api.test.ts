import { afterEach, describe, expect, it, vi } from "vitest";
import {
  apiFetch,
  apiUrl,
  operatorKey,
  operatorPrincipal,
  setOperatorKey,
  setOperatorPrincipal,
  setSubscriptionCreds,
  subscriptionCreds,
} from "@/lib/api";
import { createMockResponse, createMockUser, setupTestDB } from "@/test/helpers";

afterEach(() => {
  vi.restoreAllMocks();
  setOperatorKey(null);
  setOperatorPrincipal(null);
  setSubscriptionCreds(null);
  window.sessionStorage.clear();
});

describe("apiUrl", () => {
  it("keeps absolute URLs unchanged", () => {
    expect(apiUrl("https://api.example.invalid/healthz")).toBe("https://api.example.invalid/healthz");
  });

  it("normalizes a relative control-plane path", () => {
    expect(apiUrl("/api/v1/readyz")).toBe("/api/v1/readyz");
  });

  it("accepts an empty path without inventing a route", () => {
    expect(apiUrl("")).toBe("");
  });
});

describe("apiFetch", () => {
  it("fetches a relative route with copied headers", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createMockResponse({ ready: true }),
    );

    const response = await apiFetch("/readyz", {
      headers: { "x-test-request": "unit" },
    });

    expect(response.ok).toBe(true);
    expect(await response.json()).toEqual({ ready: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "/readyz",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    const requestInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(requestInit.headers).get("x-test-request")).toBe("unit");
  });

  it("propagates transport errors instead of fabricating a response", async () => {
    const error = new Error("offline");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(error);
    await expect(apiFetch("/healthz")).rejects.toBe(error);
  });

  it("uses the shared offline factories without Firebase or a real database", () => {
    const user = createMockUser({ id: "u-42", roles: ["viewer"] });
    const db = setupTestDB({ user });
    expect(db.get<typeof user>("user")?.id).toBe("u-42");
    expect(db.entries()).toHaveLength(1);
  });
});

describe("HttpOnly operator session migration", () => {
  it("clears stale operator bearers rather than storing new secrets", () => {
    window.sessionStorage.setItem("pythia.operatorKey", "stale-fixture");
    expect(operatorKey()).toBeNull();
    setOperatorKey("new-fixture");
    expect(operatorKey()).toBeNull();
    expect(window.sessionStorage.getItem("pythia.operatorKey")).toBeNull();
  });
  it("uses cookies without an operator bearer on mutations", async () => {
    setOperatorKey("not-a-grant");
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    await apiFetch("/api/v1/agentic/start", {method:"POST",body:"{}"});
    const init = mock.mock.calls[0]![1] as RequestInit;
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("Authorization")).toBeNull();
  });
  it("returns 401 without retrying or prompting for a JS-readable bearer", async () => {
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({error:"SESSION_REQUIRED"},{status:401}));
    const prompt = vi.spyOn(window, "prompt");
    expect((await apiFetch("/api/v1/config",{method:"PUT",body:"{}"})).status).toBe(401);
    expect(mock).toHaveBeenCalledTimes(1);
    expect(prompt).not.toHaveBeenCalled();
  });
});

describe("subscription boundary", () => {
  const headers = (call: unknown[]) => new Headers((call[1] as RequestInit).headers);

  it("sends the subscription triple and injects observation on privileged POSTs", async () => {
    setSubscriptionCreds({ tenant: "t-1", actor: "op-1", token: "tok-1" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(createMockResponse({ ok: true }));
    await apiFetch("/api/v1/mining/start", { method: "POST", body: "{}" });
    const sent = headers(fetchMock.mock.calls[0]!);
    expect(sent.get("X-HYBA-Tenant")).toBe("t-1");
    expect(sent.get("X-HYBA-Actor")).toBe("op-1");
    expect(sent.get("Authorization")).toBe("Bearer tok-1");
    const body = JSON.parse(String((fetchMock.mock.calls[0]![1] as RequestInit).body));
    expect(body.observation.actor).toBe("op-1");
    expect(body.observation.ui).toBe("operator-console");
  });

  it("keeps subscription headers on privileged GETs without a body", async () => {
    setSubscriptionCreds({ tenant: "t-1", actor: "op-1", token: "tok-1" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(createMockResponse({ evidence: [] }));
    await apiFetch("/api/v1/mining/evidence");
    const sent = headers(fetchMock.mock.calls[0]!);
    expect(sent.get("Authorization")).toBe("Bearer tok-1");
    expect(sent.get("X-HYBA-Tenant")).toBe("t-1");
  });

  it("asks for creds on TENANT_AND_ACTOR_REQUIRED, retries, keeps them", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        createMockResponse({ reason: "TENANT_AND_ACTOR_REQUIRED" }, { status: 400 }),
      )
      .mockResolvedValueOnce(createMockResponse({ ok: true }));
    const prompt = vi
      .spyOn(window, "prompt")
      .mockReturnValueOnce("tok-2")
      .mockReturnValueOnce("t-2")
      .mockReturnValueOnce("op-2");
    const response = await apiFetch("/api/v1/mining/stop", { method: "POST", body: "{}" });
    expect(response.ok).toBe(true);
    expect(prompt).toHaveBeenCalledTimes(3);
    const retry = headers(fetchMock.mock.calls[1]!);
    expect(retry.get("Authorization")).toBe("Bearer tok-2");
    expect(retry.get("X-HYBA-Tenant")).toBe("t-2");
    expect(subscriptionCreds()).toEqual({ tenant: "t-2", actor: "op-2", token: "tok-2" });
  });

  it("returns the denial when the operator cancels the cred prompt", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createMockResponse({ allowed: false }, { status: 402 }),
    );
    vi.spyOn(window, "prompt").mockReturnValue(null);
    const response = await apiFetch("/api/v1/mining/evidence");
    expect(response.status).toBe(402);
    expect(subscriptionCreds()).toBeNull();
  });

  it("does not re-prompt on every denied poll after declining", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createMockResponse({ allowed: false }, { status: 402 }),
    );
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(null);
    await apiFetch("/api/v1/mining/evidence");
    await apiFetch("/api/v1/mining/evidence");
    const response = await apiFetch("/api/v1/mining/evidence");
    expect(response.status).toBe(402);
    expect(prompt).toHaveBeenCalledTimes(1);
  });
});


describe("console read boundaries", () => {
  it("carries HttpOnly sessions on protected console reads", async () => {
    setOperatorKey("control-test-only"); setOperatorPrincipal("owner");
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    for (const path of ["/api/v1/mla1517/status", "/api/v1/config", "/api/v1/telemetry/summary", "/api/v1/audit/tail"]) {
      await apiFetch(path, {}, {interactive:false});
    }
    for (const call of mock.mock.calls) {
      const h = new Headers((call[1] as RequestInit).headers);
      expect(h.get("Authorization")).toBeNull();
      expect((call[1] as RequestInit).credentials).toBe("include");
      expect(h.get("X-PYTHIA-Principal")).toBe("owner");
    }
  });
  it("keeps CEO and guardian subscription credentials independent", async () => {
    setOperatorKey("control-test-only"); setOperatorPrincipal("owner");
    setSubscriptionCreds({tenant:"tenant-test", actor:"actor-test", token:"subscription-test-only"});
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    await apiFetch("/api/v1/mining/evidence", {}, {interactive:false});
    const h = new Headers((mock.mock.calls[0]![1] as RequestInit).headers);
    expect(h.get("X-PYTHIA-Control-Authorization")).toBeNull();
    expect((mock.mock.calls[0]![1] as RequestInit).credentials).toBe("include");
    expect(h.get("X-PYTHIA-Principal")).toBe("owner");
    expect(h.get("Authorization")).toBe("Bearer subscription-test-only");
    expect(h.get("X-HYBA-Tenant")).toBe("tenant-test");
    expect(h.get("X-HYBA-Actor")).toBe("actor-test");
  });
  it("never opens credential prompts or retries denied background polls", async () => {
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({reason:"TENANT_AND_ACTOR_REQUIRED"}, {status:403}));
    const prompt = vi.spyOn(window, "prompt");
    expect((await apiFetch("/api/v1/mining/evidence", {}, {interactive:false})).status).toBe(403);
    expect(mock).toHaveBeenCalledTimes(1); expect(prompt).not.toHaveBeenCalled();
  });
});
