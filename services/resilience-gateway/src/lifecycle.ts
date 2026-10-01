import { createServer, type Server } from "node:http";
import { WebSocketServer } from "ws";
import { initializeDependencies, type Dependencies } from "./dependencies.js";
import { initializeFeatureFlags } from "./feature-flags.js";
import { createRouter, type Readiness } from "./http.js";
import { logEvent } from "./observability.js";
import { attachWebSocket } from "./websocket.js";

export interface Runtime {
  server: Server;
  webSockets: WebSocketServer;
  dependencies: Dependencies;
  readiness: Readiness;
  shutdown(signal: string): Promise<void>;
}

export async function boot(port = Number(process.env.PORT ?? 3000)): Promise<Runtime> {
  const started = Date.now();
  initializeFeatureFlags();
  const dependencies = await initializeDependencies();
  const readiness: Readiness = {
    acceptingTraffic: false,
    shuttingDown: false,
  };
  let activeRequests = 0;
  const router = createRouter(dependencies, readiness);
  const server = createServer((request, response) => {
    activeRequests++;
    response.once("finish", () => activeRequests--);
    response.once("close", () => {
      if (!response.writableFinished) activeRequests--;
    });
    void router(request, response);
  });
  const webSockets = new WebSocketServer({ server, path: "/ws" });
  attachWebSocket(webSockets, dependencies);
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "0.0.0.0", () => {
      server.off("error", reject);
      resolve();
    });
  });
  readiness.acceptingTraffic = true;
  logEvent("boot_complete", { port, durationMs: Date.now() - started });

  let shutdownPromise: Promise<void> | undefined;
  const shutdown = (signal: string): Promise<void> => {
    shutdownPromise ??= performShutdown(
      signal,
      server,
      webSockets,
      dependencies,
      readiness,
      () => activeRequests,
    );
    return shutdownPromise;
  };
  return { server, webSockets, dependencies, readiness, shutdown };
}

async function performShutdown(
  signal: string,
  server: Server,
  webSockets: WebSocketServer,
  dependencies: Dependencies,
  readiness: Readiness,
  activeRequests: () => number,
): Promise<void> {
  const started = Date.now();
  readiness.shuttingDown = true;
  readiness.acceptingTraffic = false;
  logEvent("shutdown_start", { signal });
  await new Promise<void>((resolve) => server.close(() => resolve()));
  for (const client of webSockets.clients) {
    client.close(1001, "server shutting down");
  }
  const deadline = Date.now() + 30_000;
  while (activeRequests() > 0 && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  for (const client of webSockets.clients) client.terminate();
  await dependencies.close();
  webSockets.close();
  logEvent("shutdown_complete", {
    durationMs: Date.now() - started,
    forcedRequests: activeRequests(),
  });
}

export function registerProcessSignals(runtime: Runtime): void {
  for (const signal of ["SIGTERM", "SIGINT"] as const) {
    process.once(signal, () => {
      void runtime.shutdown(signal).then(() => {
        process.exitCode = 0;
      });
    });
  }
  process.once("uncaughtException", (error) => {
    logEvent("uncaught_exception", { error: error.message, stack: error.stack });
    void runtime.shutdown("uncaughtException").finally(() => {
      process.exitCode = 1;
    });
  });
  process.once("unhandledRejection", (reason) => {
    logEvent("unhandled_rejection", { reason: String(reason) });
    void runtime.shutdown("unhandledRejection").finally(() => {
      process.exitCode = 1;
    });
  });
}