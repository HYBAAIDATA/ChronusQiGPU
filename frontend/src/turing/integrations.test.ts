import { it, expect, vi } from "vitest";
import {
  INTEGRATIONS,
  BILLING_POLICY,
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

it("keeps billing on hold without a Hermitten dependency", () => {
  expect(BILLING_POLICY).toEqual({
    model: "usage_based",
    state: "on_hold",
    hermittenIntegration: false,
  });
  const billing = INTEGRATIONS.find((i) => i.id === "billing")!;
  expect(billing.capability).toBe("Billing — on hold");
  expect(billing.needs).toContain("no billing service is connected");
  expect(billing.owner).not.toBe("Hermitten");
});
