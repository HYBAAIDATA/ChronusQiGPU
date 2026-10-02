export interface RetryOptions {
  maxAttempts: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  jitterFactor: number;
  isRetryable: (error: Error) => boolean;
  sleep?: (ms: number) => Promise<void>;
  random?: () => number;
}

export async function withRetry<T>(
  operation: (attempt: number) => Promise<T>,
  options: RetryOptions,
): Promise<T> {
  if (options.maxAttempts < 1) throw new Error("maxAttempts must be >= 1");
  const sleep =
    options.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  const random = options.random ?? Math.random;
  let lastError = new Error("retry failed");

  for (let attempt = 1; attempt <= options.maxAttempts; attempt++) {
    try {
      return await operation(attempt);
    } catch (cause) {
      lastError = cause instanceof Error ? cause : new Error(String(cause));
      if (
        attempt === options.maxAttempts ||
        !options.isRetryable(lastError)
      ) {
        throw lastError;
      }
      const base = Math.min(
        options.initialDelayMs *
          options.backoffMultiplier ** (attempt - 1),
        options.maxDelayMs,
      );
      const jitter = base * options.jitterFactor * random();
      await sleep(Math.round(base + jitter));
    }
  }
  throw lastError;
}

export function defaultRetryable(error: Error): boolean {
  const message = error.message.toLowerCase();
  return [
    "timeout",
    "econnreset",
    "econnrefused",
    "etimedout",
    "429",
    "502",
    "503",
    "504",
  ].some((marker) => message.includes(marker));
}