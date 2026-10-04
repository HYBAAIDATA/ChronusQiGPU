import { useMemo, useRef, useState, type ReactNode } from "react";
import { Play, RotateCcw, SquareTerminal } from "lucide-react";
import { DEMO_SCRIPT, QuantumConsole } from "@/lib/vqc/console";
import { foldReport } from "@/lib/vqc/custody";

const BELL = ["init 2", "h 0", "cx 0 1", "psi", "prob"];
const WIDE = ["init 10000", "h 0", "cx 0 9999", "status"];
const CLOSED = ["walk 10000 pi/4", "anneal 10000", "tunnel"];
const CYCLE = ["walk cycle 8 3"];
const SCALE = ["scale", "scale 15 17", "scale budget 15 17 1364", "scale 15 16"];
const FOLD = ["fold"];
const CURE = ["cure"];
const THREAD = ["thread"];
const ALGEBRA = ["algebra"];
const CLASSICS = ["classics"];
const HENDRIX = ["hendrix", "advances", "finale", "rank", "ontology", "signal", "store", "triad"];

type Entry = { line: string; output: string };

export function TuringApp() {
  const machine = useRef(new QuantumConsole());
  const [surface, setSurface] = useState<"console" | "contract">("console");
  const [flowStep, setFlowStep] = useState(0);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<Entry[]>([]);
  const [rev, setRev] = useState(0);
  const custody = useMemo(() => foldReport(), []);
  void rev;

  function runLine(line: string) {
    const output = machine.current.do(line);
    setLog((prev) => [...prev, { line, output }]);
    setRev((value) => value + 1);
  }

  function runScript(lines: readonly string[]) {
    setBusy(true);
    for (const line of lines) runLine(line);
    if (lines === DEMO_SCRIPT) setFlowStep(DEMO_SCRIPT.length);
    setBusy(false);
  }

  function submit(typed: string) {
    const text = typed.trim() || (flowStep < DEMO_SCRIPT.length ? DEMO_SCRIPT[flowStep] : "");
    if (!text) return;
    runLine(text);
    if (!typed.trim() || typed.trim() === DEMO_SCRIPT[flowStep]) {
      setFlowStep((step) => Math.min(DEMO_SCRIPT.length, step + 1));
    }
    setDraft("");
  }

  function reset() {
    machine.current = new QuantumConsole();
    setLog([]);
    setFlowStep(0);
    setDraft("");
    setRev((value) => value + 1);
  }

  const suggestion = DEMO_SCRIPT[flowStep] ?? "help";
  const bars = machine.current.bars;
  const diagram = machine.current.diagram;

  return (
    <main className="flex min-h-screen flex-col bg-canvas text-ink">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-5 sm:px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-mono text-xs tracking-wide text-faint">Computational Intelligence as a Service</p>
              <h1 className="font-display text-4xl font-medium tracking-tight sm:text-5xl">HYBA</h1>
              <p className="mt-2 max-w-xl text-sm leading-normal text-muted">
                One substrate, not a license. Zeckendorf and Binet fold. Fibonacci and Cassini store. Lucas and Pisot scale. A decimal in place of those integers is refused.
              </p>
            </div>
            <p className="font-mono text-xs text-faint">no approximation</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SurfaceTab label="Console" current={surface === "console"} onClick={() => setSurface("console")} />
            <SurfaceTab label="Contract" current={surface === "contract"} onClick={() => setSurface("contract")} />
          </div>
          {surface === "console" ? (
            <div className="flex gap-2 overflow-x-auto">
              <Chip icon={<Play className="size-4" />} label="Demo" disabled={busy} onClick={() => runScript(DEMO_SCRIPT)} />
              <Chip icon={<SquareTerminal className="size-4" />} label="Bell pair" disabled={busy} onClick={() => runScript(BELL)} />
              <Chip label="10,000 qubits" disabled={busy} onClick={() => runScript(WIDE)} />
              <Chip label="Closed form" disabled={busy} onClick={() => runScript(CLOSED)} />
              <Chip label="Cycle walk" disabled={busy} onClick={() => runScript(CYCLE)} />
              <Chip label="Lucas scale" disabled={busy} onClick={() => runScript(SCALE)} />
              <Chip label="Fold" disabled={busy} onClick={() => runScript(FOLD)} />
              <Chip label="Cure" disabled={busy} onClick={() => runScript(CURE)} />
              <Chip label="One thread" disabled={busy} onClick={() => runScript(THREAD)} />
              <Chip label="Algebra" disabled={busy} onClick={() => runScript(ALGEBRA)} />
              <Chip label="Classics" disabled={busy} onClick={() => runScript(CLASSICS)} />
              <Chip label="Hendrix" disabled={busy} onClick={() => runScript(HENDRIX)} />
              <Chip icon={<RotateCcw className="size-4" />} label="Clear" disabled={busy} onClick={reset} />
            </div>
          ) : null}
        </div>
      </header>

      {surface === "console" ? (
        <div className="mx-auto grid w-full max-w-6xl flex-1 gap-4 px-4 py-4 sm:px-6 lg:grid-cols-3">
          <section className="flex min-h-[32rem] flex-col rounded-panel border border-line bg-panel lg:col-span-2">
            <pre className="flex-1 overflow-auto whitespace-pre-wrap p-4 font-mono text-xs leading-relaxed text-ink">
              {log.length
                ? log.map((entry) => `> ${entry.line}\n${entry.output}`).join("\n\n")
                : machine.current.banner()}
            </pre>
            <form
              className="flex gap-2 border-t border-line p-3"
              onSubmit={(event) => {
                event.preventDefault();
                submit(draft);
              }}
            >
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={suggestion}
                spellCheck={false}
                className="h-11 flex-1 rounded-lg border border-line bg-panel-2 px-3 font-mono text-sm text-ink outline-none"
              />
              <button
                type="submit"
                disabled={busy || (!draft.trim() && flowStep >= DEMO_SCRIPT.length)}
                className="h-11 rounded-lg bg-accent px-4 text-sm font-medium text-accent-ink disabled:opacity-40"
              >
                Enter
              </button>
            </form>
          </section>
          <aside className="flex flex-col gap-4">
            <Panel title="Readout">
              {bars.length ? (
                <ul className="space-y-2">
                  {bars.map((bar) => (
                    <li key={bar.label} className="font-mono text-xs">
                      <div className="flex justify-between gap-3 text-muted">
                        <span>{bar.label}</span>
                        <span className="text-ink">{bar.text}</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-panel-2">
                        <div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(1, bar.weight)) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">Exact probabilities appear here. A decimal is never the value.</p>
              )}
            </Panel>
            {diagram ? (
              <Panel title="Diagram">
                <pre className="overflow-auto font-mono text-xs leading-relaxed">{diagram}</pre>
              </Panel>
            ) : null}
          </aside>
        </div>
      ) : (
        <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
          <pre className="overflow-auto whitespace-pre-wrap rounded-panel border border-line bg-panel p-5 font-mono text-xs leading-relaxed">{custody}</pre>
        </div>
      )}
    </main>
  );
}

function SurfaceTab({ label, current, onClick }: { label: string; current: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs ${current ? "border-accent bg-accent text-accent-ink" : "border-line text-muted"}`}
    >
      {label}
    </button>
  );
}

function Chip({
  label,
  onClick,
  disabled,
  icon,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-9 shrink-0 items-center gap-2 rounded-full border border-line bg-panel px-3 text-xs text-ink disabled:opacity-40"
    >
      {icon}
      {label}
    </button>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-panel border border-line bg-panel p-4">
      <h2 className="mb-3 font-mono text-xs tracking-wide text-faint">{title}</h2>
      {children}
    </section>
  );
}
