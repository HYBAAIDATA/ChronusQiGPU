import React, { useEffect, useRef } from "react";
import { Waypoints } from "lucide-react";
import { TruthChip } from "../components/TruthChip";
import type { MlaStatus } from "../lib/status";

/**
 * Poincaré/Cassini search-manifold visualization, ported from
 * legacy/PYTHIA_Frontend manifold-view.tsx. The 32-face cursor is driven by
 * real worker attempt counts; the traversal trace is a *simulated* depiction —
 * it is not evidence of a SHA-256 shortcut.
 */
export const ManifoldView: React.FC<{ status: MlaStatus | null; offline: boolean }> = ({
  status,
  offline,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const workers = status?.workers ?? {};
  const totalAttempts = Object.values(workers).reduce(
    (sum, w) => sum + (w.attempts_total ?? 0),
    0,
  );
  const running =
    !offline && Object.values(workers).some((w) => w.liveness);
  const cursor = totalAttempts;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const t0 = performance.now();

    const draw = (now: number) => {
      const t = (now - t0) / 1000;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const r = Math.min(w, h) * 0.38;
      ctx.strokeStyle = "rgba(10,37,64,0.12)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      const a = r * 0.42;
      const foci = r * 0.28;
      ctx.strokeStyle = "rgba(99,91,255,0.75)";
      cassini(ctx, cx, cy, foci, a);

      ctx.strokeStyle = "rgba(10,37,64,0.20)";
      cassini(ctx, cx, cy, foci, a * 0.72);

      const face = (cursor >>> 0) % 32;
      for (let i = 0; i < 32; i++) {
        const ang = (i / 32) * Math.PI * 2 - Math.PI / 2;
        const inner = r * 0.9;
        const outer = r * (i === face && running ? 1.08 : 1.02);
        ctx.strokeStyle =
          i === face ? "rgba(4,120,87,0.9)" : "rgba(10,37,64,0.16)";
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(ang) * inner, cy + Math.sin(ang) * inner);
        ctx.lineTo(cx + Math.cos(ang) * outer, cy + Math.sin(ang) * outer);
        ctx.stroke();
      }

      const phi = 1.6180339887;
      const steps = 48;
      ctx.beginPath();
      for (let i = 0; i < steps; i++) {
        const u = ((reduce ? 0.12 : t * (running ? 0.18 : 0.05)) + i / phi) % 1;
        const ang = u * Math.PI * 2;
        const rad = r * (0.18 + 0.55 * ((i * phi) % 1));
        const x = cx + Math.cos(ang) * rad;
        const y = cy + Math.sin(ang) * rad;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(180,83,9,0.55)";
      ctx.stroke();

      ctx.fillStyle = "rgba(10,37,64,0.9)";
      ctx.beginPath();
      ctx.arc(cx, cy, 2.2, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "rgba(107,124,147,0.9)";
      ctx.font = "11px 'IBM Plex Mono', monospace";
      ctx.fillText("Π  Poincaré disk · Cassini oval · 32-face frame", 16, h - 16);
      ctx.fillText(`face ${String(face).padStart(2, "0")} / 32`, w - 108, h - 16);

      if (!reduce) raf = requestAnimationFrame(draw);
    };

    draw(performance.now());
    if (!reduce) raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [running, cursor]);

  const face = (cursor >>> 0) % 32;

  return (
    <div className="space-y-6 pt-8">
      <div>
        <p className="text-[11px] font-telemetry-mono uppercase tracking-[0.28em] text-[#635bff]">
          Search manifold
        </p>
        <h1 className="font-serif-display mt-3 text-4xl sm:text-5xl font-semibold tracking-tight text-[#0a2540]">
          Poincaré–Cassini traversal, driven by measured attempts.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#42566f]">
          The face cursor indexes real worker attempts modulo 32. The golden
          winding trace is a simulated depiction of the traversal heuristic —
          it is not a measurement and it is not a SHA-256 shortcut.
        </p>
      </div>

      <section className="console-surface">
        <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
          <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
            <Waypoints className="w-4 h-4 text-[#635bff]" />
            32-face frame — live cursor from worker attempts
          </h2>
          <TruthChip value="simulated" />
        </header>
        <div className="p-5">
          <div className="console-surface-inset">
            <canvas
              ref={canvasRef}
              className="w-full rounded-[3px]"
              style={{ height: 420 }}
              aria-label="Poincaré-Cassini search manifold"
            />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3 text-[12px] font-telemetry-mono">
            <p className="flex justify-between console-surface-inset px-4 py-3">
              <span className="text-[#6b7c93]">total attempts</span>
              <span className="text-[#0a2540]">{totalAttempts.toLocaleString()}</span>
            </p>
            <p className="flex justify-between console-surface-inset px-4 py-3">
              <span className="text-[#6b7c93]">current face</span>
              <span className="text-[#0a2540]">{face} / 32</span>
            </p>
            <p className="flex justify-between console-surface-inset px-4 py-3">
              <span className="text-[#6b7c93]">workers live</span>
              <span className={running ? "text-[#067647]" : "text-[#b45309]"}>
                {running ? "yes" : "no"}
              </span>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

function cassini(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  foci: number,
  a: number,
) {
  ctx.beginPath();
  let first = true;
  for (let i = 0; i <= 360; i++) {
    const th = (i / 360) * Math.PI * 2;
    const c = Math.cos(th);
    const s = Math.sin(th);
    const d = Math.pow(a, 4) - 4 * foci * foci * a * a * c * c + 2 * foci * foci * a * a;
    const r2 = foci * foci * c * c + Math.sqrt(Math.max(0, d));
    const r = Math.sqrt(Math.max(0, r2));
    const x = cx + r * c * 0.55;
    const y = cy + r * s * 0.55;
    if (first) {
      ctx.moveTo(x, y);
      first = false;
    } else ctx.lineTo(x, y);
  }
  ctx.stroke();
}
