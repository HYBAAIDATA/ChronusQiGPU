import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, apiUrl } from "@/lib/api";
import { createMockResponse, createMockUser, setupTestDB } from "@/test/helpers";

afterEach(() => {
  vi.restoreAllMocks();
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
