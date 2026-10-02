import { AsyncLocalStorage } from "node:async_hooks";
import { randomBytes } from "node:crypto";
import { monitorEventLoopDelay } from "node:perf_hooks";

const counters = new Map<string, number>();
const histograms = new Map<string, number[]>();
const traceStorage = new AsyncLocalStorage<{
  traceId: string;
  spanId: string;
  traceFlags: string;
}>();
const eventLoopDelay = monitorEventLoopDelay({ resolution: 10 });
eventLoopDelay.enable();

const EVENT_LOOP_DROWNING_NS = 500_000_000;

export function logEvent(
  evt: string,
  fields: Record<string, unknown> = {},
): void {
  console.log(
    JSON.stringify({
      evt,
      ts: new Date().toISOString(),
      ...traceStorage.getStore(),
      ...fields,
    }),
  );
}

export function increment(name: string, labels = "", by = 1): void {
  const key = labels ? `${name}{${labels}}` : name;
  counters.set(key, (counters.get(key) ?? 0) + by);
}

export function observe(name: string, labels: string, value: number): void {
  const key = labels ? `${name}{${labels}}` : name;
  const values = histograms.get(key) ?? [];
  values.push(value);
  if (values.length > 1000) values.shift();
  histograms.set(key, values);
}

export async function withTrace<T>(
  name: string,
  operation: () => Promise<T>,
  incomingTraceparent?: string,
): Promise<T> {
  const parent = traceStorage.getStore();
  const remote = parseW3cTraceparent(incomingTraceparent);
  const context = {
    traceId: parent?.traceId ?? remote?.traceId ?? randomHex(16),
    spanId: randomHex(8),
    traceFlags: parent?.traceFlags ?? remote?.traceFlags ?? "01",
  };
  const started = Date.now();
  return traceStorage.run(context, async () => {
    try {
      const result = await operation();
      logEvent("span", { name, status: "ok", durationMs: Date.now() - started });
      return result;
    } catch (error) {
      logEvent("span", {
        name,
        status: "error",
        durationMs: Date.now() - started,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  });
}

export function currentTraceparent(): string | undefined {
  const context = traceStorage.getStore();
  if (!context) return undefined;
  return `00-${context.traceId}-${context.spanId}-${context.traceFlags}`;
}

export function parseW3cTraceparent(value?: string): {
  traceId: string;
  parentSpanId: string;
  traceFlags: string;
} | null {
  if (!value) return null;
  const match = /^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/i.exec(
    value.trim(),
  );
  if (
    !match ||
    /^0+$/.test(match[1]) ||
    /^0+$/.test(match[2])
  ) {
    return null;
  }
  return {
    traceId: match[1].toLowerCase(),
    parentSpanId: match[2].toLowerCase(),
    traceFlags: match[3].toLowerCase(),
  };
}

export function eventLoopHealth(): {
  p99LagNs: number;
  drowning: boolean;
} {
  const measured = eventLoopDelay.percentile(99);
  const p99LagNs = Number.isFinite(measured) ? measured : 0;
  return {
    p99LagNs,
    drowning: p99LagNs > EVENT_LOOP_DROWNING_NS,
  };
}

function randomHex(bytes: number): string {
  return randomBytes(bytes).toString("hex");
}

export function renderMetrics(): string {
  const output: string[] = [];
  for (const [key, value] of counters) {
    output.push(`# TYPE ${key.split("{")[0]} counter`, `${key} ${value}`);
  }
  for (const [key, values] of histograms) {
    if (!values.length) continue;
    const sorted = [...values].sort((a, b) => a - b);
    for (const [quantile, position] of [
      ["0.5", 0.5],
      ["0.95", 0.95],
      ["0.99", 0.99],
    ] as const) {
      const index = Math.min(
        sorted.length - 1,
        Math.floor(sorted.length * position),
      );
      output.push(
        `${key.replace("}", `,quantile="${quantile}"}`)} ${sorted[index]}`,
      );
    }
  }
  return `${output.join("\n")}\n`;
}