import { useEffect, useRef } from "react";
import { useBackend } from "@/lib/pythia/backend-store";

export function ManifoldView({ height = 420 }: { height?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const healthOk = useBackend((s) => s.health.ok);
  const workers = useBackend((s) => s.status?.workers);

  const totalAttempts = Object.values(workers ?? {}).reduce(
    (sum, w) => sum + (w.attempts_total ?? 0),
    0,
  );
  const running = healthOk && Object.values(workers ?? {}).some((w) => w.liveness);
  const cursor = totalAttempts;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let t0 = performance.now();

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
      ctx.strokeStyle = "rgba(238,234,226,0.12)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      const a = r * 0.42;
      const foci = r * 0.28;
      ctx.strokeStyle = "rgba(200,204,212,0.85)";
      cassini(ctx, cx, cy, foci, a);

      ctx.strokeStyle = "rgba(238,234,226,0.22)";
      cassini(ctx, cx, cy, foci, a * 0.72);

      const face = (cursor >>> 0) % 32;
      for (let i = 0; i < 32; i++) {
        const ang = (i / 32) * Math.PI * 2 - Math.PI / 2;
        const inner = r * 0.9;
        const outer = r * (i === face && running ? 1.08 : 1.02);
        ctx.strokeStyle = i === face ? "rgba(238,234,226,0.9)" : "rgba(238,234,226,0.18)";
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
      ctx.strokeStyle = "rgba(125,154,134,0.7)";
      ctx.stroke();

      ctx.fillStyle = "rgba(238,234,226,0.9)";
      ctx.beginPath();
      ctx.arc(cx, cy, 2.2, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "rgba(156,152,144,0.9)";
      ctx.font = "11px 'IBM Plex Mono', monospace";
      ctx.fillText("Π  Poincaré disk · Cassini oval · 32-face frame", 16, h - 16);
      ctx.fillText(`face ${String(face).padStart(2, "0")} / 32`, w - 108, h - 16);

      if (!reduce) raf = requestAnimationFrame(draw);
    };

    draw(performance.now());
    if (!reduce) raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [running, cursor]);

  return (
    <canvas
      ref={canvasRef}
      className="h-full w-full rounded-lg"
      style={{ height }}
      aria-label="Poincaré-Cassini search manifold"
    />
  );
}

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
