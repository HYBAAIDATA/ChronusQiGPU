import React, { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import {
  evidenceAlert,
  evidenceRows,
  intelligenceRows,
  lossBreakdown,
  type EvidenceRow,
  type MiningEvidence,
} from "../lib/evidence";
import { TruthChip } from "./TruthChip";

/** The miner's own evidence snapshot: route, lease, plan provenance, outcome, recovery. */
export const MiningEvidencePanel: React.FC = () => {
  const [evidence, setEvidence] = useState<MiningEvidence | null>(null);
  const [offline, setOffline] = useState(false);

  const poll = useCallback(async () => {
    try {
      const response = await apiFetch("/api/v1/mining/evidence");
      if (response.ok) setEvidence((await response.json()) as MiningEvidence);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    void poll();
    const timer = window.setInterval(poll, 5000);
    return () => window.clearInterval(timer);
  }, [poll]);

  const alert = offline ? "CONTROL API UNREACHABLE" : evidenceAlert(evidence);
  const rows = evidenceRows(evidence);
  const intel = intelligenceRows(evidence);
  const losses = lossBreakdown(evidence);
  const trail = evidence?.recovery?.recent ?? [];

  return (
    <section className="console-surface mt-6" aria-labelledby="mining-evidence-title">
      <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
        <h2
          id="mining-evidence-title"
          className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f]"
        >
          Mining evidence
        </h2>
        {alert && (
          <span className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#b45309]">
            {alert}
          </span>
        )}
      </header>
      <div className="p-5 grid gap-x-8 sm:grid-cols-2">
        {rows.map((item) => (
          <Row key={item.key} item={item} />
        ))}
        {rows.length === 0 && (
          <p className="text-[13px] text-[#6b7c93] sm:col-span-2">
            {evidence?.reason ?? "Waiting for the miner to publish evidence."}
          </p>
        )}
      </div>
      {intel.length > 0 && (
        <div className="px-5 pb-5" aria-labelledby="operating-intelligence-title">
          <h3
            id="operating-intelligence-title"
            className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] mb-2"
          >
            Operating intelligence
          </h3>
          <div className="grid gap-x-8 sm:grid-cols-2">
            {intel.map((item) => (
              <Row key={item.key} item={item} />
            ))}
          </div>
          {losses.length > 0 && (
            <div className="mt-4">
              <h4 className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] mb-2">
                Where the time went
              </h4>
              <ul className="space-y-1">
                {losses.map((share) => (
                  <li key={share.key} className="flex items-center gap-3 text-[12px] font-telemetry-mono">
                    <span className="w-44 shrink-0 text-[#42566f]">{share.label}</span>
                    <span className="flex-1 h-2 bg-[rgba(10,37,64,0.06)]" aria-hidden="true">
                      <span
                        className="block h-2 bg-[#0a2540]"
                        style={{ width: `${Math.min(100, share.fraction * 100).toFixed(1)}%` }}
                      />
                    </span>
                    <span className="w-14 text-right text-[#0a2540]">{(share.fraction * 100).toFixed(1)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {trail.length > 0 && (
        <div className="px-5 pb-5">
          <h3 className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] mb-2">
            Recent recoveries
          </h3>
          <ul className="text-[12px] font-telemetry-mono text-[#42566f] space-y-1">
            {trail.map((item) => (
              <li key={item.recovery_id}>
                {item.state} · {item.recovery_id}
                {item.failure ? ` · ${item.failure}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
};

const Row: React.FC<{ item: EvidenceRow }> = ({ item }) => (
  <div className="flex items-start justify-between gap-4 py-2 border-b border-[rgba(10,37,64,0.07)]">
    <span className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] pt-0.5">
      {item.label}
    </span>
    <span className="flex items-center gap-2 text-right text-[13px] font-telemetry-mono text-[#0a2540] break-all">
      {item.value ?? <span className="text-[#6b7c93] lowercase">not reported</span>}
      <TruthChip value={item.truth} />
    </span>
  </div>
);
