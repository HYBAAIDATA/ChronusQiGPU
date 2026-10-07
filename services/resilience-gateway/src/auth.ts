import { createHmac, timingSafeEqual } from "node:crypto";

export interface GatewayIdentity {
  subject: string;
  tenantId: string;
}

export interface GatewayTicketVerifier {
  verify(ticket: string): Promise<GatewayIdentity | null>;
}

export interface RateLimitDecision {
  allowed: boolean;
  remaining: number;
  retryAfterSeconds: number;
}

const IDENTITY_RE = /^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$/;

export class HmacGatewayTicketVerifier implements GatewayTicketVerifier {
  constructor(
    private readonly secret: string,
    private readonly maxTicketBytes = 4096,
  ) {}

  get configured(): boolean {
    return Buffer.byteLength(this.secret, "utf8") >= 32;
  }

  async verify(ticket: string): Promise<GatewayIdentity | null> {
    if (!this.configured || Buffer.byteLength(ticket, "utf8") > this.maxTicketBytes) {
      return null;
    }
    const parts = ticket.split(".");
    if (parts.length !== 2) return null;
    const [encodedPayload, encodedSignature] = parts;
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
      const now = Math.floor(Date.now() / 1000);
      if (
        typeof payload.sub !== "string" ||
        !IDENTITY_RE.test(payload.sub) ||
        typeof payload.tenantId !== "string" ||
        !IDENTITY_RE.test(payload.tenantId) ||
        typeof payload.exp !== "number" ||
        !Number.isFinite(payload.exp) ||
        payload.exp <= now ||
        (payload.nbf !== undefined &&
          (typeof payload.nbf !== "number" ||
            !Number.isFinite(payload.nbf) ||
            payload.nbf > now))
      ) {
        return null;
      }
      return { subject: payload.sub, tenantId: payload.tenantId };
    } catch {
      return null;
    }
  }
}

interface WindowBucket {
  windowStartedAt: number;
  count: number;
}

export class FixedWindowRateLimiter {
  private readonly buckets = new Map<string, WindowBucket>();

  constructor(
    readonly limit: number,
    readonly windowMs = 60_000,
    private readonly maxEntries = 10_000,
  ) {
    if (!Number.isInteger(limit) || limit < 1) {
      throw new Error("rate limit must be a positive integer");
    }
    if (!Number.isInteger(windowMs) || windowMs < 1) {
      throw new Error("rate-limit window must be a positive integer");
    }
  }

  consume(key: string, now = Date.now()): RateLimitDecision {
    let bucket = this.buckets.get(key);
    if (!bucket || now - bucket.windowStartedAt >= this.windowMs) {
      if (!bucket && this.buckets.size >= this.maxEntries) this.prune(now);
      bucket = { windowStartedAt: now, count: 0 };
      this.buckets.set(key, bucket);
    }

    const retryAfterSeconds = Math.max(
      1,
      Math.ceil((bucket.windowStartedAt + this.windowMs - now) / 1000),
    );
    if (bucket.count >= this.limit) {
      return { allowed: false, remaining: 0, retryAfterSeconds };
    }
    bucket.count += 1;
    return {
      allowed: true,
      remaining: Math.max(0, this.limit - bucket.count),
      retryAfterSeconds,
    };
  }

  private prune(now: number): void {
    for (const [key, bucket] of this.buckets) {
      if (now - bucket.windowStartedAt >= this.windowMs) {
        this.buckets.delete(key);
      }
    }
    while (this.buckets.size >= this.maxEntries) {
      const oldest = this.buckets.keys().next().value as string | undefined;
      if (oldest === undefined) break;
      this.buckets.delete(oldest);
    }
  }
}

export function bearerToken(header: string | string[] | undefined): string | null {
  if (typeof header !== "string") return null;
  const match = /^Bearer\s+(.+)$/i.exec(header.trim());
  return match?.[1]?.trim() || null;
}

export function scopeTenantPath(tenantId: string, rawPath: string): string {
  if (!IDENTITY_RE.test(tenantId)) {
    throw new Error("invalid tenant");
  }
  if (rawPath.length > 1024 || rawPath.includes("\0") || rawPath.includes("\\")) {
    throw new Error("invalid dependency path");
  }
  const segments = rawPath.split("/").filter(Boolean);
  if (segments.some((segment) => segment === "." || segment === "..")) {
    throw new Error("invalid dependency path");
  }
  const suffix = segments.length ? `/${segments.map(encodeURIComponent).join("/")}` : "/";
  return `/tenants/${encodeURIComponent(tenantId)}${suffix}`;
}
