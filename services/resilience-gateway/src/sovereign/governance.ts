export type ExperimentArm = "A" | "B" | "C" | "E";

export interface Observation {
  arm: ExperimentArm;
  requestFingerprint: string;
  outputFingerprint: string;
  latencyMs: number;
  maintainabilityIndex: number;
}

export interface GovernanceSla {
  minimumSamplesPerArm: number;
  maximumOutputDrift: number;
  maximumLatencyRegression: number;
  minimumMaintainabilityIndex: number;
}

export interface GovernanceDecision {
  authorized: boolean;
  reasons: string[];
  driftByArm: Partial<Record<ExperimentArm, number>>;
}

export function evaluateExperiment(
  observations: readonly Observation[],
  sla: GovernanceSla,
): GovernanceDecision {
  const baseline = observations.filter(({ arm }) => arm === "A");
  const candidates: ExperimentArm[] = ["B", "C", "E"];
  const reasons: string[] = [];
  const driftByArm: Partial<Record<ExperimentArm, number>> = {};
  const baselineByRequest = new Map(
    baseline.map((item) => [item.requestFingerprint, item]),
  );
  const baselineLatency = mean(baseline.map(({ latencyMs }) => latencyMs));

  if (baseline.length < sla.minimumSamplesPerArm) {
    reasons.push("baseline sample floor not met");
  }
  for (const arm of candidates) {
    const samples = observations.filter((item) => item.arm === arm);
    if (samples.length < sla.minimumSamplesPerArm) {
      reasons.push(`${arm} sample floor not met`);
      continue;
    }
    const comparable = samples.filter((item) =>
      baselineByRequest.has(item.requestFingerprint),
    );
    const drift =
      comparable.filter(
        (item) =>
          baselineByRequest.get(item.requestFingerprint)?.outputFingerprint !==
          item.outputFingerprint,
      ).length / Math.max(1, comparable.length);
    driftByArm[arm] = drift;
    if (drift > sla.maximumOutputDrift) {
      reasons.push(`${arm} output drift ${drift} exceeds SLA`);
    }
    const latencyRegression =
      mean(samples.map(({ latencyMs }) => latencyMs)) /
        Math.max(1, baselineLatency) -
      1;
    if (latencyRegression > sla.maximumLatencyRegression) {
      reasons.push(`${arm} latency regression exceeds SLA`);
    }
    if (
      Math.min(...samples.map(({ maintainabilityIndex }) => maintainabilityIndex)) <
      sla.minimumMaintainabilityIndex
    ) {
      reasons.push(`${arm} maintainability floor not met`);
    }
  }
  return { authorized: reasons.length === 0, reasons, driftByArm };
}

function mean(values: readonly number[]): number {
  return values.length
    ? values.reduce((total, value) => total + value, 0) / values.length
    : 0;
}