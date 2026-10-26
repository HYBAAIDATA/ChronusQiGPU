/** UI-only adapter contract. NOT an HTTP schema or a new authority.
 * A reviewed adapter must map an actual versioned service contract to this port.
 * No transport, credential store, endpoint, or default provider is supplied here.
 */
export type Scope = Readonly<{
  principal: string;
  tenant: string;
  authorizationRevision: string;
  expiresAt: number;
}>;
export type EvidenceClass =
  | "supported"
  | "measured"
  | "modeled"
  | "pending"
  | "unknown"
  | "unavailable"
  | "failed";
export type Outcome = Readonly<{
  recordId: string;
  candidate: string;
  profile: string;
  storeId: string;
  sourceDigest: string;
  restoredDigest: string | null;
  exactness: string;
  custody: "durable" | "memory_only" | "unknown";
  reconstruction: "pass" | "fail" | "not_run";
  restart: "pass" | "fail" | "not_run";
  evidenceClass: EvidenceClass;
  evidence: Readonly<Record<string, unknown>>;
}>;
export interface WorkflowPort {
  /** Must authenticate and authorize tenant server-side; requestedTenant is untrusted. */
  connect(requestedTenant: string, signal: AbortSignal): Promise<Scope>;
  backup(
    scope: Scope,
    payload: File,
    requestKey: string,
    signal: AbortSignal,
  ): Promise<Outcome>;
  restore(
    scope: Scope,
    recordId: string,
    requestKey: string,
    signal: AbortSignal,
  ): Promise<Outcome>;
  /** Optional: present only when the actual service supports authorized evidence export. */
  exportEvidence?(
    scope: Scope,
    recordId: string,
    signal: AbortSignal,
  ): Promise<Blob>;
}
export type Phase =
  | "unbound"
  | "locked"
  | "connecting"
  | "ready"
  | "busy"
  | "result"
  | "denied"
  | "expired"
  | "unknown"
  | "failed";
export type Snapshot = Readonly<{
  phase: Phase;
  scope: Scope | null;
  outcome: Outcome | null;
  message: string;
  requestKey: string | null;
}>;
export class BoundaryError extends Error {
  readonly kind: "denied" | "expired" | "unknown" | "failed";
  constructor(kind: BoundaryError["kind"]) {
    super(kind);
    this.kind = kind;
  }
}
const DIGEST = /^[a-f0-9]{64}$/;
const nonempty = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;
const CLASSES: readonly string[] = [
  "supported",
  "measured",
  "modeled",
  "pending",
  "unknown",
  "unavailable",
  "failed",
];
function checkedScope(scope: Scope, tenant: string, now: number): Scope {
  if (
    !scope ||
    scope.tenant !== tenant ||
    !nonempty(scope.principal) ||
    !nonempty(scope.authorizationRevision) ||
    !Number.isFinite(scope.expiresAt) ||
    scope.expiresAt <= now
  )
    throw new BoundaryError("denied");
  return Object.freeze({ ...scope });
}
export function checkedOutcome(value: Outcome): Outcome {
  if (
    !value ||
    ![
      value.recordId,
      value.candidate,
      value.profile,
      value.storeId,
      value.exactness,
    ].every(nonempty) ||
    typeof value.sourceDigest !== "string" ||
    !DIGEST.test(value.sourceDigest) ||
    (value.restoredDigest !== null &&
      (typeof value.restoredDigest !== "string" ||
        !DIGEST.test(value.restoredDigest))) ||
    !["durable", "memory_only", "unknown"].includes(value.custody) ||
    !["pass", "fail", "not_run"].includes(value.reconstruction) ||
    !["pass", "fail", "not_run"].includes(value.restart) ||
    !CLASSES.includes(value.evidenceClass) ||
    !value.evidence ||
    typeof value.evidence !== "object" ||
    Array.isArray(value.evidence) ||
    (value.reconstruction === "pass" &&
      value.sourceDigest !== value.restoredDigest)
  )
    throw new BoundaryError("unknown");
  // Reject evidence that would crash JSON inspection (cycles, BigInt, custom objects).
  let evidence: Record<string, unknown>;
  try {
    if (
      ![Object.prototype, null].includes(Object.getPrototypeOf(value.evidence))
    )
      throw new Error("not a JSON object");
    evidence = JSON.parse(JSON.stringify(value.evidence));
    if (!evidence || typeof evidence !== "object" || Array.isArray(evidence))
      throw new Error("not a JSON object");
  } catch {
    throw new BoundaryError("unknown");
  }
  // The adapter supplies redacted evidence; the browser does not manufacture a witness.
  return Object.freeze({ ...value, evidence: Object.freeze(evidence) });
}
export function verifiedRestore(value: Outcome): boolean {
  return (
    value.evidenceClass === "measured" &&
    value.exactness === "EXACT" &&
    value.custody === "durable" &&
    value.reconstruction === "pass" &&
    value.sourceDigest === value.restoredDigest
  );
}
/** Drops protected data before notifying, cancels work and rejects late callbacks.
 * Client expiry is a display safeguard, not a replacement for server revocation.
 */
export class WorkflowBoundary {
  private snapshot: Snapshot;
  private generation = 0;
  private aborter: AbortController | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private listeners = new Set<() => void>();
  constructor(
    private readonly port: WorkflowPort | null,
    private readonly timeoutMs = 30_000,
  ) {
    this.snapshot = Object.freeze({
      phase: port ? "locked" : "unbound",
      scope: null,
      outcome: null,
      requestKey: null,
      message: port
        ? "Confirm server-authorized tenant access."
        : "No reviewed service adapter is bound. Execution is unavailable.",
    });
  }
  getSnapshot = (): Snapshot => this.snapshot;
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private publish(value: Snapshot): void {
    this.snapshot = Object.freeze(value);
    this.listeners.forEach((fn) => fn());
  }
  private invalidate(): number {
    ++this.generation;
    this.aborter?.abort();
    this.aborter = null;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    return this.generation;
  }
  clear = (reason: "locked" | "expired" = "locked"): void => {
    this.invalidate();
    this.publish({
      phase: this.port ? reason : "unbound",
      scope: null,
      outcome: null,
      requestKey: null,
      message:
        reason === "expired"
          ? "Session expired. Protected results cleared; confirm access again."
          : "Protected results cleared. Confirm access again.",
    });
  };
  dispose(): void {
    this.clear();
    this.listeners.clear();
  }
  private armExpiry(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    const scope = this.snapshot.scope;
    if (scope)
      this.timer = setTimeout(
        () => {
          this.checkExpiry();
          if (this.snapshot.scope) this.armExpiry();
        },
        Math.max(0, Math.min(2_147_483_647, scope.expiresAt - Date.now())),
      );
  }
  checkExpiry = (): void => {
    if (this.snapshot.scope && this.snapshot.scope.expiresAt <= Date.now())
      this.clear("expired");
  };
  private async bounded<T>(
    task: (signal: AbortSignal) => Promise<T>,
  ): Promise<T> {
    const controller = new AbortController();
    this.aborter = controller;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        task(controller.signal),
        new Promise<never>((_, reject) => {
          timeout = setTimeout(() => {
            controller.abort();
            reject(new BoundaryError("unknown"));
          }, this.timeoutMs);
        }),
      ]);
    } finally {
      if (timeout !== undefined) clearTimeout(timeout);
      if (this.aborter === controller) this.aborter = null;
    }
  }
  async connect(tenant: string): Promise<void> {
    if (!this.port) return;
    const generation = this.invalidate();
    this.publish({
      phase: "connecting",
      scope: null,
      outcome: null,
      requestKey: null,
      message: "Confirming access with the service…",
    });
    try {
      if (!nonempty(tenant)) throw new BoundaryError("denied");
      const scope = checkedScope(
        await this.bounded((signal) => this.port!.connect(tenant, signal)),
        tenant,
        Date.now(),
      );
      if (generation !== this.generation) return;
      this.publish({
        phase: "ready",
        scope,
        outcome: null,
        requestKey: null,
        message:
          "Access confirmed by the service adapter. Select a bounded workload.",
      });
      this.armExpiry();
    } catch (error) {
      if (generation === this.generation) this.failure(error, null);
    }
  }
  private failure(error: unknown, requestKey: string | null): void {
    const phase = error instanceof BoundaryError ? error.kind : "unknown";
    this.invalidate();
    this.publish({
      phase,
      scope: null,
      outcome: null,
      requestKey: phase === "unknown" ? requestKey : null,
      message:
        phase === "denied"
          ? "Access denied or revoked. Protected results cleared."
          : phase === "expired"
            ? "Session expired. Confirm access again."
            : phase === "unknown"
              ? "Outcome unknown. Do not resubmit blindly. Reconcile the request key with the operator."
              : "The service reported failure. Confirm access before continuing.",
    });
  }
  async execute(
    kind: "backup" | "restore",
    input: File | string,
    requestKey: string,
  ): Promise<void> {
    this.checkExpiry();
    const scope = this.snapshot.scope;
    if (
      !this.port ||
      !scope ||
      !["ready", "result"].includes(this.snapshot.phase)
    )
      return;
    if (
      !nonempty(requestKey) ||
      (kind === "restore" ? !nonempty(input) : typeof input === "string")
    )
      return;
    const generation = this.invalidate();
    this.publish({
      phase: "busy",
      scope,
      outcome: null,
      requestKey,
      message:
        kind === "backup"
          ? "Submitting backup. No durable receipt yet."
          : "Requesting restore. Reconstruction is not yet verified.",
    });
    this.armExpiry();
    try {
      const value = checkedOutcome(
        await this.bounded((signal) =>
          kind === "backup"
            ? this.port!.backup(scope, input as File, requestKey, signal)
            : this.port!.restore(scope, input as string, requestKey, signal),
        ),
      );
      if (generation !== this.generation) return;
      if (scope.expiresAt <= Date.now()) {
        this.clear("expired");
        return;
      }
      this.publish({
        phase: "result",
        scope,
        outcome: value,
        requestKey,
        message: verifiedRestore(value)
          ? "Service reports a digest-matched restore with durable custody. Inspect evidence and restart scope."
          : "Service result received. Review the reported limitations; verified restore is not established.",
      });
      this.armExpiry();
    } catch (error) {
      if (generation === this.generation) this.failure(error, requestKey);
    }
  }
  canExport(): boolean {
    return (
      !!this.port?.exportEvidence &&
      !!this.snapshot.outcome &&
      !!this.snapshot.scope &&
      this.snapshot.scope.expiresAt > Date.now()
    );
  }
  async exportEvidence(): Promise<Blob | null> {
    this.checkExpiry();
    const { scope, outcome } = this.snapshot;
    if (
      !this.port?.exportEvidence ||
      !scope ||
      !outcome ||
      this.snapshot.phase !== "result"
    )
      return null;
    const generation = this.invalidate();
    this.publish({
      ...this.snapshot,
      phase: "busy",
      message: "Reauthorizing evidence export…",
    });
    this.armExpiry();
    try {
      const blob = await this.bounded((signal) =>
        this.port!.exportEvidence!(scope, outcome.recordId, signal),
      );
      if (generation !== this.generation) return null;
      if (scope.expiresAt <= Date.now()) {
        this.clear("expired");
        return null;
      }
      if (!(blob instanceof Blob)) throw new BoundaryError("unknown");
      this.publish({
        ...this.snapshot,
        phase: "result",
        message: "Evidence export received from the service.",
      });
      this.armExpiry();
      return blob;
    } catch (error) {
      if (generation === this.generation) this.failure(error, null);
      return null;
    }
  }
}
