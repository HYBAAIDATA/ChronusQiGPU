import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  isRecord,
  parseCapabilities,
  parseJob,
  parseProgram,
  request,
  ServiceError,
  type Command,
  type Capabilities,
  type Credentials,
  type Job,
  type Program,
} from "./client";
import "./workspace.css";
import History from "./History";
import Evidence, { returnedText } from "./Evidence";
import { downloadJson } from "./downloads";
const EXAMPLE = JSON.stringify(
  {
    n_qubits: 2,
    operations: [
      { gate: "h", qubits: [0] },
      { gate: "cx", qubits: [0, 1] },
    ],
  },
  null,
  2,
);
type Pending = { program: Program; key: string };
export default function TuringWorkspace() {
  const credentials = useRef<Credentials | null>(null);
  const boundIdentity = useRef<{ tenant: string; actor: string } | null>(null);
  const [connected, setConnected] = useState(false);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [raw, setRaw] = useState(EXAMPLE);
  const [review, setReview] = useState<Program | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelReview, setCancelReview] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = "TURING — Computational workspace";
  }, []);
  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = event.currentTarget,
      data = new FormData(form);
    const creds = {
      tenant: String(data.get("tenant") ?? "").trim(),
      actor: String(data.get("actor") ?? "").trim(),
      token: String(data.get("token") ?? "").trim(),
    };
    try {
      if (
        boundIdentity.current &&
        (pending || job) &&
        (creds.tenant !== boundIdentity.current.tenant ||
          creds.actor !== boundIdentity.current.actor)
      )
        throw new Error(
          "Reconnect with the same tenant and actor to preserve the retained execution context.",
        );
      const envelope = parseCapabilities(
        await request(creds, { action: "capabilities" }),
      );
      credentials.current = creds;
      boundIdentity.current = { tenant: creds.tenant, actor: creds.actor };
      setCapabilities(envelope);
      setConnected(true);
      form.reset();
      setNotice("Connected to the guarded technical-evaluation service.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection unavailable.");
    } finally {
      setBusy(false);
    }
  }
  function disconnect() {
    credentials.current = null;
    boundIdentity.current = null;
    setCancelReview(false);
    setConnected(false);
    setCapabilities(null);
    setJob(null);
    setReview(null);
    setPending(null);
    setRaw(EXAMPLE);
    setError("");
    setNotice(
      "Disconnected. In-memory credentials and displayed results cleared; server jobs are not cancelled.",
    );
  }
  async function execute(command: Command) {
    if (!credentials.current)
      throw new ServiceError("Reconnect to the evaluation service.");
    try {
      return await request(credentials.current, command);
    } catch (e) {
      if (
        e instanceof ServiceError &&
        (e.httpStatus === 401 || e.httpStatus === 403)
      ) {
        credentials.current = null;
        setConnected(false);
        setCapabilities(null);
        setNotice(
          "Access refused or expired. Reconnect with the same tenant and actor. Any retained request remains unresolved; no job is assumed stopped.",
        );
      }
      throw e;
    }
  }
  async function selectJob(id: string) {
    setBusy(true);
    setError("");
    setCancelReview(false);
    try {
      setJob(parseJob(await execute({ action: "status", job_id: id })));
      setTimeout(() => resultHeading.current?.focus(), 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Job unavailable.");
    } finally {
      setBusy(false);
    }
  }
  function prepare(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      setReview(parseProgram(raw));
      setTimeout(() => reviewHeading.current?.focus(), 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid native program.");
    }
  }
  async function submit(retained?: Pending) {
    if (!credentials.current || (!review && !retained)) return;
    const attempt = retained ?? { program: review!, key: crypto.randomUUID() };
    setPending(attempt);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = parseJob(
        await execute({
          action: "submit",
          program: attempt.program,
          idempotency_key: attempt.key,
        }),
      );
      setJob(response);
      setPending(null);
      setReview(null);
      setNotice(
        "The service acknowledged this job. Inspect status and provenance below.",
      );
      setTimeout(() => resultHeading.current?.focus(), 0);
    } catch (e) {
      const uncertain = !(e instanceof ServiceError) || e.uncertain;
      if (!uncertain && !retained) setPending(null);
      setError(
        (e instanceof Error ? e.message : "Submission unavailable.") +
          (uncertain || retained
            ? " Outcome unknown. Retry this same request key; do not create a new submission."
            : " The request was refused."),
      );
    } finally {
      setBusy(false);
    }
  }
  async function update(action: "status" | "cancel") {
    if (!credentials.current || !job) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = parseJob(await execute({ action, job_id: job.job_id }));
      setJob(next);
      setCancelReview(false);
      if (action === "cancel")
        setNotice(
          next.cancellation_accepted
            ? "Cancellation accepted before execution."
            : "Cancellation not accepted. Running native jobs cannot be forcibly stopped; refresh their status.",
        );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Status unavailable. Last confirmed state is shown.",
      );
    } finally {
      setBusy(false);
    }
  }
  function download() {
    if (!job?.report) return;
    downloadJson(job.report, `${job.job_id}.json`);
  }
  const pipelineReport =
    job?.report && isRecord(job.report.pipeline_report)
      ? job.report.pipeline_report
      : null;
  const result =
    pipelineReport && isRecord(pipelineReport.result)
      ? pipelineReport.result
      : null;
  const certificate = pipelineReport?.certificate;
  const running = job?.status === "queued" || job?.status === "running";
  return (
    <div className="turing">
      <a className="t-skip" href="#workspace-content">
        Skip to workspace
      </a>
      <header className="t-header">
        <a className="t-wordmark" href="/turing/product">
          TURING<span>Computational intelligence</span>
        </a>
        <nav className="t-nav" aria-label="Product navigation">
          <a href="/turing/product">Product</a>
          <a href="/turing/documentation">Documentation</a>
          <a href="/turing/security">Security</a>
        </nav>
        <span className="t-label">
          Technical evaluation · Not a production service
        </span>
      </header>
      <main id="workspace-content" className="t-main">
        <section className="t-intro">
          <p className="t-eyebrow">The computational workspace</p>
          <h1>
            From a precise question.
            <br />
            To an inspectable result.
          </h1>
          <p>
            Submit native mathematical programs to the existing TURING engine.
            Inspect the returned result, validation evidence and execution
            provenance in one place.
          </p>
        </section>
        <aside className="t-boundary">
          <strong>A bounded, honest starting point.</strong> This pilot retains
          jobs in one server process. A restart loses their history. It does not
          provision enterprise capacity, establish commercial entitlements or
          reconcile billing.
        </aside>
        {error && (
          <div className="t-alert" role="alert">
            <strong>Action needs attention</strong>
            <p>{error}</p>
          </div>
        )}
        <p className="t-announcement" role="status" aria-live="polite">
          {notice ||
            (connected
              ? "Service connection verified. Inputs still require native admission."
              : "No service connection. No computation has been submitted.")}
        </p>
        <div className="t-grid">
          <section className="t-card" aria-labelledby="connection-title">
            <p className="t-step">01 / Access</p>
            <h2 id="connection-title">Connect to your service</h2>
            <p className="t-muted">
              AL HARAS validates the tenant, actor and subscription on every
              request. This is a technical-evaluation connection, not enterprise
              SSO.
            </p>
            {!connected ? (
              <form onSubmit={connect} className="t-form">
                <label>
                  Tenant identifier
                  <input
                    name="tenant"
                    required
                    maxLength={128}
                    autoComplete="off"
                    disabled={busy}
                  />
                </label>
                <label>
                  Actor identifier
                  <input
                    name="actor"
                    required
                    maxLength={128}
                    autoComplete="off"
                    disabled={busy}
                  />
                </label>
                <label>
                  Subscription bearer
                  <input
                    name="token"
                    type="password"
                    required
                    autoComplete="off"
                    disabled={busy}
                  />
                </label>
                <p className="t-small">
                  Credentials remain in this tab's memory and are sent only to
                  the same-origin service. They are not saved in browser
                  storage.
                </p>
                <button disabled={busy} type="submit">
                  {busy ? "Connecting…" : "Connect to evaluation service"}
                </button>
              </form>
            ) : (
              <>
                <dl className="t-details">
                  <dt>Connection</dt>
                  <dd>Verified for this request boundary</dd>
                  <dt>Gate family</dt>
                  <dd>Native exact operations</dd>
                  <dt>Pilot admission limit</dt>
                  <dd>
                    {capabilities?.max_qubits} logical qubits /{" "}
                    {capabilities?.max_operations} operations
                  </dd>
                  <dt>Job retention</dt>
                  <dd>Process-local, bounded</dd>
                  <dt>Commercial status</dt>
                  <dd>Not integrated</dd>
                </dl>
                <button
                  className="t-secondary"
                  disabled={busy || pending !== null}
                  onClick={disconnect}
                >
                  Disconnect and clear this view
                </button>
              </>
            )}
          </section>
          <section className="t-card" aria-labelledby="program-title">
            <p className="t-step">02 / Define</p>
            <h2 id="program-title">Compose a native program</h2>
            <p className="t-muted">
              The example prepares a two-qubit Bell-state circuit. It is an
              editable input—not a precomputed result. The engine remains the
              authority for admission and execution.
            </p>
            <form onSubmit={prepare} className="t-form">
              <label htmlFor="native-program">Native program · JSON</label>
              <textarea
                id="native-program"
                spellCheck={false}
                rows={12}
                value={raw}
                onChange={(e) => {
                  setRaw(e.target.value);
                  setReview(null);
                }}
                disabled={busy || !!pending}
                aria-describedby="program-help"
                maxLength={32768}
              />
              <p id="program-help" className="t-small">
                Fixed native gates only. No continuous angles, dynamic control
                or silent approximation. Pilot limits are admission safeguards,
                not throughput guarantees.
              </p>
              <button type="submit" disabled={!connected || busy || !!pending}>
                Review execution request
              </button>
            </form>
            {review && !pending && (
              <section className="t-review" aria-labelledby="review-title">
                <h3 id="review-title" tabIndex={-1} ref={reviewHeading}>
                  Review before execution
                </h3>
                <p>
                  {review.n_qubits} logical qubits · {review.operations.length}{" "}
                  operations · exact native admission · no sampling requested.
                </p>
                <p>
                  No pricing estimate or commercial billing integration is
                  available. Execution consumes service resources.
                </p>
                <div className="t-actions">
                  <button disabled={busy} onClick={() => void submit()}>
                    Confirm and submit
                  </button>
                  <button
                    className="t-secondary"
                    disabled={busy}
                    onClick={() => setReview(null)}
                  >
                    Back to editing
                  </button>
                </div>
              </section>
            )}
            {pending && (
              <section className="t-review">
                <h3>Retained request</h3>
                <p>Recovery key</p>
                <code className="t-wrap">{pending.key}</code>
                <p>
                  Keep this key until the service acknowledges the job. A server
                  restart can erase process-local deduplication; confirm with
                  the operator before retrying after a restart.
                </p>
                <button
                  disabled={busy || !connected}
                  onClick={() => void submit(pending)}
                >
                  {busy
                    ? "Awaiting acknowledgement…"
                    : "Retry the same request"}
                </button>
              </section>
            )}
          </section>
        </div>
        <section className="t-card t-results" aria-labelledby="result-title">
          <div className="t-result-header">
            <div>
              <p className="t-step">03 / Inspect</p>
              <h2 id="result-title" tabIndex={-1} ref={resultHeading}>
                Result & execution evidence
              </h2>
            </div>
            {job && <span className="t-state">{job.status}</span>}
          </div>
          {!job ? (
            <div className="t-empty">
              <span className="t-empty-mark" aria-hidden="true">
                ∴
              </span>
              <h3>No execution evidence yet</h3>
              <p>
                Connect, review a valid program and submit it. Results appear
                only after the native service returns them.
              </p>
            </div>
          ) : (
            <>
              <dl className="t-details t-job-details">
                <dt>Job identifier</dt>
                <dd>
                  <code>{job.job_id}</code>
                </dd>
                <dt>Submitted</dt>
                <dd>
                  <time dateTime={job.submitted_at}>
                    {new Date(job.submitted_at).toLocaleString()}
                  </time>
                </dd>
                <dt>Last confirmed state</dt>
                <dd>{job.status} · refresh to check current state</dd>
                {result && (
                  <>
                    <dt>Result truth class</dt>
                    <dd>
                      {typeof result.truth_class === "string"
                        ? result.truth_class
                        : "Not supplied"}
                    </dd>
                    <dt>Backend</dt>
                    <dd>
                      {typeof result.backend === "string"
                        ? result.backend
                        : "Not supplied"}
                    </dd>
                  </>
                )}
              </dl>
              <div className="t-actions">
                <button
                  disabled={busy || !connected}
                  className="t-secondary"
                  onClick={() => void update("status")}
                >
                  Refresh job status
                </button>
                {running && (
                  <button
                    disabled={busy || !connected}
                    className="t-secondary"
                    onClick={() => setCancelReview(true)}
                  >
                    Request cancellation
                  </button>
                )}
                {job.report && (
                  <button className="t-secondary" onClick={download}>
                    Download returned report
                  </button>
                )}
              </div>
              {cancelReview && running && (
                <section className="t-review" aria-labelledby="cancel-title">
                  <h3 id="cancel-title">Confirm cancellation request</h3>
                  <p>
                    Cancellation can stop a queued job only. A running native
                    execution may finish; this does not reverse consumed
                    resources or resolve billing.
                  </p>
                  <div className="t-actions">
                    <button
                      disabled={busy || !connected}
                      onClick={() => void update("cancel")}
                    >
                      Confirm cancellation request
                    </button>
                    <button
                      className="t-secondary"
                      disabled={busy}
                      onClick={() => setCancelReview(false)}
                    >
                      Keep execution
                    </button>
                  </div>
                </section>
              )}
              <details className="t-input-summary">
                <summary>Submitted input and effective pilot limits</summary>
                <p>
                  Width: {job.program.n_qubits}. Operations:{" "}
                  {job.program.operations.length}. Server admission: 12 logical
                  qubits / 256 operations / 4,096 amplitudes. Backend selection
                  and validation remain native-engine decisions; inspect the
                  returned configuration.
                </p>
                <pre tabIndex={0} aria-label="Submitted native program">
                  {JSON.stringify(job.program, null, 2)}
                </pre>
              </details>
              {job.error && (
                <p className="t-alert" role="alert">
                  {job.error}. No successful result is asserted.
                </p>
              )}
              {job.report && (
                <>
                  <p className="t-muted">
                    The report below is returned by the native facade, including
                    its configuration, implementation hash and canonical
                    pipeline evidence. Its presence is not independent
                    certification or enterprise custody acceptance.
                  </p>
                  <Evidence report={job.report} />
                  <div className="t-evidence">
                    <h3>Returned provenance</h3>
                    <dl className="t-details">
                      <dt>Artifact hash</dt>
                      <dd>
                        <code>{returnedText(job.report.artifact_hash)}</code>
                      </dd>
                      <dt>Implementation hash</dt>
                      <dd>
                        <code>
                          {returnedText(job.report.implementation_hash)}
                        </code>
                      </dd>
                      <dt>Certificate</dt>
                      <dd>
                        {certificate
                          ? "Returned by native pipeline; inspect report"
                          : "Not supplied"}
                      </dd>
                    </dl>
                    <pre tabIndex={0} aria-label="Native execution report">
                      {JSON.stringify(job.report, null, 2)}
                    </pre>
                  </div>
                </>
              )}
            </>
          )}
        </section>
        {connected && (
          <History execute={execute} select={selectJob} busy={busy} />
        )}
        <section className="t-next">
          <h2>What this pilot does—and does not do.</h2>
          <div>
            <p>
              <strong>Implemented boundary</strong>
              <br />
              Guarded native submission, identity-scoped job access,
              process-local idempotency, filtered history, status, confirmed
              cancellation and unmodified report inspection.
            </p>
            <p>
              <strong>Still requires integration</strong>
              <br />
              Enterprise identity, durable execution custody, provisioning,
              commercial entitlements, authoritative usage metering and
              Hermitten reconciliation.
            </p>
          </div>
        </section>
      </main>
      <footer className="t-footer">
        <span>TURING / HYBA</span>
        <span>
          Mathematical inputs. Governed execution. Inspectable evidence.
        </span>
      </footer>
    </div>
  );
}
