import assert from "node:assert/strict";
import test from "node:test";
import {
  executeIdempotently,
  MemoryIdempotencyStore,
} from "../src/http.js";
import { parseW3cTraceparent, withTrace, currentTraceparent } from "../src/observability.js";

test("concurrent idempotency claims execute the operation exactly once", async () => {
  const store = new MemoryIdempotencyStore();
  let executions = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const operation = async () => {
    executions++;
    await gate;
    return { status: 200, body: '{"charged":true}' };
  };
  const first = executeIdempotently(store, "charge-1", operation);
  await new Promise((resolve) => setImmediate(resolve));
  const second = await executeIdempotently(store, "charge-1", operation);
  assert.equal(second.state, "pending");
  release();
  assert.equal((await first).state, "executed");
  assert.equal(executions, 1);
  const replay = await executeIdempotently(store, "charge-1", operation);
  assert.equal(replay.state, "replayed");
  assert.equal(executions, 1);
});

test("W3C traceparent is validated and propagated", async () => {
  const incoming =
    "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01";
  assert.equal(
    parseW3cTraceparent(incoming)?.traceId,
    "4bf92f3577b34da6a3ce929d0e0e4736",
  );
  const outgoing = await withTrace(
    "test",
    async () => currentTraceparent(),
    incoming,
  );
  assert.match(
    outgoing ?? "",
    /^00-4bf92f3577b34da6a3ce929d0e0e4736-[0-9a-f]{16}-01$/,
  );
  assert.equal(
    parseW3cTraceparent(`00-${"0".repeat(32)}-00f067aa0ba902b7-01`),
    null,
  );
});