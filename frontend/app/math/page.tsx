'use client';

import React, { useState } from 'react';
import { Binary, Calculator, Check, ArrowRight, Zap, Sparkles } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { StatusPill } from '@/components/console/status-pill';

export default function MathPage() {
  // Q(sqrt(5)) inputs: (a + b*sqrt(5)) * (c + d*sqrt(5))
  const [a, setA] = useState('3');
  const [b, setB] = useState('2');
  const [c, setC] = useState('1');
  const [d, setD] = useState('4');

  // Exact multiplication in Q(sqrt(5)): (ac + 5bd) + (ad + bc)*sqrt(5)
  const aNum = parseInt(a, 10) || 0;
  const bNum = parseInt(b, 10) || 0;
  const cNum = parseInt(c, 10) || 0;
  const dNum = parseInt(d, 10) || 0;

  const resRational = aNum * cNum + 5 * bNum * dNum;
  const resRadical = aNum * dNum + bNum * cNum;

  // Metallic family selector
  const [selectedMetallic, setSelectedMetallic] = useState(1);
  const metallicFamilies = [
    {
      m: 1,
      name: 'Golden Mean (Ï†)',
      symbol: 'Ï†',
      poly: 'Î»Â² - Î» - 1 = 0',
      root: '(1 + âˆš5) / 2 â‰ˆ 1.6180339887...',
      conjugate: '(1 - âˆš5) / 2 â‰ˆ -0.6180339887...',
      decay: 'O(Ï†^-n) asymptotic decay',
      field: 'Q(âˆš5)',
    },
    {
      m: 2,
      name: 'Silver Mean (Î´_S)',
      symbol: 'Î´_S',
      poly: 'Î»Â² - 2Î» - 1 = 0',
      root: '1 + âˆš2 â‰ˆ 2.4142135623...',
      conjugate: '1 - âˆš2 â‰ˆ -0.4142135623...',
      decay: 'O(Î´_S^-n) exponential contraction',
      field: 'Q(âˆš2)',
    },
    {
      m: 3,
      name: 'Bronze Mean (Î´_B)',
      symbol: 'Î´_B',
      poly: 'Î»Â² - 3Î» - 1 = 0',
      root: '(3 + âˆš13) / 2 â‰ˆ 3.3027756377...',
      conjugate: '(3 - âˆš13) / 2 â‰ˆ -0.3027756377...',
      decay: 'O(Î´_B^-n) ultra-fast contraction',
      field: 'Q(âˆš13)',
    },
  ];

  const currentFamily = metallicFamilies.find((f) => f.m === selectedMetallic) || metallicFamilies[0];

  return (
    <div className="space-y-8">
      {/* Executive Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-neutral-800 bg-neutral-900/60 backdrop-blur-md gap-4">
        <div>
          <div className="text-xs font-mono uppercase tracking-wider text-neutral-400">
            Algebraic Ring Engine Â· Field Arithmetic
          </div>
          <h2 className="text-xl font-semibold text-white tracking-tight">
            Exact Mathematical Engine & Metallic Contraction
          </h2>
        </div>
        <StatusPill status="MATHEMATICAL_EXECUTION" label="EXACT ALGEBRA" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Interactive Q(sqrt(5)) Multiplier */}
        <div className="lg:col-span-6 space-y-6">
          <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-5">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <Calculator className="w-4 h-4 text-purple-400" />
                <h3 className="text-base font-semibold text-white">
                  Exact Field Multiplier in \(\mathbb&#123;Q&#125;(\sqrt&#123;5&#125;)\)
                </h3>
              </div>
              <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                0 ROUND-OFF
              </span>
            </div>

            <p className="text-xs text-neutral-300 leading-relaxed font-mono">
              Numbers are evaluated strictly as rational pairs \((a, b) \in \mathbb&#123;Q&#125;^2\):
              <br />
              <span className="text-purple-300 block mt-1">
                (a + bâˆš5) Â· (c + dâˆš5) = (ac + 5bd) + (ad + bc)âˆš5
              </span>
            </p>

            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-neutral-400">Operand 1: a (Real)</label>
                  <Input
                    type="number"
                    value={a}
                    onChange={(e) => setA(e.target.value)}
                    className="bg-neutral-950 border-neutral-800 text-white font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-neutral-400">Operand 1: b (âˆš5)</label>
                  <Input
                    type="number"
                    value={b}
                    onChange={(e) => setB(e.target.value)}
                    className="bg-neutral-950 border-neutral-800 text-white font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-neutral-400">Operand 2: c (Real)</label>
                  <Input
                    type="number"
                    value={c}
                    onChange={(e) => setC(e.target.value)}
                    className="bg-neutral-950 border-neutral-800 text-white font-mono"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-neutral-400">Operand 2: d (âˆš5)</label>
                  <Input
                    type="number"
                    value={d}
                    onChange={(e) => setD(e.target.value)}
                    className="bg-neutral-950 border-neutral-800 text-white font-mono"
                  />
                </div>
              </div>

              {/* Exact Computed Output */}
              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 font-mono space-y-2">
                <span className="text-neutral-500 text-[10px] uppercase tracking-wider block">
                  Deterministic Exact Product
                </span>
                <div className="text-lg font-semibold text-emerald-400">
                  {resRational} + {resRadical}âˆš5
                </div>
                <div className="text-[11px] text-neutral-500">
                  Real = {aNum}Ã—{cNum} + 5({bNum}Ã—{dNum}) = {resRational} Â· Irrational = {aNum}Ã—{dNum} + {bNum}Ã—{cNum} = {resRadical}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right: Metallic Means Family Explorer */}
        <div className="lg:col-span-6 space-y-6">
          <Card className="p-6 border-neutral-800 bg-neutral-900/70 backdrop-blur-md space-y-5">
            <div className="flex items-center justify-between border-b border-neutral-800 pb-3">
              <div className="flex items-center gap-2">
                <Binary className="w-4 h-4 text-blue-400" />
                <h3 className="text-base font-semibold text-white">
                  Metallic Means Family (\(m \ge 1\))
                </h3>
              </div>
              <span className="text-xs font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                PISOT SCALING
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {metallicFamilies.map((fam) => (
                <button
                  key={fam.m}
                  onClick={() => setSelectedMetallic(fam.m)}
                  className={`p-3 rounded-lg border text-left font-mono transition-all ${
                    selectedMetallic === fam.m
                      ? 'bg-blue-600/20 border-blue-500 text-blue-300 font-semibold shadow-sm'
                      : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:border-neutral-700'
                  }`}
                >
                  <div className="text-xs text-neutral-400">{fam.name}</div>
                  <div className="text-sm text-white font-bold mt-1">{fam.symbol}</div>
                </button>
              ))}
            </div>

            <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 font-mono text-xs space-y-3">
              <div>
                <span className="text-neutral-500 text-[10px] block">CHARACTERISTIC POLYNOMIAL</span>
                <span className="text-white text-sm font-semibold">{currentFamily.poly}</span>
              </div>
              <div>
                <span className="text-neutral-500 text-[10px] block">DOMINANT EIGENVALUE (PISOT)</span>
                <span className="text-emerald-400">{currentFamily.root}</span>
              </div>
              <div>
                <span className="text-neutral-500 text-[10px] block">ALGEBRAIC CONJUGATE (|&lambda;*| &lt; 1)</span>
                <span className="text-purple-400">{currentFamily.conjugate}</span>
              </div>
              <div>
                <span className="text-neutral-500 text-[10px] block">CONTRACTION BOUND</span>
                <span className="text-amber-400 font-semibold">{currentFamily.decay}</span>
              </div>
            </div>

            <p className="text-xs text-neutral-400 leading-relaxed font-mono">
              Because all algebraic conjugates strictly satisfy \(|\lambda^*| &lt; 1\), powers of the dominant root contract exponentially towards integers, guaranteeing bounded integer-lattice distance without floating-point error.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
