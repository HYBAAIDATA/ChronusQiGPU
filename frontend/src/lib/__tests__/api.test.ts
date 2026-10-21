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

describe("operator key", () => {
  const bearer = (call: unknown[]) => new Headers((call[1] as RequestInit).headers).get("Authorization");

  it("does not send the key on unrelated public reads", async () => {
    setOperatorKey("k-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    await apiFetch("/readyz");
    expect(bearer(fetchMock.mock.calls[0]!)).toBeNull();
  });

  it("sends the session key on state-changing requests", async () => {
    setOperatorKey("k-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({ ok: true }));
    await apiFetch("/api/v1/mining/start", { method: "POST", body: "{}" });
    expect(bearer(fetchMock.mock.calls[0]!)).toBe("Bearer k-1");
  });

  it("asks once on 401, retries with the key and keeps it for the session", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(createMockResponse({ error: "operator key required" }, { status: 401 }))
      .mockResolvedValueOnce(createMockResponse({ ok: true }));
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(" k-2 ");
    const response = await apiFetch("/api/v1/agentic/start", { method: "POST", body: "{}" });
    expect(response.ok).toBe(true);
    expect(prompt).toHaveBeenCalledTimes(1);
    expect(bearer(fetchMock.mock.calls[1]!)).toBe("Bearer k-2");
    expect(operatorKey()).toBe("k-2");
  });

  it("binds a mapped principal to its bearer on retry", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        createMockResponse({ error: "operator principal required" }, { status: 401 }),
      )
      .mockResolvedValueOnce(createMockResponse({ ok: true }));
    vi.spyOn(window, "prompt")
      .mockReturnValueOnce("andre")
      .mockReturnValueOnce("ceo-token");
    const response = await apiFetch("/api/v1/agentic/start", {
      method: "POST",
      body: "{}",
    });
    expect(response.ok).toBe(true);
    const retry = new Headers((fetchMock.mock.calls[1]![1] as RequestInit).headers);
    expect(retry.get("Authorization")).toBe("Bearer ceo-token");
    expect(retry.get("X-PYTHIA-Principal")).toBe("andre");
    expect(operatorKey()).toBe("ceo-token");
    expect(operatorPrincipal()).toBe("andre");
  });

  it("forgets a refused key and returns the refusal when the operator cancels", async () => {
    setOperatorKey("stale");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createMockResponse({ error: "operator key required" }, { status: 401 }),
    );
    vi.spyOn(window, "prompt").mockReturnValue(null);
    const response = await apiFetch("/api/v1/config", { method: "PUT", body: "{}" });
    expect(response.status).toBe(401);
    expect(operatorKey()).toBeNull();
  });

  it("does not re-prompt after the operator declines once", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createMockResponse({ error: "operator key required" }, { status: 401 }),
    );
    const prompt = vi.spyOn(window, "prompt").mockReturnValue(null);
    await apiFetch("/api/v1/config", { method: "PUT", body: "{}" });
    const response = await apiFetch("/api/v1/config", { method: "PUT", body: "{}" });
    expect(response.status).toBe(401);
    expect(prompt).toHaveBeenCalledTimes(1);
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
  it("carries server-mapped control credentials on protected console reads", async () => {
    setOperatorKey("control-test-only"); setOperatorPrincipal("owner");
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    for (const path of ["/api/v1/mla1517/status", "/api/v1/config", "/api/v1/telemetry/summary", "/api/v1/audit/tail"]) {
      await apiFetch(path, {}, {interactive:false});
    }
    for (const call of mock.mock.calls) {
      const h = new Headers((call[1] as RequestInit).headers);
      expect(h.get("Authorization")).toBe("Bearer control-test-only");
      expect(h.get("X-PYTHIA-Principal")).toBe("owner");
    }
  });
  it("keeps CEO and guardian subscription credentials independent", async () => {
    setOperatorKey("control-test-only"); setOperatorPrincipal("owner");
    setSubscriptionCreds({tenant:"tenant-test", actor:"actor-test", token:"subscription-test-only"});
    const mock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    await apiFetch("/api/v1/mining/evidence", {}, {interactive:false});
    const h = new Headers((mock.mock.calls[0]![1] as RequestInit).headers);
    expect(h.get("X-PYTHIA-Control-Authorization")).toBe("Bearer control-test-only");
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
