import { randomUUID } from "node:crypto";
import type { IncomingMessage } from "node:http";
import type { RawData, WebSocket, WebSocketServer } from "ws";
import type { Dependencies } from "./dependencies.js";
import { increment, logEvent } from "./observability.js";

interface SessionState {
  id: string;
  lastPong: number;
  missedPongs: number;
  inFlight: number;
}

export class WebSocketSession {
  private readonly state: SessionState = {
    id: randomUUID(),
    lastPong: Date.now(),
    missedPongs: 0,
    inFlight: 0,
  };
  private heartbeat?: NodeJS.Timeout;
  private closed = false;

  constructor(
    private readonly socket: WebSocket,
    private readonly dependencies: Dependencies,
  ) {}

  start(): void {
    this.socket.on("message", (raw) => void this.onMessage(raw));
    this.socket.on("pong", () => {
      this.state.lastPong = Date.now();
      this.state.missedPongs = 0;
    });
    this.socket.once("close", () => this.close());
    this.socket.once("error", () => this.close());
    this.heartbeat = setInterval(() => this.pulse(), 25_000);
  }

  private async onMessage(raw: RawData): Promise<void> {
    if (this.state.inFlight >= 5) {
      increment("ws_backpressure_total");
      this.send({ type: "error", code: "backpressure", retryable: true });
      return;
    }
    this.state.inFlight++;
    try {
      let message: Record<string, unknown>;
      try {
        message = JSON.parse(raw.toString()) as Record<string, unknown>;
      } catch {
        this.send({ type: "error", code: "invalid_json", retryable: false });
        return;
      }
      if (message.type === "pong") {
        this.state.lastPong = Date.now();
        this.state.missedPongs = 0;
      } else if (message.type === "ping") {
        this.send({ type: "pong", timestamp: message.timestamp });
      } else if (message.type === "read") {
        const result = await this.dependencies.firestore.read(
          String(message.path ?? "/"),
        );
        this.send({ type: "result", id: message.id, ...result });
      } else {
        this.send({ type: "error", code: "unknown_type", retryable: false });
      }
    } finally {
      this.state.inFlight--;
    }
  }

  private pulse(): void {
    if (this.socket.readyState !== this.socket.OPEN) return;
    if (Date.now() - this.state.lastPong > 35_000) {
      this.state.missedPongs++;
      if (this.state.missedPongs >= 3) {
        logEvent("ws_stale", { sessionId: this.state.id });
        this.socket.terminate();
        return;
      }
    }
    this.socket.ping();
    this.send({ type: "ping", timestamp: Date.now() });
  }

  private send(message: unknown): void {
    if (this.socket.readyState === this.socket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  private close(): void {
    if (this.closed) return;
    this.closed = true;
    if (this.heartbeat) clearInterval(this.heartbeat);
  }
}

export function attachWebSocket(
  server: WebSocketServer,
  dependencies: Dependencies,
): void {
  server.on(
    "connection",
    (socket: WebSocket, _request: IncomingMessage) =>
      new WebSocketSession(socket, dependencies).start(),
  );
}