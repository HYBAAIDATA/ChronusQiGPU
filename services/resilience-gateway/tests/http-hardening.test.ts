import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";
import {
  FixedWindowRateLimiter,
  HmacGatewayTicketVerifier,
  scopeTenantPath,
} from "../src/auth.js";
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

test("HTTP bearer tickets fail closed and retain tenant identity", async () => {
  const secret = "0123456789abcdef0123456789abcdef";
  const verifier = new HmacGatewayTicketVerifier(secret);
  const issue = (payload: Record<string, unknown>) => {
    const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
    const signature = createHmac("sha256", secret)
      .update(encoded)
      .digest("base64url");
    return `${encoded}.${signature}`;
  };
  const valid = issue({
    sub: "operator-1",
    tenantId: "tenant-1",
    exp: Math.floor(Date.now() / 1000) + 30,
  });
  assert.deepEqual(await verifier.verify(valid), {
    subject: "operator-1",
    tenantId: "tenant-1",
  });
  assert.equal(
    await verifier.verify(
      issue({
        sub: "operator-1",
        tenantId: "tenant-1",
        exp: Math.floor(Date.now() / 1000) - 1,
      }),
    ),
    null,
  );
  assert.equal(
    await new HmacGatewayTicketVerifier("short").verify(valid),
    null,
  );
});

test("HTTP rate limiter rejects the first request beyond the configured window", () => {
  const limiter = new FixedWindowRateLimiter(2, 1_000);
  assert.equal(limiter.consume("tenant-1:operator-1", 1_000).allowed, true);
  assert.equal(limiter.consume("tenant-1:operator-1", 1_100).allowed, true);
  const denied = limiter.consume("tenant-1:operator-1", 1_200);
  assert.equal(denied.allowed, false);
  assert.equal(denied.remaining, 0);
  assert.equal(limiter.consume("tenant-1:operator-1", 2_001).allowed, true);
});

test("dependency paths are scoped to the authenticated tenant", () => {
  assert.equal(
    scopeTenantPath("tenant-1", "/portfolio/open"),
    "/tenants/tenant-1/portfolio/open",
  );
  assert.throws(
    () => scopeTenantPath("tenant-1", "../tenant-2/secrets"),
    /invalid dependency path/,
  );
  assert.throws(
    () => scopeTenantPath("tenant-1", "/safe\\..\\tenant-2"),
    /invalid dependency path/,
  );
});
