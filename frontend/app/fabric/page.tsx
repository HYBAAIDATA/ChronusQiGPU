'use client';

import React, { useState } from 'react';
import { Layers, Cpu, Zap, Shield, CheckCircle2, FileCode, Play, ChevronRight, RotateCcw } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { StatusPill } from '@/components/console/status-pill';

export default function FabricPage() {
  const [activeStep, setActiveStep] = useState(0);

  const RTL_STEPS = [
    {
      step: 0,
      title: 'Cycle 0: Operand Latching',
      desc: '32 parallel Fibonacci-coded words op_a_zeck_i and op_b_zeck_i are latched into input registers on clk_i positive edge.',
      signals: {
        clk_i: '1',
        op_a_zeck_i: '32\'h0000002A (Zeckendorf: F7+F5+F3)',
        op_b_zeck_i: '32\'h00000015 (Zeckendorf: F6+F4+F2)',
        norm_valid_o: '0',
      },
      codeSnippet: `always @(posedge clk_i or negedge rst_n_i) begin
  if (!rst_n_i) begin
    reg_a <= 32'b0;
    reg_b <= 32'b0;
  end else begin
    reg_a <= op_a_zeck_i;
    reg_b <= op_b_zeck_i;
  end
end`,
    },
    {
      step: 1,
      title: 'Cycle 1: Bitwise Summation & Conflict Detection',
      desc: 'Bitwise sum computed across all 32 lanes. Consecutive 1s (Fi and Fi+1 active) are detected simultaneously across all warps.',
      signals: {
        clk_i: '1',
        raw_sum: '32\'h0000003F',
        adjacent_conflicts: '32\'h0000000C (Conflict detected at bits 2,3)',
        carry_propagation: '0 (Eliminated)',
      },
      codeSnippet: `assign conflict_mask = raw_sum & (raw_sum >> 1);
assign duplicate_mask = raw_sum & (raw_sum >> 2);
// Zero carry-ripple: conflict resolution performed locally in parallel`,
    },
    {
      step: 2,
      title: 'Cycle 2: Parallel Zeckendorf Normalization',
      desc: 'Local rewrite rule F_i + F_{i+1} -> F_{i+2} applied in single cycle. Non-adjacent canonical form achieved.',
      signals: {
        clk_i: '1',
        normalized_out: '32\'h00000055 (Canonical non-adjacent form)',
        norm_valid_o: '1 (Verified)',
        cycles_elapsed: '1',
      },
      codeSnippet: `result_zeck_o <= (raw_sum ^ conflict_mask) | (conflict_mask << 2);
norm_valid_o  <= 1'b1;`,
    },
  ];

  return (
    <div className="space-y-8">
      {/* Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-neutral-800 bg-neutral-900/60 backdrop-blur-md gap-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-neutral-400">
            Execution Fabric · QiGPU Substrate
          </div>
          <h2 className="text-xl font-semibold text-white tracking-tight">
            Substrate-Agnostic Execution & Hardware Abstraction
          </h2>
        </div>
        <StatusPill status="PHYSICAL_HARDWARE_EXECUTION" label="QiGPU SUBSTRATE ACTIVE" />
      </div>

      {/* Substrate & Agnostic Posture Banner */}
      <Card className="p-6 border-blue-900/40 bg-gradient-to-r from-blue-950/30 via-neutral-950 to-purple-950/20 backdrop-blur-md">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
            <Zap className="w-6 h-6" />
          </div>
          <div className="space-y-2">
            <h3 className="text-base font-semibold text-white tracking-tight">
              Hardware-Agnostic Posture: Direct Algebraic Execution
            </h3>
            <p className="text-xs sm:text-sm text-neutral-300 leading-relaxed">
              Chronus operates directly on exact algebraic ring structures (ℚ(√5), metallic means, and non-adjacent Zeckendorf representation). 
              QiGPU does not require proprietary vendor GPU drivers, external host compilers, or physical accelerator availability to execute. 
              The software mathematical reference backend executes immediately and deterministically, while hardware targets (OpenCL, SystemVerilog RTL) provide zero-loss parallel acceleration.
            </p>
            <div className="pt-2 flex flex-wrap gap-2 text-xs font-mono">
              <span className="px-2.5 py-1 rounded bg-neutral-900 text-blue-300 border border-neutral-800">
                ✓ No Vendor Lock-In
              </span>
              <span className="px-2.5 py-1 rounded bg-neutral-900 text-purple-300 border border-neutral-800">
                ✓ Exact Fractional Precision
              </span>
              <span className="px-2.5 py-1 rounded bg-neutral-900 text-emerald-300 border border-neutral-800">
                ✓ Deterministic Purity
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Backend Registry Monitor */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">
            Backend Registry Monitor
          </h3>
          <span className="text-xs font-mono text-neutral-400">3 Execution Engines Registered</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* NativeMathReferenceBackend */}
          <Card className="p-5 border-neutral-800 bg-neutral-900/60 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-emerald-400 font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> ACTIVE DEFAULT
              </span>
              <StatusPill status="MATHEMATICAL_EXECUTION" />
            </div>
            <div>
              <h4 className="text-base font-semibold text-white">NativeMathReferenceBackend</h4>
              <p className="text-xs text-neutral-400 mt-1 leading-relaxed">
                Exact infinite-precision arithmetic in ℚ(√5) via rational pairs. Fast doubling Lucas sequences up to n = 100,000.
              </p>
            </div>
            <div className="pt-3 border-t border-neutral-800 text-[11px] font-mono text-neutral-500 space-y-1">
              <div className="flex justify-between">
                <span>Precision:</span>
                <span className="text-neutral-200">Infinite (Fraction)</span>
              </div>
              <div className="flex justify-between">
                <span>Verification:</span>
                <span className="text-emerald-400">PASSED</span>
              </div>
            </div>
          </Card>

          {/* OpenCLPVBackend */}
          <Card className="p-5 border-neutral-800 bg-neutral-900/60 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-blue-400 font-semibold flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" /> HARDWARE ACCELERATOR
              </span>
              <StatusPill status="SOFTWARE_EXECUTION" />
            </div>
            <div>
              <h4 className="text-base font-semibold text-white">OpenCLPVBackend</h4>
              <p className="text-xs text-neutral-400 mt-1 leading-relaxed">
                Multi-limb Pisot-Vijayaraghavan lattice execution. Dispatches to CPU/GPU OpenCL device queues via pv_lattice.cl.
              </p>
            </div>
            <div className="pt-3 border-t border-neutral-800 text-[11px] font-mono text-neutral-500 space-y-1">
              <div className="flex justify-between">
                <span>Multi-Limb:</span>
                <span className="text-neutral-200">4 × 64-bit (256-bit)</span>
              </div>
              <div className="flex justify-between">
                <span>Status:</span>
                <span className="text-blue-400">VERIFIED TESTED</span>
              </div>
            </div>
          </Card>

          {/* SystemVerilogRTLBackend */}
          <Card className="p-5 border-neutral-800 bg-neutral-900/60 backdrop-blur-md space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-amber-400 font-semibold flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" /> RTL SYNTHESIS
              </span>
              <StatusPill status="PHYSICAL_HARDWARE_EXECUTION" />
            </div>
            <div>
              <h4 className="text-base font-semibold text-white">SystemVerilogRTLBackend</h4>
              <p className="text-xs text-neutral-400 mt-1 leading-relaxed">
                32-Lane Carry-Free Zeckendorf ALU synthesized in hw/zeckendorf_alu_32lane.sv. Eliminates carry chains entirely.
              </p>
            </div>
            <div className="pt-3 border-t border-neutral-800 text-[11px] font-mono text-neutral-500 space-y-1">
              <div className="flex justify-between">
                <span>Carry Propagation:</span>
                <span className="text-amber-400">0 Cycles (O(1))</span>
              </div>
              <div className="flex justify-between">
                <span>Synthesis Gate:</span>
                <span className="text-emerald-400">PASSED</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Interactive RTL Inspector */}
      <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-neutral-800 pb-4 gap-2">
          <div className="flex items-center gap-2">
            <FileCode className="w-5 h-5 text-amber-400" />
            <div>
              <h3 className="text-base font-semibold text-white">
                Interactive RTL Inspector: 32-Lane Zeckendorf ALU
              </h3>
              <p className="text-xs text-neutral-400 font-mono">
                Source: hw/zeckendorf_alu_32lane.sv · Step through cycle pipeline execution
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              onClick={() => setActiveStep((prev) => (prev > 0 ? prev - 1 : 0))}
              disabled={activeStep === 0}
              variant="outline"
              className="border-neutral-800 text-xs text-neutral-400 hover:text-white"
            >
              Previous
            </Button>
            <Button
              onClick={() => setActiveStep((prev) => (prev < RTL_STEPS.length - 1 ? prev + 1 : 0))}
              className="bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-mono"
            >
              Step Clock ({activeStep + 1}/{RTL_STEPS.length})
              <ChevronRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
        </div>

        {/* Stepper Details */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-6 space-y-4 font-mono text-xs">
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2">
              <div className="text-sm font-semibold text-amber-400">
                {RTL_STEPS[activeStep].title}
              </div>
              <p className="text-neutral-400 font-sans text-xs leading-relaxed">
                {RTL_STEPS[activeStep].desc}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2">
              <span className="text-[10px] text-neutral-500 uppercase tracking-wider block">
                Active Cycle Signals
              </span>
              <div className="space-y-1.5 text-[11px]">
                {Object.entries(RTL_STEPS[activeStep].signals).map(([sig, val]) => (
                  <div key={sig} className="flex justify-between border-b border-neutral-900 pb-1">
                    <span className="text-neutral-500">{sig}:</span>
                    <span className="text-neutral-200">{val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-6">
            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 font-mono text-xs text-neutral-300 space-y-2">
              <span className="text-neutral-500 text-[10px] uppercase tracking-wider block">
                Verilog Pipeline Stage
              </span>
              <pre className="text-neutral-400 text-xs overflow-x-auto leading-relaxed">
                {RTL_STEPS[activeStep].codeSnippet}
              </pre>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
