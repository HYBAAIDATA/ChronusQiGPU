import React, { useMemo } from "react";
import { Download, ShieldCheck } from "lucide-react";
import { TruthChip } from "../components/TruthChip";
import { IMPLEMENTED, runAudit } from "../lib/audit";
import type { MlaStatus } from "../lib/status";

const GROUP_ORDER = ["consensus", "algebra", "integrity", "uat"] as const;

/** Audit trail — local evidence checks plus a downloadable evidence pack. */
export const AuditView: React.FC<{ status: MlaStatus | null }> = ({ status }) => {
  const checks = useMemo(() => runAudit(), []);
  const passed = checks.filter((c) => c.passed).length;

  const downloadPack = () => {
    const pack = {
      schema: "pythia.audit_pack/1",
      generated_at: new Date().toISOString(),
      checks,
      status_snapshot: {
        generated_at: status?.generated_at ?? null,
        backend: status?.backend ?? null,
        workers: Object.fromEntries(
          Object.entries(status?.workers ?? {}).map(([k, w]) => [
            k,
            {
              state: w.state,
              liveness: w.liveness,
              attempts_total: w.attempts_total,
              hashrate: w.effectiveness?.hashrate ?? null,
            },
          ]),
        ),
        stratum_connected: status?.stratum?.connected ?? false,
        device_available: status?.device?.available ?? false,
      },
    };
    const blob = new Blob([JSON.stringify(pack, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pythia-audit-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 pt-8">
      <div>
        <p className="text-[11px] font-telemetry-mono uppercase tracking-[0.28em] text-[#635bff]">
          Audit trail
        </p>
        <h1 className="font-serif-display mt-3 text-4xl sm:text-5xl font-semibold tracking-tight text-[#0a2540]">
          {passed}/{checks.length} checks — evidence, not narrative.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#42566f]">
          Every check below executes locally against exact BigInt arithmetic and
          the SHA-256d consensus vectors. The evidence pack serializes this run
          plus a measured backend snapshot.
        </p>
        <button
          className="mt-5 px-3 py-1.5 rounded-md border border-[rgba(99,91,255,0.35)] bg-[rgba(99,91,255,0.10)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#635bff] hover:bg-[rgba(99,91,255,0.18)] transition-colors"
          onClick={downloadPack}
        >
          <Download className="w-3 h-3 inline mr-1" /> download evidence pack
        </button>
      </div>

      {GROUP_ORDER.map((group) => {
        const rows = checks.filter((c) => c.group === group);
        if (rows.length === 0) return null;
        return (
          <section key={group} className="console-surface">
            <header className="px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
              <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f]">
                {group}
              </h2>
            </header>
            <div className="p-5 space-y-2">
              {rows.map((c) => (
                <div
                  key={c.id}
                  className="console-surface-inset px-4 py-3 flex items-start justify-between gap-4"
                >
                  <div className="min-w-0">
                    <p className="text-[12px] font-telemetry-mono text-[#0a2540]">
                      <span className="text-[#6b7c93]">{c.id}</span> · {c.name}
                    </p>
                    <p className="mt-1 text-[11px] font-telemetry-mono leading-5 text-[#42566f]">
                      {c.detail}
                    </p>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded-[2px] border text-[10px] font-telemetry-mono uppercase tracking-wider shrink-0 ${
                      c.passed
                        ? "text-[#067647] border-[rgba(4,120,87,0.35)]"
                        : "text-[#df1b41] border-[rgba(223,27,65,0.35)]"
                    }`}
                  >
                    {c.passed ? "pass" : "fail"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        );
      })}

      <section className="console-surface">
        <header className="px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
          <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#635bff]" />
            Honesty invariants
          </h2>
        </header>
        <div className="p-5 grid gap-2 md:grid-cols-2">
          {IMPLEMENTED.map((i) => (
            <div key={i.id} className="console-surface-inset px-4 py-3">
              <p className="text-[12px] font-telemetry-mono text-[#0a2540]">
                <span className="text-[#6b7c93]">{i.id}</span> · {i.title}
              </p>
              <p className="mt-1 text-[11px] font-telemetry-mono leading-5 text-[#42566f]">
                {i.fix}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
