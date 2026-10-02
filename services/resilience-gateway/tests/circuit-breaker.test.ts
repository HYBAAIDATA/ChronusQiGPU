import assert from "node:assert/strict";
import test from "node:test";
import { CircuitBreaker } from "../src/resilience/circuit-breaker.js";

test("half-open allows one concurrent probe", async () => {
  const breaker = new CircuitBreaker({
    name: "test",
    failureThreshold: 1,
    successThreshold: 1,
    timeout: 100,
    resetTimeout: 20,
    halfOpenMaxConcurrent: 1,
  });
  await breaker.execute(
    async () => {
      throw new Error("boom");
    },
    async () => "fallback",
  );
  await new Promise((resolve) => setTimeout(resolve, 25));
  let operations = 0;
  const results = await Promise.all(
    Array.from({ length: 20 }, () =>
      breaker.execute(
        async () => {
          operations++;
          await new Promise((resolve) => setTimeout(resolve, 10));
          return "origin";
        },
        async () => "fallback",
      ),
    ),
  );
  assert.equal(operations, 1);
  assert.equal(results.filter((value) => value === "fallback").length, 19);
  assert.equal(breaker.metrics.halfOpenRejections, 19);
  assert.equal(breaker.currentState, "CLOSED");
});

test("timeout is counted and opens the circuit", async () => {
  const breaker = new CircuitBreaker({
    name: "slow",
    failureThreshold: 1,
    successThreshold: 1,
    timeout: 5,
    resetTimeout: 100,
    halfOpenMaxConcurrent: 1,
  });
  const result = await breaker.execute(
    () => new Promise<string>(() => {}),
    async (error) => error.message,
  );
  assert.match(result, /timeout/);
  assert.equal(breaker.metrics.timeouts, 1);
  assert.equal(breaker.currentState, "OPEN");
});