import { afterEach, describe, expect, it, vi } from "vitest";
import {
  parseCapabilities,
  parseJob,
  parseProgram,
  request,
  ServiceError,
} from "./client";
const program = {
  n_qubits: 2,
  operations: [
    { gate: "h", qubits: [0] },
    { gate: "cx", qubits: [0, 1] },
  ],
};
const envelope = {
  schema_version: "turing.workspace.v1",
  persistence: "in_memory_process_local",
  service_mode: "technical_evaluation_only",
};
afterEach(() => vi.unstubAllGlobals());
describe("TURING workspace contracts", () => {
  it("parses a native input without calculating a result", () =>
    expect(parseProgram(JSON.stringify(program))).toEqual(program));
  it.each([true, "2", 0, 13, 1.5])("refuses invalid widths: %s", (width) =>
    expect(() =>
      parseProgram(JSON.stringify({ ...program, n_qubits: width })),
    ).toThrow(),
  );
  it.each([
    { gate: "rx", qubits: [0] },
    { gate: "h", qubits: [true] },
    { gate: "cx", qubits: [0, 0] },
    { gate: "h", qubits: [2] },
  ])("refuses unsupported operations: %s", (op) =>
    expect(() =>
      parseProgram(JSON.stringify({ n_qubits: 2, operations: [op] })),
    ).toThrow(),
  );
  it("rejects extra engine configuration", () =>
    expect(() =>
      parseProgram(JSON.stringify({ ...program, shots: 100 })),
    ).toThrow());
  it("does not invent missing reports", () =>
    expect(() =>
      parseJob({
        job_id: "j",
        status: "succeeded",
        submitted_at: new Date().toISOString(),
        program,
      }),
    ).toThrow(ServiceError));
  it("does not accept invented lifecycle states", () =>
    expect(() =>
      parseJob({
        job_id: "j",
        status: "completed",
        submitted_at: new Date().toISOString(),
        program,
      }),
    ).toThrow());
  it("keeps returned evidence intact", () => {
    const report = { fixture: true, opaque_evidence: [1, 2] };
    expect(
      parseJob({
        job_id: "j",
        status: "succeeded",
        submitted_at: new Date().toISOString(),
        program,
        report,
      }).report,
    ).toBe(report);
  });
  it("rejects an unexpected capability envelope", () =>
    expect(() =>
      parseCapabilities({ max_qubits: 99999, gates: [] }),
    ).toThrow());
  it("uses same-origin in-memory credentials and no automatic resubmission", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ ...envelope }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetcher);
    await request(
      { tenant: "tenant", actor: "actor", token: "fixture-not-a-secret" },
      { action: "capabilities" },
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    const [path, init] = fetcher.mock.calls[0];
    expect(path).toBe("/api/v1/quantum/workspace");
    expect(init.credentials).toBe("omit");
    expect(init.redirect).toBe("error");
    expect(init.headers.Authorization).toBe("Bearer fixture-not-a-secret");
  });
  it("treats interrupted submission as unknown, not failed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network")));
    await expect(
      request(
        { tenant: "a", actor: "b", token: "fixture" },
        { action: "submit", program, idempotency_key: "same-key" },
      ),
    ).rejects.toMatchObject({ uncertain: true });
  });
  it("distinguishes refusal from uncertain service failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"error":"native_admission_refused"}', { status: 422 }),
        ),
    );
    await expect(
      request(
        { tenant: "a", actor: "b", token: "fixture" },
        { action: "capabilities" },
      ),
    ).rejects.toMatchObject({ uncertain: false });
  });
});
