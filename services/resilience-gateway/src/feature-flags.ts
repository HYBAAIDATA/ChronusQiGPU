import { createHash } from "node:crypto";

interface Flag {
  enabled: boolean;
  rolloutPercent: number;
  updatedAt: number;
}

const flags = new Map<string, Flag>();

export function initializeFeatureFlags(): void {
  setFlag("new_ws_protocol", true, 100);
  setFlag("dependency_breakers", true, 100);
  setFlag("sync_queue", false, 0);
}

export function setFlag(
  name: string,
  enabled: boolean,
  rolloutPercent: number,
): void {
  if (rolloutPercent < 0 || rolloutPercent > 100) {
    throw new Error("rolloutPercent must be between 0 and 100");
  }
  flags.set(name, { enabled, rolloutPercent, updatedAt: Date.now() });
}

export function isEnabled(name: string, subjectId?: string): boolean {
  const flag = flags.get(name);
  if (!flag?.enabled) return false;
  if (flag.rolloutPercent === 100) return true;
  if (!subjectId) return false;
  const bucket =
    createHash("sha256").update(subjectId).digest().readUInt32BE(0) % 100;
  return bucket < flag.rolloutPercent;
}