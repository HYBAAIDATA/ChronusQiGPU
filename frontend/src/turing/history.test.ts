import { describe, expect, it, vi, afterEach } from "vitest";
import { parseJobPage, request, ServiceError } from "./client";
const record = {
  job_id: "job-1",
  status: "queued",
  submitted_at: "2026-10-19T15:00:00Z",
  n_qubits: 2,
  operation_count: 2,
};
const page = {
  jobs: [record],
  offset: 0,
  limit: 10,
  total_matching: 1,
  total_retained: 1,
  next_offset: null,
  observed_at: "2026-10-19T15:00:01Z",
};
describe("retained execution history", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("accepts metadata without returning a fabricated report", () => {
    expect(parseJobPage(page).jobs[0]).toEqual(record);
    expect(parseJobPage(page).jobs[0]).not.toHaveProperty("report");
  });
  it("allows a genuinely empty current-process page", () => {
    expect(
      parseJobPage({ ...page, jobs: [], total_matching: 0, total_retained: 0 })
        .jobs,
    ).toEqual([]);
  });
  it.each([
    { offset: -1 },
    { limit: 21 },
    { total_matching: 2 },
    { observed_at: "yesterday" },
    { next_offset: 3 },
    { jobs: [{ ...record, status: "completed" }] },
    { jobs: [{ ...record, n_qubits: 13 }] },
    { jobs: [{ ...record, operation_count: true }] },
    { jobs: [{ ...record, submitted_at: "invalid" }] },
    { jobs: {} },
  ])("rejects malformed page %#", (fields) =>
    expect(() => parseJobPage({ ...page, ...fields })).toThrow(ServiceError),
  );
  it("preserves auth-denial status for a safe reconnection journey", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: "subscription_expired" }), {
            status: 403,
          }),
      ),
    );
    await expect(
      request(
        { tenant: "tenant", actor: "actor", token: "fixture-not-a-secret" },
        { action: "list" },
      ),
    ).rejects.toMatchObject({ httpStatus: 403, uncertain: false });
  });
});
