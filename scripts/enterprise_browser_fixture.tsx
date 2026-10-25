/** Browser component harness. EVERY service response is a labeled double. */
import React from "react";
import { createRoot } from "react-dom/client";
import EnterpriseApp from "../frontend/src/enterprise/EnterpriseApp";
import {
  BoundaryError,
  type WorkflowPort,
  type Outcome,
} from "../frontend/src/enterprise/boundary";
const scenario =
  new URL(location.href).searchParams.get("scenario") ?? "unbound";
const outcome = (restored: boolean): Outcome => ({
  recordId: "FIXTURE-record-42",
  candidate: "FIXTURE-only-NOT-a-runtime-candidate",
  profile: "FIXTURE-theseus-profile",
  storeId: "FIXTURE-alpha-store",
  sourceDigest: "a".repeat(64),
  restoredDigest: restored ? "a".repeat(64) : null,
  exactness: "EXACT",
  custody: "durable",
  reconstruction: restored ? "pass" : "not_run",
  restart: "not_run",
  evidenceClass: "measured",
  evidence: {
    fixture: true,
    notice: "Synthetic adapter double. NOT runtime qualification.",
  },
});
const port: WorkflowPort = {
  async connect(tenant) {
    if (tenant === "denied") throw new BoundaryError("denied");
    return {
      principal: "FIXTURE-principal",
      tenant,
      authorizationRevision: "FIXTURE-rev1",
      expiresAt: Date.now() + (scenario === "expired" ? 700 : 60_000),
    };
  },
  async backup(_scope, _file, _key, signal) {
    if (scenario === "failure") throw new BoundaryError("failed");
    if (scenario === "unknown") throw new BoundaryError("unknown");
    if (scenario === "loading")
      await new Promise((resolve, reject) => {
        const timer = setTimeout(resolve, 2000);
        signal.addEventListener("abort", () => {
          clearTimeout(timer);
          reject(new Error("aborted"));
        });
      });
    return outcome(false);
  },
  async restore() {
    if (scenario === "revoked") throw new BoundaryError("denied");
    return outcome(true);
  },
  async exportEvidence() {
    return new Blob([JSON.stringify({ fixture: true })], {
      type: "application/json",
    });
  },
};
createRoot(document.getElementById("root")!).render(
  <>
    <div
      style={{
        background: "#fff3cd",
        color: "#593900",
        padding: "12px 24px",
        font: "bold 16px system-ui",
        borderBottom: "2px solid #593900",
      }}
    >
      COMPONENT FIXTURE — {scenario} — no runtime service or engine execution
    </div>
    <EnterpriseApp port={scenario === "unbound" ? null : port} />
  </>,
);
