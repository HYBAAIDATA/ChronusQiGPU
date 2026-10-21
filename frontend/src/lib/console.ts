import type { MlaStatus, ReadyToMine, FabricMap, VerificationStatus, SelftestStatus, AgenticStatus, CampaignStatus, TelemetrySummary, AuditTail, IntelligenceStatus } from "./status";
import type { MiningEvidence } from "./evidence";

export type ConsoleSources = {
  fabric: FabricMap | null; verification: VerificationStatus | null;
  selftest: SelftestStatus | null; agentic: AgenticStatus | null;
  campaign: CampaignStatus | null; telemetry: TelemetrySummary | null;
  audit: AuditTail | null; intelligence: IntelligenceStatus | null;
  cognition: Record<string, unknown> | null;
};
export type ConsoleStatus = MlaStatus & {
  ready_to_mine?: ReadyToMine;
  console?: Partial<ConsoleSources> & { unavailable?: Record<string, string> };
};
export type ConsoleData = { status: ConsoleStatus | null; evidence: MiningEvidence | null; evidenceError: string | null; offline: boolean; loading: boolean };
/** Transport shape validation only. Readiness and measurements remain backend verdicts. */
export function parseConsoleStatus(value: unknown): ConsoleStatus {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid_status_object");
  const v = value as ConsoleStatus;
  if (v.schema_version !== "chronus.mla1517.status/1" || typeof v.generated_at !== "string" || !Number.isFinite(Date.parse(v.generated_at))) throw new Error("invalid_status_envelope");
  if (v.ready_to_mine && typeof v.ready_to_mine.ready !== "boolean") throw new Error("invalid_readiness_verdict");
  if (v.console !== undefined && (!v.console || typeof v.console !== "object" || Array.isArray(v.console))) throw new Error("invalid_console_sources");
  return v;
}
