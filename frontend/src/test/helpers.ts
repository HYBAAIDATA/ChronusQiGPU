/** Offline, dependency-free factories shared by frontend unit tests. */

export interface MockUser {
  id: string;
  email: string;
  displayName: string;
  roles: string[];
  emailVerified: boolean;
}

export function createMockUser(overrides: Partial<MockUser> = {}): MockUser {
  return {
    id: "user-test-001",
    email: "operator@example.invalid",
    displayName: "Test Operator",
    roles: ["operator"],
    emailVerified: true,
    ...overrides,
  };
}

export interface TestDB {
  get<T>(key: string, fallback?: T): T | undefined;
  set<T>(key: string, value: T): void;
  has(key: string): boolean;
  delete(key: string): boolean;
  clear(): void;
  reset(): void;
  entries(): Array<[string, unknown]>;
}

/** A deterministic in-memory substitute for persistence; never touches Firebase. */
export function setupTestDB(initial: Record<string, unknown> = {}): TestDB {
  const seed = new Map(Object.entries(initial));
  const data = new Map(seed);
  return {
    get<T>(key: string, fallback?: T): T | undefined {
      return (data.has(key) ? data.get(key) : fallback) as T | undefined;
    },
    set<T>(key: string, value: T): void {
      data.set(key, value);
    },
    has: (key) => data.has(key),
    delete: (key) => data.delete(key),
    clear: () => data.clear(),
    reset: () => {
      data.clear();
      for (const [key, value] of seed) data.set(key, value);
    },
    entries: () => Array.from(data.entries()),
  };
}

export function createMockResponse<T>(body: T, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  if (!headers.has("content-type")) headers.set("content-type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}
