export interface ResilientWebSocketOptions {
  url: string;
  ticket: () => Promise<string>;
  onMessage: (message: unknown) => void;
  onStateChange?: (
    state: "connecting" | "open" | "reconnecting" | "closed",
  ) => void;
  maxReconnectAttempts?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  backoffMultiplier?: number;
  jitterFactor?: number;
}

export class ResilientWebSocketClient {
  private socket?: WebSocket;
  private attempts = 0;
  private intentionalClose = false;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private readonly options: Required<ResilientWebSocketOptions>;

  constructor(options: ResilientWebSocketOptions) {
    this.options = {
      maxReconnectAttempts: 10,
      initialBackoffMs: 1_000,
      maxBackoffMs: 30_000,
      backoffMultiplier: 1.5,
      jitterFactor: 0.3,
      onStateChange: () => {},
      ...options,
    };
  }

  connect(): void {
    this.intentionalClose = false;
    this.options.onStateChange(
      this.attempts === 0 ? "connecting" : "reconnecting",
    );
    const socket = new WebSocket(this.options.url);
    this.socket = socket;
    socket.onopen = () => {
      void this.options
        .ticket()
        .then((token) => {
          socket.send(JSON.stringify({ type: "auth", token }));
        })
        .catch(() => socket.close(4001, "ticket unavailable"));
    };
    socket.onmessage = ({ data }) => {
      try {
        const message = JSON.parse(String(data)) as Record<string, unknown>;
        if (message.type === "authenticated") {
          this.attempts = 0;
          this.options.onStateChange("open");
        } else if (message.type === "ping") {
          this.send({ type: "pong", timestamp: message.timestamp });
        } else {
          this.options.onMessage(message);
        }
      } catch {
        // Malformed server messages are ignored rather than crashing the UI.
      }
    };
    socket.onclose = ({ code }) => {
      if (this.intentionalClose || code === 1000 || code === 1001) {
        this.options.onStateChange("closed");
      } else {
        this.scheduleReconnect();
      }
    };
  }

  send(value: unknown): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(value));
    return true;
  }

  close(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close(1000, "client shutdown");
  }

  private scheduleReconnect(): void {
    if (this.attempts >= this.options.maxReconnectAttempts) {
      this.options.onStateChange("closed");
      return;
    }
    const base = Math.min(
      this.options.initialBackoffMs *
        this.options.backoffMultiplier ** this.attempts,
      this.options.maxBackoffMs,
    );
    this.attempts++;
    const spread = base * this.options.jitterFactor;
    const delay = Math.round(base - spread + Math.random() * spread * 2);
    this.options.onStateChange("reconnecting");
    this.reconnectTimer = setTimeout(() => this.connect(), Math.max(0, delay));
  }
}