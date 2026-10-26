import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  WorkflowBoundary,
  verifiedRestore,
  type WorkflowPort,
} from "./boundary";
import "./enterprise.css";

/** No default network binding. A reviewed actual-service adapter is required. */
export default function EnterpriseApp({
  port = null,
}: {
  port?: WorkflowPort | null;
}) {
  const boundary = useMemo(() => new WorkflowBoundary(port), [port]);
  const state = useSyncExternalStore(
    boundary.subscribe,
    boundary.getSnapshot,
    boundary.getSnapshot,
  );
  const [tenant, setTenant] = useState("");
  const [recordId, setRecordId] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const [hasFile, setHasFile] = useState(false);
  const outcome = state.outcome;
  const active = !!state.scope && ["ready", "result"].includes(state.phase);
  useEffect(() => {
    const visibility = () => boundary.checkExpiry();
    const hide = () => boundary.clear();
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("pagehide", hide);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("pagehide", hide);
      boundary.dispose();
    };
  }, [boundary]);
  useEffect(() => {
    if (!active) {
      setRecordId("");
      if (file.current) file.current.value = "";
      setHasFile(false);
    }
  }, [active, state.phase, state.scope]);
  const clear = () => {
    setHasFile(false);
    setRecordId("");
    if (file.current) file.current.value = "";
    boundary.clear();
  };
  const execute = (kind: "backup" | "restore") => {
    const input =
      kind === "backup" ? file.current?.files?.[0] : recordId.trim();
    if (!input) return;
    const key = crypto.randomUUID();
    setHasFile(false);
    if (file.current) file.current.value = "";
    void boundary.execute(kind, input, key);
  };
  const exportEvidence = async () => {
    const blob = await boundary.exportEvidence();
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "hyba-evidence.json";
    document.body.append(link);
    link.click();
    link.remove();
    // Release the object URL, including on page exit. No persistent browser cache.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };
  return (
    <div className="hyba-enterprise">
      <a className="he-skip" href="#enterprise-main">
        Skip to content
      </a>
      <header className="he-header">
        <div className="he-container">
          <p className="he-identity">
            HYBA <span>Capacity Fabric</span>
          </p>
          <p>Enterprise · qualification candidate</p>
        </div>
      </header>
      <main id="enterprise-main" tabIndex={-1} className="he-container">
        <p className="he-eyebrow">STORAGE / VERIFIED BACKUP & RESTORE</p>
        <h1>
          Recover your data.
          <br />
          Inspect the evidence.
        </h1>
        <p className="he-lead">
          One bounded workflow: retain a working form, recover the original
          bytes, and inspect custody and reconstruction evidence.
        </p>
        <section className="he-notice" aria-labelledby="availability-title">
          <h2 id="availability-title">
            {port
              ? "Service adapter supplied — qualification still required"
              : "Execution unavailable — service contract not bound"}
          </h2>
          <p>
            {port
              ? "An adapter binding is not a production declaration. The service owns access, exactness, custody and recovery decisions."
              : "This route does not call a placeholder endpoint or simulate a successful backup. The reviewed service contract must be bound and jointly tested before customer execution is enabled."}
          </p>
          <p>
            Production/publication HOLD · no billing activation · no
            hardware-performance claim
          </p>
        </section>
        <div className="he-workflow">
          <section className="he-panel" aria-labelledby="access-title">
            <p className="he-step">01 / ACCESS</p>
            <h2 id="access-title">Confirm the tenant boundary</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void boundary.connect(tenant.trim());
              }}
            >
              <label htmlFor="he-tenant">Tenant requested</label>
              <input
                id="he-tenant"
                value={tenant}
                onChange={(e) => {
                  clear();
                  setTenant(e.target.value);
                }}
                autoComplete="off"
                required
                disabled={!port || state.phase === "connecting"}
              />
              <p className="he-help">
                The service must authorize this scope. Typing a tenant is not
                permission.
              </p>
              <div className="he-actions">
                <button
                  disabled={
                    !port || !tenant.trim() || state.phase === "connecting"
                  }
                >
                  Confirm access
                </button>
                <button type="button" className="he-secondary" onClick={clear}>
                  Clear session
                </button>
              </div>
            </form>
            {state.scope && (
              <dl>
                <dt>Principal</dt>
                <dd>{state.scope.principal}</dd>
                <dt>Tenant</dt>
                <dd>{state.scope.tenant}</dd>
                <dt>Authorization revision</dt>
                <dd>{state.scope.authorizationRevision}</dd>
                <dt>Expires</dt>
                <dd>{new Date(state.scope.expiresAt).toISOString()}</dd>
              </dl>
            )}
          </section>
          <section className="he-panel" aria-labelledby="work-title">
            <p className="he-step">02 / WORKLOAD</p>
            <h2 id="work-title">Back up, then verify a restore</h2>
            <fieldset disabled={!active}>
              <legend>Service-admitted workload</legend>
              <label htmlFor="he-file">Backup source</label>
              <input
                id="he-file"
                type="file"
                ref={file}
                onChange={() => setHasFile(!!file.current?.files?.length)}
              />
              <p className="he-help">
                Limits, approval and supported representation are enforced by
                the service. No automatic retry.
              </p>
              <button
                type="button"
                disabled={!hasFile}
                onClick={() => execute("backup")}
              >
                Submit backup
              </button>
              <label htmlFor="he-record">Custody record to restore</label>
              <input
                id="he-record"
                value={recordId}
                onChange={(e) => setRecordId(e.target.value)}
                autoComplete="off"
              />
              <button
                type="button"
                disabled={!recordId.trim()}
                onClick={() => execute("restore")}
              >
                Verify restore
              </button>
            </fieldset>
          </section>
        </div>
        <section
          className="he-panel he-status"
          aria-labelledby="result-title"
          aria-busy={state.phase === "busy" || state.phase === "connecting"}
        >
          <p className="he-step">03 / OUTCOME & ASSURANCE</p>
          <h2 id="result-title">
            {outcome && verifiedRestore(outcome)
              ? "Digest-matched restore reported"
              : "No verified restore asserted"}
          </h2>
          <p role="status" aria-live="polite">
            <strong>{state.phase.toUpperCase()}</strong> — {state.message}
          </p>
          {state.requestKey && (
            <p>
              Request key: <code>{state.requestKey}</code>
            </p>
          )}
          {state.phase === "busy" && (
            <p>
              Clearing or switching sessions does not cancel server work. Retain
              the request key before leaving.
            </p>
          )}
          {state.phase === "unknown" && (
            <p>
              Retain this key for reconciliation. Confirming access does not
              determine whether the previous write committed.
            </p>
          )}
          {outcome && (
            <>
              <dl className="he-evidence">
                <dt>Evidence class</dt>
                <dd>{outcome.evidenceClass}</dd>
                <dt>Candidate</dt>
                <dd>{outcome.candidate}</dd>
                <dt>Custody record</dt>
                <dd>{outcome.recordId}</dd>
                <dt>Store / profile</dt>
                <dd>
                  {outcome.storeId} / {outcome.profile}
                </dd>
                <dt>Custody</dt>
                <dd>{outcome.custody}</dd>
                <dt>Exactness</dt>
                <dd>{outcome.exactness}</dd>
                <dt>Source digest</dt>
                <dd>
                  <code>{outcome.sourceDigest}</code>
                </dd>
                <dt>Restored digest</dt>
                <dd>
                  <code>{outcome.restoredDigest ?? "not reported"}</code>
                </dd>
                <dt>Reconstruction</dt>
                <dd>{outcome.reconstruction}</dd>
                <dt>Restart exercise</dt>
                <dd>{outcome.restart}</dd>
              </dl>
              <details>
                <summary>Inspect service-supplied evidence</summary>
                <pre>{JSON.stringify(outcome.evidence, null, 2)}</pre>
              </details>
              <button
                type="button"
                disabled={!boundary.canExport() || !active}
                onClick={() => void exportEvidence()}
              >
                Export authorized evidence
              </button>
              {!boundary.canExport() && (
                <p className="he-help">
                  Authorized evidence export is unavailable in this adapter.
                </p>
              )}
            </>
          )}
        </section>
        <section className="he-panel" aria-labelledby="scope-title">
          <h2 id="scope-title">
            What this launch slice does — and does not promise
          </h2>
          <p>
            Storage is the customer outcome. Theseus owns durable custody; Ovid
            owns transformation and lineage; AL HARAS owns authorization. Engine
            identities remain visible for assurance, not separate launch
            purchases.
          </p>
          <p>
            Movement, Tensor, Intelligence, managed cloud, sovereign/offline
            deployment, cross-region recovery and service levels require their
            own acceptance. They are not enabled by this route. A completion
            count is not a billable unit.
          </p>
          <h3>Recovery and support</h3>
          <p>
            For denial or expiry, confirm access again. For an unknown write,
            preserve the request key and ask the deployment operator to
            reconcile custody before retrying. For integrity failure, preserve
            the store and evidence; do not overwrite, migrate or delete it.
          </p>
          <p>
            Support contact, approved environments, retention, key ownership and
            commercial terms must be supplied in the deployment handoff before
            customer onboarding.
          </p>
        </section>
      </main>
      <footer className="he-container he-footer">
        HYBA · Active Infrastructure Capacity · Evidence before claims
        <br />
        Brand release pending official logo assets and approved display-font
        substitution.
      </footer>
    </div>
  );
}
