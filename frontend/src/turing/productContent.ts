import type { PublicPage } from "./routes";
export type Article = {
  eyebrow: string;
  title: string;
  intro: string;
  sections: { title: string; paragraphs: string[]; items?: string[] }[];
};
/** Publication-safe capability copy: no pricing, benchmarks, customers or certifications. */
export const ARTICLES: Record<
  Exclude<PublicPage, "product" | "contact">,
  Article
> = {
  capabilities: {
    eyebrow: "A precise computational boundary",
    title: "Capability begins with a defined domain.",
    intro:
      "The evaluation workspace exposes a bounded native-program workflow. Engine-level capabilities are broader than this interface; they are not promises of enterprise service capacity.",
    sections: [
      {
        title: "Available through this workspace",
        paragraphs: [
          "Submit a JSON program with an integer width of 1–12 logical qubits and up to 256 operations. The server applies a 4,096-amplitude admission bound; the native facade still decides whether a program is admitted.",
        ],
        items: [
          "Fixed gates: i, x, y, z, h, s, sdg, t, tdg, cx, cnot, cz and swap.",
          "Queued, running, succeeded, failed and cancelled native job states.",
          "Same-identity job lookup, filtered execution history, queued cancellation and returned-report export.",
        ],
      },
      {
        title: "A useful first evaluation",
        paragraphs: [
          "An editable two-qubit Bell-state program applies h to qubit 0 and cx to qubits 0 and 1. It tests the submission-to-evidence journey without embedding a precomputed answer in the interface.",
          "Use your own admitted native programs to assess exact gate composition and provenance inspection. Determine suitability for a business problem through a separately scoped technical evaluation.",
        ],
      },
      {
        title: "Not exposed by this interface",
        paragraphs: [
          "Continuous rotation parameters, dynamic control, physical-QPU execution, unbounded programs and silent approximation are not supported by this workspace. Do not infer them from broader package names.",
          "Instance counts, commercial allocations, throughput guarantees and financial outcomes are not measured or promised here.",
        ],
      },
    ],
  },
  "how-it-works": {
    eyebrow: "From input to evidence",
    title: "A result you can interrogate.",
    intro:
      "The interface collects a mathematical program. The service authenticates the request. The existing TURING pipeline governs admission, execution and returned evidence.",
    sections: [
      {
        title: "01 · Define and review",
        paragraphs: [
          "Author a native JSON program. Client-side validation gives early feedback; it does not override server checks. Review the width, operation count and absence of a commercial estimate before confirming submission.",
        ],
      },
      {
        title: "02 · Admit and execute",
        paragraphs: [
          "AL HARAS preflight must allow the tenant, actor and subscription for the request. The adapter enforces the pilot envelope and calls TuringPipeline, preserving the canonical VQCPipeline underneath. A security subscription is not a commercial TURING entitlement.",
        ],
      },
      {
        title: "03 · Inspect",
        paragraphs: [
          "Read the backend's last confirmed job state. On success, inspect the returned report, including any configuration, artifact hash, implementation hash, stage evidence, certificate and witness it supplies. Missing evidence stays missing; it is never replaced with a favourable value.",
        ],
      },
      {
        title: "04 · Recover deliberately",
        paragraphs: [
          "If submission loses its acknowledgement, keep the same request key and program. Retry that request rather than creating a duplicate. Process-local deduplication does not survive a server restart; confirm server continuity with the operator before retrying after one.",
          "A returned certificate is native pipeline evidence, not independent certification. This pilot does not establish durable enterprise custody or a cross-restart reproducibility guarantee.",
        ],
      },
    ],
  },
  enterprise: {
    eyebrow: "Enterprise evaluation",
    title: "Governance before commitment.",
    intro:
      "TURING is being developed around computational capability delivered as a service, not per-seat software licensing. This interface is a technical evaluation, not an enterprise production offer.",
    sections: [
      {
        title: "Begin with a bounded question",
        paragraphs: [
          "Agree the computational task, supported input domain, expected evidence, confidentiality constraints and acceptance criteria. Evaluate the native workflow before negotiating allocations or service commitments.",
        ],
      },
      {
        title: "Commercial structure to validate",
        paragraphs: [
          "Potential arrangements include service commitments, reserved capacity, included usage, measured consumption, support and bespoke engagements. No rates or discounts are implied. Pricing requires measured cost to serve and agreed outcome value, with approved contract terms.",
        ],
      },
      {
        title: "Required before enterprise activation",
        paragraphs: [
          "The following dependencies are not operational in this workspace.",
        ],
        items: [
          "Approved enterprise identity provider, organisation model and server-enforced role policies.",
          "Contract authority and an explicit definition of a provisioned resource.",
          "Capacity inventory, admission rules and recoverable lifecycle operations.",
          "Durable job custody, customer retention policy, backup and recovery evidence.",
          "Authoritative metering and tested Hermitten rating, invoicing and reconciliation.",
        ],
      },
      {
        title: "No implied customer commitments",
        paragraphs: [
          "This preview contains no customer endorsements, contractual capacity guarantees, certifications, production SLAs or approved commercial terms. Public launch and production deployment require separate authorisation.",
        ],
      },
    ],
  },
  documentation: {
    eyebrow: "Evaluation guide",
    title: "A small contract. Explicit semantics.",
    intro:
      "Use the same-origin evaluation API only with credentials issued through the existing AL HARAS authority. Never place a bearer in a URL, source file, screenshot or support ticket.",
    sections: [
      {
        title: "Connect",
        paragraphs: [
          "The workspace requires a tenant identifier, actor identifier and subscription bearer. They remain in this tab's memory. Navigation to another page or closing the tab clears that connection; reconnect to inspect jobs retained by the same server process.",
          "The server pilot flag is disabled by default. An unavailable service is not an invitation to bypass authentication. Only the service operator can configure a controlled technical evaluation.",
        ],
      },
      {
        title: "Request contract",
        paragraphs: [
          "POST /api/v1/quantum/workspace with JSON, Authorization: Bearer, X-HYBA-Tenant and X-HYBA-Actor. Commands are capabilities, submit, status, cancel and list. Every command passes the existing guardian preflight; the adapter rechecks the allowed tenant-bound receipt.",
          "submit requires program and idempotency_key; status and cancel require job_id. list accepts offset, limit (1–20), a native status and a job-identifier query. History is newest-first and identity-scoped. Refresh from offset zero after a new submission.",
        ],
      },
      {
        title: "Errors and recovery",
        paragraphs: [
          "400: invalid schema or field. 401/403: authority denied or expired; reconnect with the same identity. 404: no job in the current identity/process. 409: conflicting idempotency key. 422: native domain refusal. 429: bounded retained-job limit. 503: disabled service, unavailable dependency or unknown execution outcome.",
          "A timeout, broken connection or unreadable acknowledgement is not proof that execution failed. Retain and retry the same program and key only while the original server process is known to be continuous. Cancellation can stop queued work; a running native computation may finish.",
        ],
      },
      {
        title: "Read and export evidence",
        paragraphs: [
          "Select a retained execution to retrieve its current status. Successful jobs expose the unmodified returned report. Download is local JSON export, not delivery to another service. Treat inputs, results and report metadata as potentially confidential.",
          "This implementation does not supply business-project sharing, organisation-wide history, metered charges or invoices. Empty history means no retained rows in this identity/process, not zero lifetime use.",
        ],
      },
    ],
  },
  security: {
    eyebrow: "Security boundary",
    title: "Be precise about what is protected.",
    intro:
      "The pilot reuses AL HARAS. It does not introduce a new authentication protocol, enterprise SSO or a compliance claim.",
    sections: [
      {
        title: "Implemented request controls",
        paragraphs: [
          "Every workspace action is behind the existing privileged-request guardian. Tenant and actor scope are checked on the server for job access; foreign jobs are not found. Input fields are allowlisted and programs are bounded.",
          "The client sends a bearer only to the same-origin endpoint, omits cookies, rejects redirects and does not persist credentials in browser storage. It renders returned data as text and exports only the selected report.",
        ],
      },
      {
        title: "Data lifecycle",
        paragraphs: [
          "Job registry and idempotency mappings are in one process. Restart loses their history. Disconnect clears the displayed execution and in-memory credentials; it does not cancel server jobs. Raw reports may contain sensitive inputs or metadata and need an operator-approved retention policy.",
          "The host's audit/evidence path is separate from browser state. Do not assume clearing the view deletes server audit records. Retention, residency, legal hold, support access and data-deletion procedures require explicit service-owner review.",
        ],
      },
      {
        title: "Limits and deployment obligations",
        paragraphs: [
          "Retained-job bounds are not a complete abuse-control or multi-worker scheduling design. The deployment must supply approved TLS termination, secret management, request-rate policy, monitoring and dependency controls. Live guardian boot and enterprise identity require environment qualification.",
          "There is no unrestricted operator impersonation, billing administration or provisioning endpoint in this workspace. No certification, regulatory-compliance status or encryption-at-rest guarantee is asserted.",
        ],
      },
    ],
  },
  research: {
    eyebrow: "Method and evidence",
    title: "Separate the claim from its evidence.",
    intro:
      "This preview treats native mathematical execution, returned verification evidence, service guarantees and research hypotheses as different categories.",
    sections: [
      {
        title: "Implementation reference",
        paragraphs: [
          "The existing package provides a typed TuringPipeline facade over the canonical VQCPipeline. The evaluation adapter does not modify that engine or implement a second one in the browser.",
          "Source code and repository tests are engineering evidence. A locally mocked browser result is UI-test evidence only, not proof of a native computation or customer acceptance.",
        ],
      },
      {
        title: "Read the report in context",
        paragraphs: [
          "Inspect the report's verdict, execution classification, validation stages, refusals and missing or gated subsystems. A native certificate or witness must be interpreted under the package's own validation contract, not as an external audit opinion.",
        ],
      },
      {
        title: "No unsupported research claims",
        paragraphs: [
          "No performance benchmark, physical-QPU claim, research priority, general-purpose advantage or peer-reviewed publication is asserted on these pages. Authorised publications and independently reproducible evaluations can be added after source verification and approval.",
        ],
      },
    ],
  },
  "legal/privacy": {
    eyebrow: "Evaluation data notice · not an approved legal policy",
    title: "Know what this preview retains.",
    intro:
      "An approved company privacy policy has not been provided. This technical notice describes this implementation; it is not a substitute for legal approval or a production data-processing agreement.",
    sections: [
      {
        title: "Browser handling",
        paragraphs: [
          "Credentials stay in memory and are sent to the same-origin service. This workspace adds no third-party analytics or browser-storage persistence. Local downloads may contain confidential data; protect them under your own policy.",
        ],
      },
      {
        title: "Service handling",
        paragraphs: [
          "The server retains jobs in process-local memory. Existing guardian audit and evidence handling are separate and depend on operator configuration. A restart or UI disconnect is not a data-deletion assurance.",
        ],
      },
      {
        title: "Before sharing data",
        paragraphs: [
          "Do not submit personal, regulated or production-confidential data without an approved handling arrangement. Controller identity, legal basis, retention, residency, rights requests, subprocessors and the privacy contact must be confirmed by the responsible organisation before public launch.",
        ],
      },
    ],
  },
  "legal/terms": {
    eyebrow: "Release gate · no approved commercial terms",
    title: "Technical access is not a service commitment.",
    intro:
      "No approved service agreement or public terms have been supplied. These pages do not grant a production SLA, reserved capacity, billable entitlement or contractual right to use customer data.",
    sections: [
      {
        title: "Evaluation boundary",
        paragraphs: [
          "Use must be authorised by the service operator and confined to an agreed technical evaluation. No price, warranty, support response time, customer allocation or enterprise availability commitment is represented here.",
        ],
      },
      {
        title: "Approval required",
        paragraphs: [
          "Legal review must establish the contracting entity, jurisdiction, acceptable use, confidentiality, intellectual-property treatment, data-processing terms, liability, termination and dispute procedures. Commercial and production activation remain blocked until authorised terms are in place.",
        ],
      },
    ],
  },
};
