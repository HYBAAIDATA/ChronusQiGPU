import type { IncomingMessage, ServerResponse } from "node:http";
import type { Dependencies } from "./dependencies.js";
import { increment, observe, renderMetrics, withTrace } from "./observability.js";

export interface Readiness {
  acceptingTraffic: boolean;
  shuttingDown: boolean;
}

interface CachedResponse {
  status: number;
  body: string;
  expiresAt: number;
}

export interface IdempotencyStore {
  get(key: string): Promise<CachedResponse | null>;
  set(key: string, response: CachedResponse): Promise<void>;
}

export class MemoryIdempotencyStore implements IdempotencyStore {
  private readonly values = new Map<string, CachedResponse>();
  async get(key: string): Promise<CachedResponse | null> {
    const value = this.values.get(key);
    if (!value || value.expiresAt <= Date.now()) {
      this.values.delete(key);
      return null;
    }
    return value;
  }
  async set(key: string, response: CachedResponse): Promise<void> {
    this.values.set(key, response);
  }
}

export function createRouter(
  dependencies: Dependencies,
  readiness: Readiness,
  idempotency: IdempotencyStore = new MemoryIdempotencyStore(),
) {
  return async (request: IncomingMessage, response: ServerResponse) => {
    const started = Date.now();
    const route = `${request.method ?? "GET"} ${(request.url ?? "/").split("?")[0]}`;
    increment("http_requests_total", `route="${route}"`);
    try {
      await withTrace(route, () =>
        withTimeout(
          dispatch(request, response, route, dependencies, readiness, idempotency),
          10_000,
        ),
      );
    } catch (error) {
      increment("http_errors_total", `route="${route}"`);
      if (!response.headersSent) {
        sendJson(response, 500, {
          error: {
            code: "internal",
            message: error instanceof Error ? error.message : String(error),
          },
        });
      }
    } finally {
      observe(
        "http_duration_ms",
        `route="${route}",status="${response.statusCode}"`,
        Date.now() - started,
      );
    }
  };
}

async function dispatch(
  request: IncomingMessage,
  response: ServerResponse,
  route: string,
  dependencies: Dependencies,
  readiness: Readiness,
  idempotency: IdempotencyStore,
): Promise<void> {
  if (route === "GET /healthz") {
    sendJson(response, 200, { status: "alive", uptime: process.uptime() });
    return;
  }
  if (route === "GET /readyz") {
    const ready =
      readiness.acceptingTraffic &&
      !readiness.shuttingDown &&
      dependencies.isReady();
    sendJson(response, ready ? 200 : 503, {
      status: ready ? "ready" : "not_ready",
    });
    return;
  }
  if (route === "GET /metrics") {
    response.writeHead(200, { "content-type": "text/plain; version=0.0.4" });
    response.end(renderMetrics());
    return;
  }
  if (route === "GET /api/v1/dependencies/firestore") {
    const url = new URL(request.url ?? "/", "http://localhost");
    const result = await dependencies.firestore.read(url.searchParams.get("path") ?? "/");
    sendJson(response, result.degraded ? 206 : 200, result);
    return;
  }
  if (request.method && !["GET", "HEAD", "OPTIONS"].includes(request.method)) {
    const key = request.headers["idempotency-key"];
    if (typeof key === "string") {
      const replay = await idempotency.get(key);
      if (replay) {
        response.writeHead(replay.status, {
          "content-type": "application/json",
          "x-idempotent-replay": "1",
        });
        response.end(replay.body);
        return;
      }
    }
  }
  sendJson(response, 404, {
    error: { code: "not_found", message: "Route not found" },
  });
}

export function sendJson(
  response: ServerResponse,
  status: number,
  value: unknown,
): void {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(value));
}

export async function withTimeout<T>(
  operation: Promise<T>,
  timeoutMs: number,
): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  try {
    return await Promise.race([
      operation,
      new Promise<T>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`timeout after ${timeoutMs}ms`)),
          timeoutMs,
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}