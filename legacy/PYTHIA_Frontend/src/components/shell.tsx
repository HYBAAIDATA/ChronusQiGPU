import { Link, useRouterState } from "@tanstack/react-router";
import {
  FunctionSquare,
  Hexagon,
  LayoutDashboard,
  Network,
  ShieldCheck,
  SquareTerminal,
} from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useBackend } from "@/lib/pythia/backend-store";

const NAV = [
  { to: "/", label: "Operations", short: "Ops", icon: LayoutDashboard },
  { to: "/console", label: "Console", short: "Mine", icon: SquareTerminal },
  { to: "/algebra", label: "Algebra", short: "Math", icon: FunctionSquare },
  { to: "/intelligence", label: "Intelligence", short: "Intel", icon: Network },
  { to: "/manifold", label: "Manifold", short: "Field", icon: Hexagon },
  { to: "/audit", label: "Audit", short: "Audit", icon: ShieldCheck },
] as const;

export function Shell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const health = useBackend((s) => s.health);
  const status = useBackend((s) => s.status);
  const polling = useBackend((s) => s.polling);
  const recovery = useBackend((s) => s.recovery);

  const stratumConnected = status?.stratum?.connected ?? false;
  const workers = status?.workers ?? {};
  const anyRunning = Object.values(workers).some(
    (w) => w.state === "running" || w.state === "ready" || w.liveness,
  );
  const failClosed = recovery?.state === "circuit_open" || recovery?.state === "fail_closed";

  return (
    <TooltipProvider>
      <div className="min-h-dvh bg-background text-foreground">
        <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-sm">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
            <Link to="/" className="flex items-center gap-3">
              <Mark />
              <div className="leading-none">
                <p className="font-display text-lg tracking-tight">PYTHIA</p>
                <p className="mt-1 hidden text-[10px] uppercase tracking-[0.22em] text-muted-foreground sm:block">
                  Algebraic operator
                </p>
              </div>
            </Link>
            <nav className="hidden items-center gap-1 md:flex">
              {NAV.map((item) => {
                const active = pathname === item.to;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "flex h-10 items-center gap-2 rounded-md px-3 text-sm text-muted-foreground transition-colors hover:text-foreground",
                      active && "bg-secondary text-foreground",
                    )}
                  >
                    <Icon className="size-3.5" strokeWidth={1.75} />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <StatusPill
              healthOk={health.ok}
              stratumConnected={stratumConnected}
              running={anyRunning}
              failClosed={failClosed}
              polling={polling}
            />
          </div>
        </header>
        <main className="mx-auto w-full min-w-0 max-w-6xl overflow-x-hidden px-4 pb-28 pt-8 md:pb-16">{children}</main>
        <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] md:hidden">
          <div className="grid grid-cols-6">
            {NAV.map((item) => {
              const active = pathname === item.to;
              const Icon = item.icon;
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "flex min-h-14 flex-col items-center justify-center gap-1 text-[10px] text-muted-foreground",
                    active && "text-foreground",
                  )}
                >
                  <Icon className="size-4" strokeWidth={1.75} />
                  {item.short}
                </Link>
              );
            })}
          </div>
        </nav>
      </div>
    </TooltipProvider>
  );
}

function StatusPill({
  healthOk,
  stratumConnected,
  running,
  failClosed,
  polling,
}: {
  healthOk: boolean;
  stratumConnected: boolean;
  running: boolean;
  failClosed: boolean;
  polling: boolean;
}) {
  const label = failClosed
    ? "fail closed"
    : !healthOk
      ? "backend offline"
      : running
        ? stratumConnected
          ? "mining live"
          : "workers up"
        : stratumConnected
          ? "stratum up"
          : polling
            ? "idle"
            : "offline";
  const tone = failClosed
    ? "text-destructive"
    : !healthOk
      ? "text-muted-foreground"
      : running || stratumConnected
        ? "text-live"
        : "text-muted-foreground";
  return (
    <div className={cn("flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest", tone)}>
      <span
        className={cn(
          "size-1.5 rounded-full",
          failClosed
            ? "bg-destructive"
            : !healthOk
              ? "bg-muted-foreground/50"
              : running || stratumConnected
                ? "bg-live"
                : "bg-muted-foreground/50",
        )}
      />
      {label}
    </div>
  );
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="size-8 text-accent" aria-hidden>
      <ellipse cx="12" cy="16" rx="7.2" ry="10" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <ellipse cx="20" cy="16" rx="7.2" ry="10" fill="none" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

/** Boot-time driver: start backend polling once; no browser mining loop. */
export function BackendDriver() {
  const startPolling = useBackend((s) => s.startPolling);
  const stopPolling = useBackend((s) => s.stopPolling);
  useEffect(() => {
    startPolling();
    return () => stopPolling();
  }, [startPolling, stopPolling]);
  return null;
}

/** @deprecated Use BackendDriver — mock MiningEngine path removed. */
export const EngineDriver = BackendDriver;
