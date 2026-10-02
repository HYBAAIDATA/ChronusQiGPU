import type { IncomingMessage, ServerResponse } from "node:http";
import type { Dependencies } from "./dependencies.js";
import {
  currentTraceparent,
  eventLoopHealth,
  increment,
  observe,
  renderMetrics,
  withTrace,
} from "./observability.js";

export interface Readiness {
  acceptingTraffic: boolean;
  shuttingDown: boolean;
}

export interface CachedResponse {
  status: number;
  body: string;
  expiresAt: number;
}

export interface IdempotencyStore {
  begin(
    key: string,
    pendingTtlMs: number,
  ): Promise<
    | { state: "owner" }
    | { state: "pending" }
    | { state: "done"; response: CachedResponse }
  >;
  complete(key: string, response: CachedResponse): Promise<void>;
  abandon(key: string): Promise<void>;
}

export class MemoryIdempotencyStore implements IdempotencyStore {
  private readonly values = new Map<
    string,
    | { state: "pending"; expiresAt: number }
    | { state: "done"; response: CachedResponse }
  >();
  async begin(
    key: string,
    pendingTtlMs: number,
  ): Promise<
    | { state: "owner" }
    | { state: "pending" }
    | { state: "done"; response: CachedResponse }
  > {
    const value = this.values.get(key);
    const expiresAt =
      value?.state === "pending" ? value.expiresAt : value?.response.expiresAt;
    if (value && expiresAt && expiresAt > Date.now()) {
      return value.state === "pending"
        ? { state: "pending" }
        : { state: "done", response: value.response };
    }
    if (value) {
      this.values.delete(key);
    }
    this.values.set(key, {
      state: "pending",
      expiresAt: Date.now() + pendingTtlMs,
    });
    return { state: "owner" };
  }
  async complete(key: string, response: CachedResponse): Promise<void> {
    this.values.set(key, { state: "done", response });
  }
  async abandon(key: string): Promise<void> {
    const value = this.values.get(key);
    if (value?.state === "pending") this.values.delete(key);
  }
}

export type IdempotentResult =
  | { state: "executed"; response: CachedResponse }
  | { state: "replayed"; response: CachedResponse }
  | { state: "pending" };

export async function executeIdempotently(
  store: IdempotencyStore,
  key: string,
  operation: () => Promise<Omit<CachedResponse, "expiresAt">>,
  options: { pendingTtlMs?: number; resultTtlMs?: number } = {},
): Promise<IdempotentResult> {
  const pendingTtlMs = options.pendingTtlMs ?? 30_000;
  const resultTtlMs = options.resultTtlMs ?? 86_400_000;
  const claim = await store.begin(key, pendingTtlMs);
  if (claim.state === "pending") return { state: "pending" };
  if (claim.state === "done") {
    return { state: "replayed", response: claim.response };
  }
  try {
    const result = await operation();
    const response = { ...result, expiresAt: Date.now() + resultTtlMs };
    await store.complete(key, response);
    return { state: "executed", response };
  } catch (error) {
    await store.abandon(key);
    throw error;
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
        {
          const traceparent = currentTraceparent();
          if (traceparent) response.setHeader("traceparent", traceparent);
          return withTimeout(
            dispatch(
              request,
              response,
              route,
              dependencies,
              readiness,
              idempotency,
            ),
            10_000,
          );
        },
        typeof request.headers.traceparent === "string"
          ? request.headers.traceparent
          : undefined,
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
    const loop = eventLoopHealth();
    sendJson(response, loop.drowning ? 503 : 200, {
      status: loop.drowning ? "drowning" : "alive",
      uptime: process.uptime(),
      eventLoopP99LagMs: loop.p99LagNs / 1_000_000,
    });
    return;
  }
  if (route === "GET /readyz") {
    const loop = eventLoopHealth();
    const ready =
      readiness.acceptingTraffic &&
      !readiness.shuttingDown &&
      dependencies.isReady() &&
      !loop.drowning;
    sendJson(response, ready ? 200 : 503, {
      status: ready ? "ready" : "not_ready",
      eventLoopP99LagMs: loop.p99LagNs / 1_000_000,
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
      const claim = await idempotency.begin(key, 30_000);
      if (claim.state === "pending") {
        sendJson(response, 425, {
          error: {
            code: "idempotency_pending",
            message: "An identical request is still being processed",
          },
        });
        return;
      }
      if (claim.state === "done") {
        response.writeHead(claim.response.status, {
          "content-type": "application/json",
          "x-idempotent-replay": "1",
        });
        response.end(claim.response.body);
        return;
      }
      await idempotency.abandon(key);
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