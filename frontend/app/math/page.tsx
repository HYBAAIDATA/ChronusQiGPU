'use client';
import React, { useMemo, useState } from 'react';
import { Card } from '@/components/ui/card';

function parseInteger(value: string): bigint | null {
  if (!/^-?\d+$/.test(value.trim())) return null;
  try { return BigInt(value.trim()); } catch { return null; }
}
export default function MathPage() {
  const [a, setA] = useState('3'); const [b, setB] = useState('2'); const [c, setC] = useState('1'); const [d, setD] = useState('4');
  const values = useMemo(() => [a, b, c, d].map(parseInteger), [a, b, c, d]);
  const valid = values.every((value) => value !== null);
  const output = valid ? { rational: values[0]! * values[2]! + 5n * values[1]! * values[3]!, radical: values[0]! * values[3]! + values[1]! * values[2]! } : null;
  const inputs: Array<[string, string, (value: string) => void]> = [['a', a, setA], ['b', b, setB], ['c', c, setC], ['d', d, setD]];
  return <div className="space-y-7">
    <header className="space-y-2 border-b border-neutral-800 pb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Explore / Arithmetic</p><h1 className="text-3xl font-semibold tracking-tight text-white">Q(√5) integer calculator</h1><p className="max-w-3xl text-sm leading-6 text-neutral-400">A browser-side demonstration of multiplication for integer coefficients. It uses JavaScript BigInt, avoiding Number precision loss for these integer operations; it does not call or benchmark the Chronus backend.</p></header>
    <Card className="max-w-3xl border-neutral-800 bg-neutral-900/50 p-5 sm:p-6"><div><h2 className="font-semibold text-white">Multiply (a + b√5)(c + d√5)</h2><p className="mt-1 font-mono text-xs text-neutral-500">(ac + 5bd) + (ad + bc)√5</p></div><div className="mt-5 grid grid-cols-2 gap-4">{inputs.map(([label, value, setter]) => <label key={label} className="space-y-1.5 text-sm text-neutral-300"><span>{label}</span><input inputMode="numeric" value={value} onChange={(event) => setter(event.target.value)} className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 font-mono text-white outline-none focus:border-blue-400" /></label>)}</div><div aria-live="polite" className="mt-5 rounded-lg border border-neutral-800 bg-neutral-950 p-4"><p className="text-xs uppercase tracking-wide text-neutral-500">Exact integer result</p>{output ? <p className="mt-2 break-words font-mono text-lg text-neutral-100">{output.rational.toString()} + {output.radical.toString()}√5</p> : <p className="mt-2 text-sm text-amber-300">Enter four whole-number coefficients.</p>}</div></Card>
  </div>;
}
