import assert from "node:assert/strict";
import test from "node:test";
import { withRetry } from "../src/resilience/retry.js";

test("retry jitter never undercuts exponential delay", async () => {
  const delays: number[] = [];
  let calls = 0;
  const result = await withRetry(
    async () => {
      calls++;
      if (calls < 3) throw new Error("503");
      return "ok";
    },
    {
      maxAttempts: 3,
      initialDelayMs: 100,
      maxDelayMs: 1_000,
      backoffMultiplier: 2,
      jitterFactor: 0.2,
      isRetryable: () => true,
      random: () => 0,
      sleep: async (delay) => {
        delays.push(delay);
      },
    },
  );
  assert.equal(result, "ok");
  assert.deepEqual(delays, [100, 200]);
});