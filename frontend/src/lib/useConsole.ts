import { useCallback, useEffect, useRef, useState } from "react";
import { miningDashboardAccess, type MiningDashboardAccess } from "./access";
import { apiFetch } from "./api";
import { parseConsoleStatus, type ConsoleData } from "./console";
import type { MiningEvidence } from "./evidence";
const INITIAL: MiningDashboardAccess = { allowed: false, principalId: null, role: null, reason: "checking_control_entitlement" };
const EMPTY: ConsoleData = { status: null, evidence: null, evidenceError: null, offline: false, loading: false };
export function useConsole() {
  const [access, setAccess] = useState(INITIAL);
  const [data, setData] = useState<ConsoleData>(EMPTY);
  const refreshRef = useRef<() => void>(() => {});
  const refresh = useCallback(() => refreshRef.current(), []);
  useEffect(() => {
    let disposed = false, epoch = 0, polling = false, checking = false, recheck = false;
    let current = INITIAL;
    const controllers = new Set<AbortController>();
    const request = async <T,>(run: (signal: AbortSignal) => Promise<T>): Promise<T> => {
      const controller = new AbortController(); controllers.add(controller);
      const timeout = window.setTimeout(() => controller.abort(), 10_000);
      try { return await run(controller.signal); }
      finally { window.clearTimeout(timeout); controllers.delete(controller); }
    };
    const clear = (next: MiningDashboardAccess) => {
      epoch++; current = next; setAccess(next); setData(EMPTY);
      for (const controller of controllers) controller.abort();
    };
    const poll = async () => {
      if (disposed || !current.allowed || polling) return;
      polling = true; const ticket = epoch;
      try {
        const { response, body } = await request(async signal => {
          const response = await apiFetch("/api/v1/mla1517/status", { signal, cache: "no-store" }, { interactive: false });
          return { response, body: response.ok ? await response.json() : null };
        });
        if (disposed || ticket !== epoch) return;
        if (response.status === 401 || response.status === 403) { clear({ ...current, allowed: false, reason: "control_session_not_authorized" }); return; }
        if (!response.ok) throw new Error(`status_http_${response.status}`);
        const status = parseConsoleStatus(body);
        if (disposed || ticket !== epoch) return;
        setData({ status, evidence: null, evidenceError: null, offline: false, loading: false });
        // This guardian-protected endpoint stays separate: bundling it into
        // public status would bypass subscription/tenant mediation.
        try {
          const { evidenceResponse, evidence } = await request(async signal => {
            const evidenceResponse = await apiFetch("/api/v1/mining/evidence", { signal, cache: "no-store" }, { interactive: false });
            return { evidenceResponse, evidence: evidenceResponse.ok ? await evidenceResponse.json() as MiningEvidence : null };
          });
          if (!evidenceResponse.ok) throw new Error(`evidence_http_${evidenceResponse.status}`);
          if (!evidence || typeof evidence !== "object" || typeof evidence.evidence_available !== "boolean") throw new Error("invalid_evidence_envelope");
          if (!disposed && ticket === epoch) setData({ status, evidence, evidenceError: null, offline: false, loading: false });
        } catch (error) {
          if (!disposed && ticket === epoch) setData({ status, evidence: null, evidenceError: error instanceof Error ? error.message : "evidence_unavailable", offline: false, loading: false });
        }
      } catch {
        if (!disposed && ticket === epoch) setData({ ...EMPTY, offline: true });
      } finally {
        polling = false;
        if (!disposed && ticket !== epoch && current.allowed) void poll();
      }
    };
    const check = async () => {
      if (disposed) return;
      if (checking) { recheck = true; return; }
      checking = true; const ticket = epoch;
      try {
        const next = await request(signal => miningDashboardAccess(fetch, signal));
        if (disposed || ticket !== epoch) return;
        if (!next.allowed) clear(next);
        else {
          if (current.allowed && current.principalId !== next.principalId) clear(next);
          current = next; setAccess(next);
          setData(old => ({ ...old, loading: old.status === null && !old.offline }));
          void poll();
        }
      } catch {
        if (!disposed && ticket === epoch) clear({ ...INITIAL, reason: "control_session_unreachable" });
      } finally {
        checking = false;
        if (recheck && !disposed) { recheck = false; void check(); }
      }
    };
    const changed = () => {
      // HttpOnly cookies cannot be inspected. Every session/binding event
      // invalidates old requests, even when browser identity fields stay null.
      clear({ ...INITIAL, reason: "checking_control_entitlement" });
      void check();
    };
    refreshRef.current = () => { void check(); };
    window.addEventListener("pythia-credentials-changed", changed);
    void check();
    const entitlementTimer = window.setInterval(() => { void check(); }, 30_000);
    const statusTimer = window.setInterval(() => { void poll(); }, 5_000);
    return () => {
      disposed = true; epoch++; refreshRef.current = () => {};
      window.clearInterval(entitlementTimer); window.clearInterval(statusTimer);
      window.removeEventListener("pythia-credentials-changed", changed);
      for (const controller of controllers) controller.abort();
    };
  }, []);
  return { access, ...data, refresh };
}
