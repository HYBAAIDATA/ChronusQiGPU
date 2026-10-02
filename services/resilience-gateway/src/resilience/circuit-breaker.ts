export type CircuitState = "CLOSED" | "OPEN" | "HALF_OPEN";

export interface CircuitBreakerOptions {
  name: string;
  failureThreshold: number;
  successThreshold: number;
  timeout: number;
  resetTimeout: number;
  halfOpenMaxConcurrent: number;
  onStateChange?: (from: CircuitState, to: CircuitState, name: string) => void;
  now?: () => number;
}

export interface CircuitMetrics {
  calls: number;
  successes: number;
  failures: number;
  timeouts: number;
  shortCircuits: number;
  halfOpenProbes: number;
  halfOpenRejections: number;
}

export class CircuitOpenError extends Error {
  constructor(public readonly circuit: string) {
    super(`circuit ${circuit} is open`);
    this.name = "CircuitOpenError";
  }
}

export class CircuitBreaker {
  private state: CircuitState = "CLOSED";
  private consecutiveFailures = 0;
  private halfOpenSuccesses = 0;
  private halfOpenInFlight = 0;
  private openedAt = 0;
  private readonly now: () => number;

  readonly metrics: CircuitMetrics = {
    calls: 0,
    successes: 0,
    failures: 0,
    timeouts: 0,
    shortCircuits: 0,
    halfOpenProbes: 0,
    halfOpenRejections: 0,
  };

  constructor(private readonly options: CircuitBreakerOptions) {
    for (const [name, value] of Object.entries({
      failureThreshold: options.failureThreshold,
      successThreshold: options.successThreshold,
      timeout: options.timeout,
      resetTimeout: options.resetTimeout,
      halfOpenMaxConcurrent: options.halfOpenMaxConcurrent,
    })) {
      if (!Number.isFinite(value) || value <= 0) {
        throw new Error(`${name} must be greater than zero`);
      }
    }
    this.now = options.now ?? Date.now;
  }

  get currentState(): CircuitState {
    this.advanceIfResetElapsed();
    return this.state;
  }

  async execute<T>(
    operation: () => Promise<T>,
    fallback: (error: Error) => Promise<T>,
  ): Promise<T> {
    this.metrics.calls++;
    this.advanceIfResetElapsed();

    if (this.state === "OPEN") {
      this.metrics.shortCircuits++;
      return fallback(new CircuitOpenError(this.options.name));
    }

    const isProbe = this.state === "HALF_OPEN";
    if (
      isProbe &&
      this.halfOpenInFlight >= this.options.halfOpenMaxConcurrent
    ) {
      this.metrics.halfOpenRejections++;
      return fallback(new CircuitOpenError(this.options.name));
    }

    if (isProbe) {
      this.halfOpenInFlight++;
      this.metrics.halfOpenProbes++;
    }

    try {
      const value = await this.withTimeout(operation());
      this.onSuccess();
      return value;
    } catch (cause) {
      const error = cause instanceof Error ? cause : new Error(String(cause));
      this.onFailure();
      return fallback(error);
    } finally {
      if (isProbe) this.halfOpenInFlight--;
    }
  }

  private async withTimeout<T>(promise: Promise<T>): Promise<T> {
    let timer: NodeJS.Timeout | undefined;
    try {
      return await Promise.race([
        promise,
        new Promise<T>((_, reject) => {
          timer = setTimeout(() => {
            this.metrics.timeouts++;
            reject(new Error(`timeout after ${this.options.timeout}ms`));
          }, this.options.timeout);
        }),
      ]);
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  private advanceIfResetElapsed(): void {
    if (
      this.state === "OPEN" &&
      this.now() - this.openedAt >= this.options.resetTimeout
    ) {
      this.transition("HALF_OPEN");
      this.halfOpenSuccesses = 0;
    }
  }

  private onSuccess(): void {
    this.metrics.successes++;
    if (this.state === "HALF_OPEN") {
      this.halfOpenSuccesses++;
      if (this.halfOpenSuccesses >= this.options.successThreshold) {
        this.consecutiveFailures = 0;
        this.transition("CLOSED");
      }
      return;
    }
    this.consecutiveFailures = 0;
  }

  private onFailure(): void {
    this.metrics.failures++;
    if (this.state === "HALF_OPEN") {
      this.open();
      return;
    }
    this.consecutiveFailures++;
    if (this.consecutiveFailures >= this.options.failureThreshold) this.open();
  }

  private open(): void {
    this.openedAt = this.now();
    this.halfOpenSuccesses = 0;
    this.transition("OPEN");
  }

  private transition(next: CircuitState): void {
    if (this.state === next) return;
    const previous = this.state;
    this.state = next;
    this.options.onStateChange?.(previous, next, this.options.name);
  }
}