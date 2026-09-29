import { describe, expect, it } from "vitest";
import { stratumAlert, stratumStages } from "@/lib/stratum";
import type { StratumStatus } from "@/lib/status";

function stage(status: StratumStatus, key: string) {
  return stratumStages(status).find((item) => item.key === key)?.state;
}

describe("Stratum evidence ladder", () => {
  it("does not display authorization from TCP state alone", () => {
    const status: StratumStatus = {
      evidence_available: true,
      primary: { transport: "CONNECTED", subscribed: false, authorized: false },
    };

    expect(stage(status, "connect")).toBe("complete");
    expect(stage(status, "subscribe")).toBe("active");
    expect(stage(status, "authorize")).toBe("idle");
  });

  it("does not display acceptance from submission alone", () => {
    const status: StratumStatus = {
      evidence_available: true,
      submission: {
        state: "REJECTED",
        last_result: "REJECTED",
        last_submit_at: 1,
      },
      counters: { submitted: 1, accepted: 0, rejected: 1 },
    };

    expect(stage(status, "submit")).toBe("complete");
    expect(stage(status, "accepted")).toBe("blocked");
  });

  it("surfaces unknown outcomes as a specific safety alert", () => {
    const status: StratumStatus = {
      evidence_available: true,
      primary: { transport: "CONNECTED" },
      submission: { state: "OUTCOME_UNKNOWN", last_result: "OUTCOME_UNKNOWN" },
    };

    expect(stratumAlert(status)).toBe("SUBMISSION OUTCOME UNKNOWN");
    expect(stage(status, "accepted")).toBe("blocked");
  });
});
