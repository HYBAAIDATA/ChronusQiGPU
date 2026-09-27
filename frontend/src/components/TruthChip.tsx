import React from "react";
import type { TruthClass } from "../lib/truth";

const TONE: Record<TruthClass, string> = {
  live: "text-[#067647] border-[rgba(4,120,87,0.35)] bg-[rgba(4,120,87,0.08)]",
  measured: "text-[#067647] border-[rgba(4,120,87,0.35)] bg-[rgba(4,120,87,0.08)]",
  computed: "text-[#2563eb] border-[rgba(37,99,235,0.35)] bg-[rgba(37,99,235,0.08)]",
  simulated: "text-[#2563eb] border-[rgba(37,99,235,0.35)] bg-[rgba(37,99,235,0.08)]",
  theoretical: "text-[#b45309] border-[rgba(180,83,9,0.35)] bg-[rgba(180,83,9,0.08)]",
  historical: "text-[#b45309] border-[rgba(180,83,9,0.35)] bg-[rgba(180,83,9,0.08)]",
  hypothesis: "text-[#7c3aed] border-[rgba(124,58,237,0.35)] bg-[rgba(124,58,237,0.08)]",
  unavailable: "text-[#42566f] border-[rgba(107,124,147,0.35)] bg-[rgba(107,124,147,0.08)]",
};

/** Provenance chip — every figure on a view carries its truth class. */
export const TruthChip: React.FC<{ value: TruthClass }> = ({ value }) => (
  <span
    className={`px-2 py-0.5 rounded-[2px] border text-[10px] font-telemetry-mono uppercase tracking-wider ${TONE[value]}`}
  >
    {value}
  </span>
);
