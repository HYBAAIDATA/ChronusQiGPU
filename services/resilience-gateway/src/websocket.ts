import {
  createHmac,
  randomUUID,
  timingSafeEqual,
} from "node:crypto";
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

export interface WebSocketIdentity {
  subject: string;
  tenantId: string;
}

export interface WebSocketTicketVerifier {
  verify(ticket: string): Promise<WebSocketIdentity | null>;
}

export class HmacWebSocketTicketVerifier implements WebSocketTicketVerifier {
  constructor(private readonly secret: string) {}

  async verify(ticket: string): Promise<WebSocketIdentity | null> {
    if (!this.secret) return null;
    const [encodedPayload, encodedSignature] = ticket.split(".");
    if (!encodedPayload || !encodedSignature) return null;
    const expected = createHmac("sha256", this.secret)
      .update(encodedPayload)
      .digest();
    let provided: Buffer;
    try {
      provided = Buffer.from(encodedSignature, "base64url");
    } catch {
      return null;
    }
    if (
      expected.length !== provided.length ||
      !timingSafeEqual(expected, provided)
    ) {
      return null;
    }
    try {
      const payload = JSON.parse(
        Buffer.from(encodedPayload, "base64url").toString("utf8"),
      ) as Record<string, unknown>;
      if (
        typeof payload.sub !== "string" ||
        typeof payload.tenantId !== "string" ||
        typeof payload.exp !== "number" ||
        payload.exp * 1000 <= Date.now()
      ) {
        return null;
      }
      return { subject: payload.sub, tenantId: payload.tenantId };
    } catch {
      return null;
    }
  }
}

export class WebSocketSession {
  private readonly state: SessionState = {
    id: randomUUID(),
    lastPong: Date.now(),
    missedPongs: 0,
    inFlight: 0,
  };
  private heartbeat?: NodeJS.Timeout;
  private authDeadline?: NodeJS.Timeout;
  private closed = false;
  private identity?: WebSocketIdentity;

  constructor(
    private readonly socket: WebSocket,
    private readonly dependencies: Dependencies,
    private readonly ticketVerifier: WebSocketTicketVerifier,
  ) {}

  start(): void {
    this.socket.on("message", (raw) => void this.onMessage(raw));
    this.socket.on("pong", () => {
      this.state.lastPong = Date.now();
      this.state.missedPongs = 0;
    });
    this.socket.once("close", () => this.close());
    this.socket.once("error", () => this.close());
    this.authDeadline = setTimeout(() => {
      if (!this.identity) this.socket.close(4001, "unauthorized");
    }, 5_000);
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
      if (!this.identity) {
        if (message.type !== "auth" || typeof message.token !== "string") {
          this.socket.close(4001, "unauthorized");
          return;
        }
        const identity = await this.ticketVerifier.verify(message.token);
        if (!identity) {
          this.socket.close(4001, "unauthorized");
          return;
        }
        this.identity = identity;
        if (this.authDeadline) clearTimeout(this.authDeadline);
        this.heartbeat = setInterval(() => this.pulse(), 25_000);
        this.send({ type: "authenticated", tenantId: identity.tenantId });
        return;
      }
      if (message.type === "auth") {
        this.send({ type: "error", code: "already_authenticated", retryable: false });
      } else if (message.type === "pong") {
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
    if (this.authDeadline) clearTimeout(this.authDeadline);
    if (this.heartbeat) clearInterval(this.heartbeat);
  }
}

export function attachWebSocket(
  server: WebSocketServer,
  dependencies: Dependencies,
  ticketVerifier: WebSocketTicketVerifier,
): void {
  server.on(
    "connection",
    (socket: WebSocket, _request: IncomingMessage) =>
      new WebSocketSession(socket, dependencies, ticketVerifier).start(),
  );
}