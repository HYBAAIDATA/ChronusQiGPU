import { useState, type FormEvent } from "react";
import {
  parseJobPage,
  type Command,
  type JobPage,
  type JobState,
} from "./client";

type Props = {
  execute: (command: Command) => Promise<Record<string, unknown>>;
  select: (id: string) => Promise<void>;
  busy: boolean;
};
/** No credentials, report payloads, synthetic usage totals or browser persistence. */
export default function History({ execute, select, busy }: Props) {
  const [page, setPage] = useState<JobPage | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<JobState | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function load(offset = 0) {
    setLoading(true);
    setError("");
    try {
      setPage(
        parseJobPage(
          await execute({
            action: "list",
            query,
            status: status || undefined,
            offset,
            limit: 10,
          }),
        ),
      );
    } catch (e) {
      // Filters changed or request failed: don't present stale rows as this query.
      setPage(null);
      setError(e instanceof Error ? e.message : "History unavailable.");
    } finally {
      setLoading(false);
    }
  }
  function filter(event: FormEvent) {
    event.preventDefault();
    void load();
  }
  return (
    <section
      className="t-card t-results"
      aria-labelledby="history-title"
      aria-busy={loading}
    >
      <p className="t-step">04 / Revisit</p>
      <h2 id="history-title">Your retained executions</h2>
      <p className="t-muted">
        Server-observed jobs for this tenant and actor only. This is
        process-local execution history, not an organisation-wide register,
        capacity inventory or billable usage statement.
      </p>
      <form className="t-history-filter" onSubmit={filter}>
        <label>
          Find a job identifier
          <input
            value={query}
            maxLength={128}
            disabled={loading || busy}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(null);
            }}
            type="search"
          />
        </label>
        <label>
          Job state
          <select
            aria-label="Job state"
            value={status}
            disabled={loading || busy}
            onChange={(e) => {
              setStatus(e.target.value as JobState | "");
              setPage(null);
            }}
          >
            <option value="">All native states</option>
            {["queued", "running", "succeeded", "failed", "cancelled"].map(
              (s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ),
            )}
          </select>
        </label>
        <button type="submit" disabled={loading || busy}>
          {loading ? "Reading history…" : "Refresh history"}
        </button>
      </form>
      {error && (
        <p className="t-alert" role="alert">
          {error}
        </p>
      )}
      {!page && !error && (
        <p className="t-small">
          Refresh to read current history. A server restart or different
          identity may make earlier jobs unavailable.
        </p>
      )}
      {page && (
        <>
          <p role="status">
            {page.total_matching} matching of {page.total_retained} retained
            executions. Observed{" "}
            <time dateTime={page.observed_at}>
              {new Date(page.observed_at).toLocaleString()}
            </time>
            .
          </p>
          {page.jobs.length === 0 ? (
            <p>
              No jobs match this query in the current server process. Submit a
              native program above or change your filters.
            </p>
          ) : (
            <ul className="t-history-list">
              {page.jobs.map((j) => (
                <li key={j.job_id}>
                  <div>
                    <code>{j.job_id}</code>
                    <p className="t-small">
                      <time dateTime={j.submitted_at}>
                        {new Date(j.submitted_at).toLocaleString()}
                      </time>{" "}
                      · {j.n_qubits} logical qubits · {j.operation_count}{" "}
                      operations
                    </p>
                  </div>
                  <span className="t-state">{j.status}</span>
                  <button
                    className="t-secondary"
                    disabled={loading || busy}
                    onClick={() => void select(j.job_id)}
                    aria-label={`Inspect job ${j.job_id}`}
                  >
                    Inspect
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="t-actions" aria-label="History pagination">
            <button
              className="t-secondary"
              disabled={loading || busy || page.offset === 0}
              onClick={() => void load(Math.max(0, page.offset - page.limit))}
            >
              Previous page
            </button>
            <button
              className="t-secondary"
              disabled={loading || busy || page.next_offset === null}
              onClick={() => void load(page.next_offset ?? 0)}
            >
              Next page
            </button>
          </div>
          <p className="t-small">
            Newest submissions first. State and totals are observations, not
            live guarantees. Refresh from the first page after a new submission.
          </p>
        </>
      )}
    </section>
  );
}
