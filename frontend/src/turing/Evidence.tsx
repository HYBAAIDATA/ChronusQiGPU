import { isRecord } from "./client";
export function returnedText(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "Not supplied";
}
/** Textual projection only: no numerical conversions, inferred success or signature verification. */
export default function Evidence({
  report,
}: {
  report: Record<string, unknown>;
}) {
  const pipeline = isRecord(report.pipeline_report)
    ? report.pipeline_report
    : null;
  const stages = Array.isArray(pipeline?.stages)
    ? pipeline.stages.filter(isRecord)
    : [];
  const result = isRecord(pipeline?.result) ? pipeline.result : null;
  return (
    <section className="t-evidence" aria-labelledby="validation-title">
      <h3 id="validation-title">Validation and mathematical output</h3>
      <dl className="t-details">
        <dt>Returned pipeline verdict</dt>
        <dd>{returnedText(pipeline?.verdict)}</dd>
        <dt>Program digest</dt>
        <dd>
          <code>{returnedText(pipeline?.program_digest)}</code>
        </dd>
      </dl>
      <p className="t-small">
        These are native report fields, not a new verification by the browser.
        PASS applies to the returned pipeline's scope; SKIPPED, GATED or
        UNAVAILABLE must not be treated as completed evidence.
      </p>
      {stages.length > 0 ? (
        <ol className="t-stage-list">
          {stages.map((s, i) => (
            <li key={i}>
              <div>
                <strong>{returnedText(s.stage)}</strong>
                <span className="t-state">{returnedText(s.state)}</span>
              </div>
              <p>{returnedText(s.detail)}</p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="t-muted">
          No readable stage evidence supplied. Inspect the unmodified report
          below.
        </p>
      )}
      {result && isRecord(result.payload) ? (
        <details className="t-input-summary">
          <summary>Returned mathematical payload</summary>
          <p className="t-small">
            Exact values retain the engine's representation. Units, tolerances
            and precision are not inferred or converted.
          </p>
          <pre tabIndex={0} aria-label="Returned mathematical payload">
            {JSON.stringify(result.payload, null, 2)}
          </pre>
        </details>
      ) : (
        <p className="t-small">
          No structured mathematical payload supplied. The complete returned
          report remains available below.
        </p>
      )}
    </section>
  );
}
