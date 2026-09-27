/**
 * Minimal structured logger — emits one JSON object per line on stdout so
 * container log drivers (json-file, fluentd, Loki, Datadog) can ingest events
 * without parsing. Zero dependencies by design.
 */

export type LogLevel = "info" | "warn" | "error";

const LEVEL_PRIORITY: Record<LogLevel, number> = { info: 20, warn: 30, error: 40 };
const configuredLevel = (process.env.LOG_LEVEL || "info").toLowerCase() as LogLevel;
const minPriority = LEVEL_PRIORITY[configuredLevel] ?? LEVEL_PRIORITY.info;

function emit(level: LogLevel, msg: string, fields?: Record<string, unknown>): void {
  if (LEVEL_PRIORITY[level] < minPriority) return;
  const line = JSON.stringify({
    ts: new Date().toISOString(),
    level,
    msg,
    ...(fields || {}),
  });
  if (level === "error") {
    console.error(line);
  } else if (level === "warn") {
    console.warn(line);
  } else {
    console.log(line);
  }
}

export const logger = {
  info: (msg: string, fields?: Record<string, unknown>) => emit("info", msg, fields),
  warn: (msg: string, fields?: Record<string, unknown>) => emit("warn", msg, fields),
  error: (msg: string, fields?: Record<string, unknown>) => emit("error", msg, fields),
};
