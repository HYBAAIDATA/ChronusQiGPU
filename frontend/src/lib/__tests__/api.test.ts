import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, apiUrl, operatorKey, setOperatorKey } from "@/lib/api";
import { createMockResponse, createMockUser, setupTestDB } from "@/test/helpers";

afterEach(() => {
  vi.restoreAllMocks();
  setOperatorKey(null);
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

  it("never sends the key on reads", async () => {
    setOperatorKey("k-1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(createMockResponse({}));
    await apiFetch("/api/v1/config");
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
    const response = await apiFetch("/api/v1/mining/stop", { method: "POST", body: "{}" });
    expect(response.ok).toBe(true);
    expect(prompt).toHaveBeenCalledTimes(1);
    expect(bearer(fetchMock.mock.calls[1]!)).toBe("Bearer k-2");
    expect(operatorKey()).toBe("k-2");
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
});
