import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import test from "node:test";
import { projectUsage } from "../src/sovereign/billing-projector.js";
import {
  InMemoryEventJournal,
  ProvenanceEventStore,
  type CommandEventInput,
} from "../src/sovereign/event-store.js";
import { evaluateExperiment } from "../src/sovereign/governance.js";
import { ShadowTenant } from "../src/sovereign/shadow-tenant.js";

function signedInput(
  overrides: Partial<CommandEventInput> = {},
): CommandEventInput {
  const keys = generateKeyPairSync("ed25519");
  const input: CommandEventInput = {
    tenantId: "tenant-1",
    type: "OUTCOME_VERIFIED",
    causalId: "request-1",
    actorId: "operator-1",
    actorPublicKeyPem: keys.publicKey.export({ type: "spki", format: "pem" }).toString(),
    actorSignatureBase64: "",
    occurredAt: "2026-10-01T17:00:00.000Z",
    payload: { boundary: "outcome", metric: "accepted_share", quantity: 1 },
    ...overrides,
  };
  input.actorSignatureBase64 = sign(
    null,
    ProvenanceEventStore.signingPayload(input),
    keys.privateKey,
  ).toString("base64");
  return input;
}

test("event stream verifies and outcome billing retains evidence hash", async () => {
  const store = new ProvenanceEventStore(new InMemoryEventJournal());
  const event = await store.append(signedInput());
  assert.equal(await store.verifyStream("tenant-1"), true);
  const usage = projectUsage(event);
  assert.equal(usage?.billable, true);
  assert.equal(usage?.evidenceHash, event.eventHash);
});

test("shadow tenant cannot write outbound", async () => {
  const events: unknown[] = [];
  const shadow = new ShadowTenant("shadow-1", "production-1", {
    append: async (event) => {
      events.push(event);
    },
  });
  await shadow.mirror({
    tenantId: "production-1",
    eventId: "evt-1",
    type: "STATE_CHANGED",
    payload: {},
  });
  shadow.injectShock("SUEZ_1956_LIQUIDITY_SHOCK", { reserveDelta: -0.25 });
  await shadow.flushShocks();
  assert.equal(events.length, 2);
  await assert.rejects(() => shadow.outboundWrite(), /severed/);
});

test("governance blocks output drift outside SLA", () => {
  const observations = [
    { arm: "A" as const, requestFingerprint: "r", outputFingerprint: "x", latencyMs: 10, maintainabilityIndex: 90 },
    { arm: "B" as const, requestFingerprint: "r", outputFingerprint: "y", latencyMs: 10, maintainabilityIndex: 90 },
    { arm: "C" as const, requestFingerprint: "r", outputFingerprint: "x", latencyMs: 10, maintainabilityIndex: 90 },
    { arm: "E" as const, requestFingerprint: "r", outputFingerprint: "x", latencyMs: 10, maintainabilityIndex: 90 },
  ];
  const decision = evaluateExperiment(observations, {
    minimumSamplesPerArm: 1,
    maximumOutputDrift: 0,
    maximumLatencyRegression: 0.1,
    minimumMaintainabilityIndex: 80,
  });
  assert.equal(decision.authorized, false);
  assert.ok(decision.reasons.some((reason) => reason.includes("B output drift")));
});