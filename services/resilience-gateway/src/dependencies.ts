import { CircuitBreaker } from "./resilience/circuit-breaker.js";
import { defaultRetryable, withRetry } from "./resilience/retry.js";
import { logEvent, observe } from "./observability.js";

export interface DependencyAdapter {
  ping(): Promise<void>;
  read(path: string): Promise<unknown>;
  close(): Promise<void>;
}

export interface DependencyRead<T> {
  value: T | null;
  degraded: boolean;
  source: "origin" | "cache" | "unavailable";
  reason?: string;
}

export class ResilientDependency {
  private ready = false;
  private readonly cache = new Map<
    string,
    { value: unknown; storedAt: number }
  >();
  private readonly breaker: CircuitBreaker;

  constructor(
    readonly name: string,
    private readonly adapter: DependencyAdapter,
    private readonly cacheTtlMs = 60_000,
  ) {
    this.breaker = new CircuitBreaker({
      name,
      failureThreshold: 5,
      successThreshold: 2,
      timeout: 3_000,
      resetTimeout: 30_000,
      halfOpenMaxConcurrent: 1,
      onStateChange: (from, to) =>
        logEvent("circuit_state", { name, from, to }),
    });
  }

  async initialize(): Promise<void> {
    try {
      await this.adapter.ping();
      this.ready = true;
    } catch (error) {
      this.ready = false;
      logEvent("dependency_init_failed", {
        dependency: this.name,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  async read<T>(path: string): Promise<DependencyRead<T>> {
    return this.breaker.execute<DependencyRead<T>>(
      async () => {
        const started = Date.now();
        const value = await withRetry(() => this.adapter.read(path), {
          maxAttempts: 3,
          initialDelayMs: 250,
          maxDelayMs: 4_000,
          backoffMultiplier: 2,
          jitterFactor: 0.2,
          isRetryable: defaultRetryable,
        });
        observe(
          "dependency_duration_ms",
          `dependency="${this.name}",operation="read"`,
          Date.now() - started,
        );
        this.cache.set(path, { value, storedAt: Date.now() });
        this.ready = true;
        return {
          value: value as T,
          degraded: false,
          source: "origin" as const,
        };
      },
      async (error) => {
        this.ready = false;
        const cached = this.cache.get(path);
        if (cached && Date.now() - cached.storedAt <= this.cacheTtlMs) {
          return {
            value: cached.value as T,
            degraded: true,
            source: "cache" as const,
            reason: error.message,
          };
        }
        return {
          value: null,
          degraded: true,
          source: "unavailable" as const,
          reason: error.message,
        };
      },
    );
  }

  isReady(): boolean {
    return this.ready;
  }

  state() {
    return this.breaker.currentState;
  }

  metrics() {
    return this.breaker.metrics;
  }

  async close(): Promise<void> {
    await this.adapter.close();
    this.ready = false;
  }
}

export interface Dependencies {
  firestore: ResilientDependency;
  postgres: ResilientDependency;
  redis: ResilientDependency;
  isReady(): boolean;
  close(): Promise<void>;
}

class ExplicitlyUnconfiguredAdapter implements DependencyAdapter {
  constructor(private readonly name: string) {}
  async ping(): Promise<void> {
    throw new Error(`${this.name} adapter is not configured`);
  }
  async read(): Promise<unknown> {
    throw new Error(`${this.name} adapter is not configured`);
  }
  async close(): Promise<void> {}
}

export async function initializeDependencies(
  adapters: Partial<Record<"firestore" | "postgres" | "redis", DependencyAdapter>> = {},
): Promise<Dependencies> {
  const firestore = new ResilientDependency(
    "firestore",
    adapters.firestore ?? new ExplicitlyUnconfiguredAdapter("firestore"),
  );
  const postgres = new ResilientDependency(
    "postgres",
    adapters.postgres ?? new ExplicitlyUnconfiguredAdapter("postgres"),
  );
  const redis = new ResilientDependency(
    "redis",
    adapters.redis ?? new ExplicitlyUnconfiguredAdapter("redis"),
  );
  await Promise.all([
    firestore.initialize(),
    postgres.initialize(),
    redis.initialize(),
  ]);
  return {
    firestore,
    postgres,
    redis,
    isReady: () =>
      firestore.isReady() && postgres.isReady() && redis.isReady(),
    close: async () => {
      await Promise.allSettled([
        redis.close(),
        postgres.close(),
        firestore.close(),
      ]);
    },
  };
}