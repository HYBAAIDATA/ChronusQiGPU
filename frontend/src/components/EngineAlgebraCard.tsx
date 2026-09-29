import React, { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { apiFetch } from "../lib/api";
import { TruthChip } from "./TruthChip";

/** Exact certificate the miner computed for its last dispatched window (pythia.dispatch_algebra/1). */
export type DispatchAlgebra = {
  ok: boolean;
  refusal: string | null;
  claim: string;
  job_id: string | null;
  route: string;
  nonce_order: string;
  window: number;
  nonce_range: [number, number];
  ceiling: { value: number; on_lucas_ladder: boolean };
  lucas: {
    k: number;
    L_k: number;
    F_k: number;
    basis: string;
    checks: Record<string, boolean>;
  } | null;
  hendrix: {
    stride: number;
    coprime: boolean;
    scale_index: number;
    scale_lucas_value: number;
  } | null;
  first_nonces: number[] | null;
  header: { version: number; prev_hash: string; ntime: string; nbits: string } | null;
  share_target_be: string | null;
  counts?: { certified: number; refused: number };
};

type EvidenceResponse = {
  evidence_available?: boolean;
  worker_live?: boolean;
  reason?: string;
  dispatch_algebra?: DispatchAlgebra | null;
};

const CHECK_LABELS: Record<string, string> = {
  q_sqrt5_trace: "Tr(φᵏ) = Lₖ in Z[φ]",
  q_sqrt5_phi_coefficient: "φᵏ = Fₖ₋₁ + Fₖφ",
  unit_norm: "N(φᵏ) = (−1)ᵏ",
  cassini: "Lₖ² − 5Fₖ² = 4(−1)ᵏ",
  pisot_rounding: "|ψᵏ| < ½ ⇒ Lₖ = round(φᵏ)",
  l15_anchor: "L₁₅ = 1364 on the ladder",
  phase1_cassini: "Phase 1 Cassini verifier agrees",
  phase1_q_matrix_trace: "Phase 1 Tr(Qᵏ) = Lₖ",
  phase1_pisot_fold_lossless: "Phase 1 Pisot fold unfolds to Fₖ",
  phase1_m32_fabric: "Phase 1 M32 fabric: 32 sites, connected",
};

const hex = (n: number) => `0x${n.toString(16).padStart(8, "0")}`;

const Row: React.FC<{ k: string; children: React.ReactNode }> = ({ k, children }) => (
  <div className="flex items-baseline justify-between gap-4 py-1.5 border-b border-[rgba(10,37,64,0.06)] last:border-0">
    <dt className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">{k}</dt>
    <dd className="font-telemetry-mono text-xs text-[#0a2540] text-right break-all">{children}</dd>
  </div>
);

/** The ALGEBRA identities as the running miner evaluated them before its last dispatch. */
export const EngineAlgebraCard: React.FC = () => {
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const response = await apiFetch("/api/v1/mining/evidence");
        const body = (await response.json()) as EvidenceResponse;
        if (alive) {
          setEvidence(body);
          setOffline(false);
        }
      } catch {
        if (alive) setOffline(true);
      }
    };
    void load();
    const timer = window.setInterval(load, 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const cert = evidence?.dispatch_algebra ?? null;
  const reason = offline
    ? "control plane unreachable"
    : evidence?.evidence_available === false
      ? evidence.reason ?? "the miner has not published evidence"
      : "no window dispatched yet";

  return (
    <section className="console-surface">
      <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
        <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
          <span className="text-[#635bff]">
            <Cpu className="w-4 h-4" />
          </span>
          Engine runtime — last dispatched window
        </h2>
        <TruthChip value={cert ? (evidence?.worker_live ? "live" : "historical") : "unavailable"} />
      </header>
      <div className="p-5">
        {!cert ? (
          <p className="text-sm text-[#6b7c93]">Not reported: {reason}.</p>
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            <dl>
              <Row k="Certificate">{cert.ok ? "passed — dispatched" : `refused: ${cert.refusal}`}</Row>
              <Row k="Job">{cert.job_id ?? "—"}</Row>
              <Row k="Route · order">
                {cert.route} · {cert.nonce_order}
              </Row>
              <Row k="Window">
                {cert.window.toLocaleString()} nonces [{hex(cert.nonce_range[0])}, {hex(cert.nonce_range[1])})
              </Row>
              {cert.lucas ? (
                <Row k="Lucas basis">
                  k = {cert.lucas.k} · Lₖ = {cert.lucas.L_k.toLocaleString()} · {cert.lucas.basis}
                </Row>
              ) : null}
              <Row k="Ceiling">
                {cert.ceiling.value.toLocaleString()}
                {cert.ceiling.on_lucas_ladder ? " (Lucas)" : ""}
              </Row>
              {cert.hendrix ? (
                <Row k="Hendrix stride">
                  {cert.hendrix.stride} · gcd = 1: {cert.hendrix.coprime ? "yes" : "no"} · scale L
                  {cert.hendrix.scale_index} = {cert.hendrix.scale_lucas_value}
                </Row>
              ) : null}
              <Row k="First nonces">
                {cert.first_nonces ? cert.first_nonces.map(hex).join(" ") : "not materialised"}
              </Row>
              {cert.counts ? (
                <Row k="Dispatches">
                  {cert.counts.certified.toLocaleString()} certified · {cert.counts.refused.toLocaleString()} refused
                </Row>
              ) : null}
            </dl>
            <div>
              <ul className="space-y-1.5">
                {Object.entries(cert.lucas?.checks ?? {}).map(([name, held]) => (
                  <li key={name} className="flex items-center justify-between font-telemetry-mono text-xs">
                    <span className="text-[#42566f]">{CHECK_LABELS[name] ?? name}</span>
                    <span className={held ? "text-[#067647]" : "text-[#b42318]"}>{held ? "holds" : "fails"}</span>
                  </li>
                ))}
              </ul>
              {cert.header ? (
                <p className="mt-4 font-telemetry-mono text-[11px] leading-5 text-[#6b7c93] break-all">
                  header v{cert.header.version} · prev {cert.header.prev_hash.slice(0, 16)}… · ntime{" "}
                  {cert.header.ntime} · nbits {cert.header.nbits}
                </p>
              ) : null}
              <p className="mt-3 text-[11px] font-telemetry-mono leading-5 text-[#6b7c93]">{cert.claim}</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
