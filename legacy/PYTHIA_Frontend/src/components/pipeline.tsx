import { cn } from "@/lib/utils";
import type { EvidenceGate } from "@/lib/pythia/engine";

const GATES: { id: EvidenceGate; label: string }[] = [
  { id: "connected", label: "Connected" },
  { id: "authorized", label: "Authorized" },
  { id: "job_received", label: "Job" },
  { id: "candidate_found", label: "Candidate" },
  { id: "submitted", label: "Submitted" },
  { id: "accepted", label: "Accepted" },
];

export function Pipeline({ evidence }: { evidence: Record<EvidenceGate, boolean> }) {
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {GATES.map((g, i) => {
        const on = evidence[g.id];
        return (
          <li
            key={g.id}
            className={cn(
              "rounded-lg px-3 py-3 shadow-[var(--shadow-border)]",
              on ? "bg-live/10" : "bg-card",
            )}
          >
            <p className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {String(i + 1).padStart(2, "0")}
            </p>
            <p className="mt-2 text-sm text-foreground">{g.label}</p>
            <p className={cn("mt-1 text-[11px] uppercase tracking-widest", on ? "text-live" : "text-muted-foreground")}>
              {on ? "evidenced" : "pending"}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
