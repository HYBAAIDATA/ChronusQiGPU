import { timingSafeEqual } from "node:crypto";
import type { IncomingMessage } from "node:http";

export interface StrategicAssetPolicy {
  assetHashes: ReadonlySet<string>;
  allowedCidrs: readonly string[];
  clearanceTokenHash: string;
}

/**
 * This server-side gate supplements, but never replaces, separate strategic
 * and standard frontend builds. Strategic chunks must not appear in the
 * standard artifact manifest.
 */
export function authorizeStrategicAsset(
  request: IncomingMessage,
  assetHash: string,
  policy: StrategicAssetPolicy,
): boolean {
  if (!policy.assetHashes.has(assetHash)) return false;
  const address = request.socket.remoteAddress ?? "";
  if (!policy.allowedCidrs.some((prefix) => address.startsWith(prefix))) {
    return false;
  }
  const provided = request.headers["x-strategic-clearance"];
  if (typeof provided !== "string") return false;
  const left = Buffer.from(provided, "hex");
  const right = Buffer.from(policy.clearanceTokenHash, "hex");
  return left.length === right.length && timingSafeEqual(left, right);
}

export function assertArtifactSegregation(
  standardAssets: readonly string[],
  strategicAssets: readonly string[],
): void {
  const standard = new Set(standardAssets);
  const overlap = strategicAssets.filter((asset) => standard.has(asset));
  if (overlap.length) {
    throw new Error(`strategic assets leaked into standard build: ${overlap.join(", ")}`);
  }
}