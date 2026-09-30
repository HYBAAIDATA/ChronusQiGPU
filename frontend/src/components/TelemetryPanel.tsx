import React, { useCallback, useEffect, useRef, useState } from "react";
import { Activity, History, Radio } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { AuditTail, TelemetrySummary } from "../lib/status";

const fmtUptime = (s: number | undefined): string => {
  if (s == null || !Number.isFinite(s)) return "not reported";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0 ? `${h}h ${m}m ${sec}s` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
};

const fmtHs = (v: number | null | undefined): string => {
  if (v == null || !Number.isFinite(v) || v < 0) return "not reported";
  const units = ["H/s", "kH/s", "MH/s", "GH/s", "TH/s", "PH/s", "EH/s"];
  let x = v;
  let i = 0;
  while (x >= 1000 && i < units.length - 1) {
    x /= 1000;
    i++;
  }
  return `${x.toFixed(x >= 100 ? 0 : 2)} ${units[i]}`;
};

const eventDetail = (r: Record<string, unknown>): string => {
  const skip = new Set(["at", "event"]);
  return Object.entries(r)
    .filter(([k, v]) => !skip.has(k) && v != null)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" ")
    .slice(0, 160);
};

/**
 * Telemetry — live worker aggregates, session counters, and the historical
 * append-only audit trail. Every number is read from the Python control
 * plane; nothing is sampled or synthesized in the browser.
 */
export const TelemetryPanel: React.FC = () => {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null);
  const [audit, setAudit] = useState<AuditTail | null>(null);
  const [unreachable, setUnreachable] = useState(false);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [sumRes, auditRes] = await Promise.all([
        apiFetch("/api/v1/telemetry/summary"),
        apiFetch("/api/v1/audit/tail?n=30"),
      ]);
      if (sumRes.ok) setSummary((await sumRes.json()) as TelemetrySummary);
      if (auditRes.ok) setAudit((await auditRes.json()) as AuditTail);
      setUnreachable(!sumRes.ok && !auditRes.ok);
    } catch {
      setUnreachable(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    timer.current = window.setInterval(refresh, 4000);
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
    };
  }, [refresh]);

  const workers = summary?.workers ?? {};
  const events = [...(audit?.records ?? [])].reverse();

  return (
    <section className="console-surface">
      <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
        <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
          <span className="text-[#635bff]">
            <Activity className="w-4 h-4" />
          </span>
          Telemetry — live, session, historical
        </h2>
        <span className="text-[10px] font-telemetry-mono text-[#6b7c93]">
          {unreachable ? "control plane unreachable" : "measured · polled every 4s"}
        </span>
      </header>
      <div className="p-5 grid gap-4 lg:grid-cols-3">
        {/* Live */}
        <div className="console-surface-inset p-4">
          <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
            <Radio className="w-3.5 h-3.5 text-[#635bff]" /> Live
          </p>
          <dl className="mt-3 space-y-2 text-[12px] font-telemetry-mono">
            <div className="flex justify-between">
              <dt className="text-[#6b7c93]">aggregate hashrate</dt>
              <dd className="text-[#0a2540]">{fmtHs(summary?.hashrate)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[#6b7c93]">shares accepted</dt>
              <dd className="text-[#0a2540]">
                {summary?.shares_accepted ?? "not reported"}
              </dd>
            </div>
            {Object.entries(workers).map(([name, w]) => (
              <div key={name} className="flex justify-between">
                <dt className="text-[#6b7c93] truncate">{name}</dt>
                <dd className="text-[#0a2540]">
                  {fmtHs(w.effectiveness?.hashrate)} · {w.attempts_total} att
                </dd>
              </div>
            ))}
            {Object.keys(workers).length === 0 && (
              <p className="text-[#6b7c93]">no supervised workers reported</p>
            )}
          </dl>
        </div>

        {/* Session */}
        <div className="console-surface-inset p-4">
          <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
            Session (since supervisor start)
          </p>
          <dl className="mt-3 space-y-2 text-[12px] font-telemetry-mono">
            <div className="flex justify-between">
              <dt className="text-[#6b7c93]">started</dt>
              <dd className="text-[#0a2540]">
                {summary?.session?.supervisor_started_at ?? "not reported"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[#6b7c93]">uptime</dt>
              <dd className="text-[#0a2540]">{fmtUptime(summary?.session?.uptime_s)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-[#6b7c93]">attempts</dt>
              <dd className="text-[#0a2540]">
                {summary?.session?.attempts_total?.toLocaleString() ?? "not reported"}
              </dd>
            </div>
          </dl>
        </div>

        {/* Historical — audit trail */}
        <div className="console-surface-inset p-4 lg:row-span-1">
          <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
            <History className="w-3.5 h-3.5 text-[#635bff]" /> Historical — audit trail
          </p>
          <div className="mt-3 max-h-56 overflow-y-auto space-y-1.5">
            {events.length === 0 ? (
              <p className="text-[12px] font-telemetry-mono text-[#6b7c93]">
                no audit records yet
              </p>
            ) : (
              events.map((r, i) => (
                <div key={i} className="text-[11px] font-telemetry-mono">
                  <span className="text-[#8898aa]">
                    {r.at ? String(r.at).slice(11, 19) : "—"}
                  </span>{" "}
                  <span className="text-[#0a2540]">{r.event ?? "event"}</span>
                  {eventDetail(r) ? (
                    <span className="text-[#6b7c93]"> · {eventDetail(r)}</span>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
