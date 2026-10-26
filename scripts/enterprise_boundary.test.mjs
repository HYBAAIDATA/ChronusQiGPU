/** UI adapter doubles only. No HTTP, installed-engine or production acceptance. */
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  WorkflowBoundary,
  BoundaryError,
  checkedOutcome,
  verifiedRestore,
} from "../frontend/src/enterprise/boundary.ts";
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
const scope = (tenant = "alpha", ttl = 60_000) => ({
  principal: "fixture-principal",
  tenant,
  authorizationRevision: "fixture-1",
  expiresAt: Date.now() + ttl,
});
const outcome = (extra = {}) => ({
  recordId: "fixture-record",
  candidate: "fixture-candidate-NOT-runtime-evidence",
  profile: "fixture-profile",
  storeId: "fixture-store",
  sourceDigest: "a".repeat(64),
  restoredDigest: "a".repeat(64),
  exactness: "EXACT",
  custody: "durable",
  reconstruction: "pass",
  restart: "not_run",
  evidenceClass: "measured",
  evidence: { fixture: true },
  ...extra,
});
const port = (extra = {}) => ({
  connect: async (tenant) => scope(tenant),
  backup: async () => outcome(),
  restore: async () => outcome(),
  ...extra,
});
const setup = async (t, p = port(), timeout = 1000) => {
  const b = new WorkflowBoundary(p, timeout);
  t.after(() => b.dispose());
  await b.connect("alpha");
  return b;
};
test("unbound client never executes", async () => {
  const b = new WorkflowBoundary(null);
  await b.connect("alpha");
  await b.execute("restore", "r", "k");
  assert.equal(b.getSnapshot().phase, "unbound");
  b.dispose();
});
test("requires confirmed scope before execution", async (t) => {
  let calls = 0;
  const b = new WorkflowBoundary(
    port({
      restore: async () => {
        calls++;
        return outcome();
      },
    }),
  );
  t.after(() => b.dispose());
  await b.execute("restore", "r", "k");
  assert.equal(calls, 0);
});
test("tenant mismatch refused", async (t) => {
  const b = await setup(t, port({ connect: async () => scope("other") }));
  assert.equal(b.getSnapshot().phase, "denied");
  assert.equal(b.getSnapshot().scope, null);
});
test("expired scope refused", async (t) => {
  const b = await setup(t, port({ connect: async () => scope("alpha", -1) }));
  assert.equal(b.getSnapshot().phase, "denied");
});
test("empty principal refused", async (t) => {
  const b = await setup(
    t,
    port({ connect: async () => ({ ...scope(), principal: "" }) }),
  );
  assert.equal(b.getSnapshot().phase, "denied");
});
test("backup uses exact request key and adapter scope", async (t) => {
  let received;
  const b = await setup(
    t,
    port({
      backup: async (...args) => {
        received = args;
        return outcome({ reconstruction: "not_run", restoredDigest: null });
      },
    }),
  );
  const file = new File(["fixture"], "input.bin");
  await b.execute("backup", file, "key-1");
  assert.equal(received[0].tenant, "alpha");
  assert.equal(received[1], file);
  assert.equal(received[2], "key-1");
  assert.equal(b.getSnapshot().phase, "result");
  assert.equal(verifiedRestore(b.getSnapshot().outcome), false);
});
test("new tenant clears outcome synchronously and rejects old completion", async (t) => {
  const d = deferred();
  const b = await setup(t, port({ restore: () => d.promise }));
  const work = b.execute("restore", "r", "key");
  const next = b.connect("beta");
  assert.equal(b.getSnapshot().outcome, null);
  assert.equal(b.getSnapshot().scope, null);
  await next;
  d.resolve(outcome());
  await work;
  assert.equal(b.getSnapshot().scope.tenant, "beta");
  assert.equal(b.getSnapshot().outcome, null);
});
test("late connect cannot overwrite newer tenant", async (t) => {
  const d = deferred();
  const b = new WorkflowBoundary(
    port({
      connect: (tenant) =>
        tenant === "alpha" ? d.promise : Promise.resolve(scope(tenant)),
    }),
  );
  t.after(() => b.dispose());
  const old = b.connect("alpha");
  await b.connect("beta");
  d.resolve(scope("alpha"));
  await old;
  assert.equal(b.getSnapshot().scope.tenant, "beta");
});
test("logout aborts and cannot resurrect result", async (t) => {
  const d = deferred();
  let signal;
  const b = await setup(
    t,
    port({
      restore: (_s, _r, _k, s) => {
        signal = s;
        return d.promise;
      },
    }),
  );
  const work = b.execute("restore", "r", "key");
  b.clear();
  assert.equal(signal.aborted, true);
  assert.equal(b.getSnapshot().scope, null);
  d.resolve(outcome());
  await work;
  assert.equal(b.getSnapshot().outcome, null);
});
test("denial clears scope, data and request key", async (t) => {
  const b = await setup(
    t,
    port({
      restore: async () => {
        throw new BoundaryError("denied");
      },
    }),
  );
  await b.execute("restore", "r", "key");
  assert.equal(b.getSnapshot().phase, "denied");
  assert.equal(b.getSnapshot().scope, null);
  assert.equal(b.getSnapshot().requestKey, null);
});
test("unknown write retains request key but no protected result", async (t) => {
  const b = await setup(
    t,
    port({
      backup: async () => {
        throw new Error("secret internal error must not be displayed");
      },
    }),
  );
  await b.execute("backup", new File(["x"], "x"), "key-unknown");
  assert.equal(b.getSnapshot().phase, "unknown");
  assert.equal(b.getSnapshot().requestKey, "key-unknown");
  assert.equal(b.getSnapshot().scope, null);
  assert.ok(!b.getSnapshot().message.includes("secret"));
});
test("timeout is unknown and late callback is discarded", async (t) => {
  const d = deferred();
  const b = await setup(t, port({ restore: () => d.promise }), 10);
  await b.execute("restore", "r", "key-timeout");
  assert.equal(b.getSnapshot().phase, "unknown");
  d.resolve(outcome());
  await delay(5);
  assert.equal(b.getSnapshot().outcome, null);
});
test("expiry during work clears result and rejects callback", async (t) => {
  const d = deferred();
  const b = await setup(
    t,
    port({ connect: async () => scope("alpha", 20), restore: () => d.promise }),
  );
  const work = b.execute("restore", "r", "key");
  await delay(35);
  assert.equal(b.getSnapshot().phase, "expired");
  d.resolve(outcome());
  await work;
  assert.equal(b.getSnapshot().outcome, null);
});
test("double submit does not create concurrent writes", async (t) => {
  const d = deferred();
  let calls = 0;
  const b = await setup(
    t,
    port({
      restore: () => {
        calls++;
        return d.promise;
      },
    }),
  );
  const first = b.execute("restore", "r", "key1");
  await b.execute("restore", "r", "key2");
  assert.equal(calls, 1);
  d.resolve(outcome());
  await first;
});
test("invalid response becomes unknown, not zero or success", async (t) => {
  const b = await setup(
    t,
    port({ restore: async () => outcome({ sourceDigest: "invalid" }) }),
  );
  await b.execute("restore", "r", "key");
  assert.equal(b.getSnapshot().phase, "unknown");
  assert.equal(b.getSnapshot().outcome, null);
});
test("JSON-inspectable evidence is required", () => {
  const cycle = {};
  cycle.self = cycle;
  assert.throws(
    () => checkedOutcome(outcome({ evidence: cycle })),
    BoundaryError,
  );
  assert.throws(
    () => checkedOutcome(outcome({ evidence: { n: 1n } })),
    BoundaryError,
  );
});
test("digest mismatch cannot claim reconstruction pass", () => {
  assert.throws(
    () => checkedOutcome(outcome({ restoredDigest: "b".repeat(64) })),
    BoundaryError,
  );
});
test("memory-only, modeled and pending are not verified durable restore", () => {
  for (const value of [
    outcome({ custody: "memory_only" }),
    outcome({ evidenceClass: "modeled" }),
    outcome({ evidenceClass: "pending" }),
  ])
    assert.equal(verifiedRestore(checkedOutcome(value)), false);
});
test("unsupported exactness cannot be presented as verified restore", () => {
  assert.equal(
    verifiedRestore(checkedOutcome(outcome({ exactness: "UNSUPPORTED" }))),
    false,
  );
});
test("restart not run stays not run; no implicit restart qualification", async (t) => {
  const b = await setup(t);
  await b.execute("restore", "r", "key");
  assert.equal(b.getSnapshot().outcome.restart, "not_run");
});
test("export absent unless adapter explicitly supports it", async (t) => {
  const b = await setup(t);
  await b.execute("restore", "r", "key");
  assert.equal(b.canExport(), false);
  assert.equal(await b.exportEvidence(), null);
});
test("export reauthorizes and denial clears existing outcome", async (t) => {
  let calls = 0;
  const b = await setup(
    t,
    port({
      exportEvidence: async () => {
        calls++;
        throw new BoundaryError("denied");
      },
    }),
  );
  await b.execute("restore", "r", "key");
  assert.equal(b.canExport(), true);
  assert.equal(await b.exportEvidence(), null);
  assert.equal(calls, 1);
  assert.equal(b.getSnapshot().outcome, null);
  assert.equal(b.getSnapshot().phase, "denied");
});
test("export after scope change cannot download old evidence", async (t) => {
  const d = deferred();
  const b = await setup(t, port({ exportEvidence: () => d.promise }));
  await b.execute("restore", "r", "key");
  const exp = b.exportEvidence();
  await b.connect("beta");
  d.resolve(new Blob(["fixture"]));
  assert.equal(await exp, null);
  assert.equal(b.getSnapshot().scope.tenant, "beta");
});
test("successful evidence export returns exact service blob", async (t) => {
  const blob = new Blob(["fixture"], { type: "application/json" });
  const b = await setup(t, port({ exportEvidence: async () => blob }));
  await b.execute("restore", "r", "key");
  assert.equal(await b.exportEvidence(), blob);
  assert.equal(b.getSnapshot().phase, "result");
});
test("notifies subscribers only with cleared protected data on logout", async (t) => {
  const b = await setup(t);
  await b.execute("restore", "r", "key");
  const seen = [];
  const unsubscribe = b.subscribe(() => seen.push(b.getSnapshot()));
  b.clear();
  unsubscribe();
  assert.equal(seen.length, 1);
  assert.equal(seen[0].scope, null);
  assert.equal(seen[0].outcome, null);
});
