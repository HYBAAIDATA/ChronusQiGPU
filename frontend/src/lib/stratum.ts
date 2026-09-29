import type { StratumStatus } from "./status";

export type StratumStageState = "complete" | "active" | "blocked" | "idle";

export type StratumStage = {
  key: string;
  label: string;
  state: StratumStageState;
};

export function stratumStages(status?: StratumStatus | null): StratumStage[] {
  const primary = status?.primary;
  const job = status?.job;
  const submission = status?.submission;
  const transport = primary?.transport === "CONNECTED";
  const subscribed = primary?.subscribed === true;
  const authorized = primary?.authorized === true;
  const activeJob = job?.active === true && job.generation != null;
  const ready = status?.ready === true;
  const submitted =
    submission?.state === "SUBMITTING" ||
    submission?.last_submit_at != null ||
    (status?.counters?.submitted ?? 0) > 0;
  const accepted = submission?.last_result === "ACCEPTED" || (status?.counters?.accepted ?? 0) > 0;
  const acceptedStage: StratumStageState = accepted
    ? "complete"
    : submission?.last_result === "REJECTED" || submission?.last_result === "OUTCOME_UNKNOWN"
      ? "blocked"
      : submitted
        ? "active"
        : "idle";

  return [
    { key: "connect", label: "Connect", state: transport ? "complete" : "blocked" },
    {
      key: "subscribe",
      label: "Subscribe",
      state: subscribed ? "complete" : transport ? "active" : "idle",
    },
    {
      key: "authorize",
      label: "Authorize",
      state: authorized ? "complete" : subscribed ? "active" : "idle",
    },
    {
      key: "job",
      label: "Job",
      state: activeJob ? "complete" : authorized ? "active" : "idle",
    },
    {
      key: "search",
      label: "Search",
      state: ready ? "complete" : activeJob ? "blocked" : "idle",
    },
    {
      key: "candidate",
      label: "Candidate",
      state: submitted ? "complete" : ready ? "active" : "idle",
    },
    {
      key: "submit",
      label: "Submit",
      state: submitted ? "complete" : "idle",
    },
    {
      key: "accepted",
      label: "Accepted",
      state: acceptedStage,
    },
  ];
}

export function stratumAlert(status?: StratumStatus | null): string | null {
  if (!status || status.evidence_available === false) return "STRATUM EVIDENCE UNAVAILABLE";
  if (status.state === "AUTH_FAILED") return "POOL AUTHORIZATION FAILED";
  if (status.submission?.state === "OUTCOME_UNKNOWN") return "SUBMISSION OUTCOME UNKNOWN";
  if (status.primary?.transport !== "CONNECTED") return "POOL DISCONNECTED";
  if (status.primary?.authorized === true && status.job?.active !== true) {
    return "NO FRESH JOB";
  }
  return null;
}
