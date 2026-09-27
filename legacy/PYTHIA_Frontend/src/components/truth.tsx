import { Badge } from "@/components/ui/badge";
import type { TruthClass } from "@/lib/pythia/engine";

const TONE: Record<TruthClass, "live" | "warn" | "theoretical" | "default" | "paper"> = {
  measured: "live",
  simulated: "paper",
  theoretical: "theoretical",
  historical: "warn",
  unavailable: "default",
};

export function TruthChip({ value }: { value: TruthClass }) {
  return <Badge tone={TONE[value]}>{value}</Badge>;
}

export function Metric({
  label,
  value,
  hint,
  truth,
}: {
  label: string;
  value: string;
  hint?: string;
  truth: TruthClass;
}) {
  return (
    <div className="min-w-0 rounded-lg bg-secondary/60 p-4 shadow-[var(--shadow-border)]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </p>
        <TruthChip value={truth} />
      </div>
      <p className="mt-3 font-mono text-2xl tabular-nums tracking-tight text-foreground">{value}</p>
      {hint ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
