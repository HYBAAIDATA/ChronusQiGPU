import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";

const counters = new Map<string, number>();
const histograms = new Map<string, number[]>();
const traceStorage = new AsyncLocalStorage<{
  traceId: string;
  spanId: string;
}>();

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
): Promise<T> {
  const parent = traceStorage.getStore();
  const context = {
    traceId: parent?.traceId ?? randomUUID(),
    spanId: randomUUID(),
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