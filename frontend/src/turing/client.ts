/** Same-origin bearer boundary. Credentials live in memory, never browser storage. */
export type Program = {
  n_qubits: number;
  operations: { gate: string; qubits: number[] }[];
};
export type JobState =
  "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type Job = {
  job_id: string;
  status: JobState;
  submitted_at: string;
  program: Program;
  report?: Record<string, unknown>;
  error?: string;
  cancellation_accepted?: boolean;
};
export type Credentials = { tenant: string; actor: string; token: string };
export type Command =
  | { action: "capabilities" }
  | { action: "submit"; program: Program; idempotency_key: string }
  | { action: "status" | "cancel"; job_id: string };
export type Capabilities = {
  max_qubits: number;
  max_operations: number;
  max_amplitudes: number;
  gates: string[];
};
const STATES: string[] = [
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
];
export const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
export class ServiceError extends Error {
  constructor(
    message: string,
    public uncertain = false,
  ) {
    super(message);
  }
}
export function parseProgram(raw: string): Program {
  const v: unknown = JSON.parse(raw);
  if (
    !isRecord(v) ||
    Object.keys(v).sort().join() !== "n_qubits,operations" ||
    typeof v.n_qubits !== "number" ||
    !Number.isInteger(v.n_qubits) ||
    v.n_qubits < 1 ||
    v.n_qubits > 12 ||
    !Array.isArray(v.operations) ||
    v.operations.length > 256
  )
    throw new Error(
      "Use a width from 1 to 12 and at most 256 native operations.",
    );
  const gates = [
    "i",
    "x",
    "y",
    "z",
    "h",
    "s",
    "sdg",
    "t",
    "tdg",
    "cx",
    "cnot",
    "cz",
    "swap",
  ];
  const width = v.n_qubits;
  const operations = v.operations.map((op: unknown) => {
    if (
      !isRecord(op) ||
      Object.keys(op).sort().join() !== "gate,qubits" ||
      typeof op.gate !== "string" ||
      !gates.includes(op.gate) ||
      !Array.isArray(op.qubits)
    )
      throw new Error(
        "Each operation requires a supported gate and a qubits array.",
      );
    const targets = op.qubits;
    const arity = ["cx", "cnot", "cz", "swap"].includes(op.gate) ? 2 : 1;
    if (
      targets.length !== arity ||
      new Set(targets).size !== arity ||
      targets.some(
        (q: unknown) =>
          typeof q !== "number" || !Number.isInteger(q) || q < 0 || q >= width,
      )
    )
      throw new Error(
        "Gate targets must be distinct, in range, and match the gate's arity.",
      );
    return { gate: op.gate, qubits: targets as number[] };
  });
  return { n_qubits: width, operations };
}
export function parseJob(v: Record<string, unknown>): Job {
  if (
    typeof v.job_id !== "string" ||
    typeof v.status !== "string" ||
    !STATES.includes(v.status) ||
    typeof v.submitted_at !== "string" ||
    Number.isNaN(Date.parse(v.submitted_at))
  )
    throw new ServiceError(
      "Invalid job response. Execution outcome is unknown; keep the request key.",
      true,
    );
  let program: Program;
  try {
    program = parseProgram(JSON.stringify(v.program));
  } catch {
    throw new ServiceError("Invalid program in job response.", true);
  }
  if (v.status === "succeeded" && !isRecord(v.report))
    throw new ServiceError("Completed job is missing its report.", true);
  return {
    job_id: v.job_id,
    status: v.status as JobState,
    submitted_at: v.submitted_at,
    program,
    report: isRecord(v.report) ? v.report : undefined,
    error: typeof v.error === "string" ? v.error : undefined,
    cancellation_accepted:
      typeof v.cancellation_accepted === "boolean"
        ? v.cancellation_accepted
        : undefined,
  };
}
export async function request(
  creds: Credentials,
  command: Command,
): Promise<Record<string, unknown>> {
  let response: Response;
  try {
    response = await fetch("/api/v1/quantum/workspace", {
      method: "POST",
      credentials: "omit",
      redirect: "error",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${creds.token}`,
        "X-HYBA-Tenant": creds.tenant,
        "X-HYBA-Actor": creds.actor,
      },
      body: JSON.stringify({
        ...command,
        observation: { ui: "turing-workspace", action: command.action },
      }),
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    throw new ServiceError(
      "Connection interrupted. A submission may still have reached the service.",
      true,
    );
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new ServiceError(
      "The service returned an unreadable response.",
      true,
    );
  }
  if (!response.ok) {
    const code =
      isRecord(value) && typeof value.error === "string"
        ? value.error
        : response.status === 401 || response.status === 403
          ? "Access denied by AL HARAS"
          : `Service returned HTTP ${response.status}`;
    throw new ServiceError(code, response.status >= 500);
  }
  if (
    !isRecord(value) ||
    value.schema_version !== "turing.workspace.v1" ||
    value.persistence !== "in_memory_process_local" ||
    value.service_mode !== "technical_evaluation_only"
  )
    throw new ServiceError("Unrecognised workspace contract.", true);
  return value;
}
export function parseCapabilities(v: Record<string, unknown>): Capabilities {
  if (
    v.max_qubits !== 12 ||
    v.max_operations !== 256 ||
    v.max_amplitudes !== 4096 ||
    !Array.isArray(v.gates) ||
    !v.gates.every((g: unknown) => typeof g === "string")
  )
    throw new ServiceError("Unexpected pilot capability envelope.");
  return {
    max_qubits: 12,
    max_operations: 256,
    max_amplitudes: 4096,
    gates: v.gates as string[],
  };
}
