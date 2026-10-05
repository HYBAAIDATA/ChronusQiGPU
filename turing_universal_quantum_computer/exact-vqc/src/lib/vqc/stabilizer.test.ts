import assert from "node:assert/strict";
import { test } from "node:test";
import { StabilizerState } from "./stabilizer.ts";

test("random stabilizer measurement preserves the canonical symplectic basis", () => {
  const state = new StabilizerState(6);
  state.h(0).h(2).h(4);
  state.cnot(0, 1).cnot(2, 3).cnot(4, 5);
  state.s(1).sdg(3).x(5);
  state.validateInvariants();

  for (const [qubit, outcome] of [
    [0, 1],
    [2, 0],
    [4, 1],
  ] as const) {
    const record = state.measure(qubit, outcome);
    assert.equal(record.outcome, outcome);
    state.validateInvariants();
  }
});

test("Bell-pair collapse supports both exact branches", () => {
  for (const outcome of [0, 1] as const) {
    const state = new StabilizerState(2);
    state.h(0).cnot(0, 1);
    const [p0, p1] = state.measurementProbabilities(0);
    assert.deepEqual([p0.n, p0.d, p1.n, p1.d], [1n, 2n, 1n, 2n]);
    const record = state.measure(0, outcome);
    assert.equal(record.random, true);
    assert.equal(record.outcome, outcome);
    state.validateInvariants();
    assert.equal(state.expectationZ(0), outcome === 0 ? "1" : "-1");
    assert.equal(state.expectationZ(1), outcome === 0 ? "1" : "-1");
  }
});

test("deterministic measurement rejects the impossible branch", () => {
  const state = new StabilizerState(1);
  state.x(0);
  assert.throws(() => state.measure(0, 0), /deterministic measurement outcome is 1/);
  const record = state.measure(0, 1);
  assert.equal(record.random, false);
  assert.equal(record.outcome, 1);
  state.validateInvariants();
});
