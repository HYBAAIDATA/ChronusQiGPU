import { it, expect, vi } from "vitest";
import {
  INTEGRATIONS,
  integrationBoundary,
  IntegrationUnavailable,
} from "./integrations";
it("never invents an external backend, customer data or operational service", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  try {
    for (const i of INTEGRATIONS) {
      const boundary = integrationBoundary(i.id);
      expect(boundary.availability).toBe("unavailable");
      await expect(boundary.invoke()).rejects.toBeInstanceOf(
        IntegrationUnavailable,
      );
    }
    expect(fetch).not.toHaveBeenCalled();
  } finally {
    vi.unstubAllGlobals();
  }
});
