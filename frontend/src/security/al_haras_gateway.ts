/**
 * AL HARAS TOPOLOGICAL GATEWAY & HODGE-BRIDGE RESONANCE LAYER
 * ===============================================================
 * Secondary structural-resonance check over Q[√5] for sovereign demo routes.
 * NOTE: This is NOT an authentication mechanism — Fibonacci/Lucas values are
 * public. Real authorization is enforced by the admin API key middleware.
 *
 * Mandate 1: Client Hodge Bridge Polynomial Generator & Header Encoding
 * Mandate 2: Server-side Yang-Mills Mass Gap Vacuum Filter (Silent drop on Δ ≤ 0 or Cassini drift)
 * Mandate 3: Geometric Materialization & Sovereign Routing to HYBA Cortex / Compass
 */

import { Request, Response, NextFunction } from "express";
import { getFibonacci, getLucas } from "../lib/q5_golden_silicon";

export interface AlHarasGateway {
  intercept: (req: Request, res: Response, next: NextFunction) => void;
  applyYangMillsFilter: (lucasScalar: bigint, powerOrder: number) => boolean;
}

export interface HodgeResonanceHeaders {
  "x-alharas-zeckendorf": string; // e.g. "F_13+F_8+F_3" or comma-separated indices "13,8,3"
  "x-alharas-lucas-scalar": string; // exact rational integer string e.g. "521"
  "x-alharas-power-order": string; // power order n for Q-matrix witness
  "x-alharas-manifold-dim"?: string; // 11 by default
}

export interface GeometricMaterializationResult {
  // Structural resonance only — NOT authentication; see the file header.
  resonance_valid: boolean;
  manifoldDimension: number;
  spectralGapNum: bigint;
  spectralGapDen: bigint;
  cassiniDeterminant: bigint;
  resonantNodeId: string;
  targetSubnet: "HYBA_CORTEX" | "HYBA_COMPASS" | "SOVEREIGN_RESERVE";
  materializedTimestamp: number;
}

/**
 * Exact Rational ALU for Topological Handshake
 */
export class AlHarasTopologicalVerifier implements AlHarasGateway {
  intercept(req: Request, res: Response, next: NextFunction): void {
    alHarasTopologicalGatewayMiddleware(req, res, next);
  }

  applyYangMillsFilter(lucasScalar: bigint, n: number): boolean {
    return AlHarasTopologicalVerifier.verifyYangMillsMassGap(lucasScalar, n).gapPositive;
  }

  /**
   * Verifies Zeckendorf canonical non-consecutive rule: |k_i - k_j| >= 2
   */
  static verifyZeckendorfIndices(indices: number[]): boolean {
    if (!indices || indices.length === 0) return false;
    const sorted = [...indices].sort((a, b) => a - b);
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sorted[i + 1] - sorted[i] < 2) {
        return false; // Consecutive Fibonacci indices violation
      }
    }
    return true;
  }

  /**
   * Evaluates exact Cassini invariant det(M^n) = (-1)^n
   */
  static verifyCassiniInvariant(n: number, reportedDet: bigint): boolean {
    if (n < 1) return false;
    const fn1 = getFibonacci(n + 1);
    const fnMinus = getFibonacci(n - 1);
    const fn = getFibonacci(n);
    const calculatedDet = fn1 * fnMinus - fn * fn;
    const expectedDet = n % 2 === 1 ? -1n : 1n;
    return calculatedDet === expectedDet && reportedDet === expectedDet;
  }

  /**
   * Evaluates exact Yang-Mills Spectral Mass Gap Delta = lambda_1 - lambda_0 > 0
   * Using exact rational companion spectrum
   */
  static verifyYangMillsMassGap(
    lucasScalar: bigint,
    n: number,
  ): { gapPositive: boolean; gapNum: bigint; gapDen: bigint } {
    // Ground state eigenvalue from base companion cycle: lambda_0 = L_n / 2
    // Excited state eigenvalue: lambda_1 = L_{n+1} / 2
    const lN = getLucas(n);
    const lN1 = getLucas(n + 1);

    // Cross-product spectral gap calculation
    const gapNum = lN1 - lN;
    const gapDen = 2n;

    const gapPositive = gapNum > 0n && lucasScalar === lN;
    return { gapPositive, gapNum, gapDen };
  }
}

/**
 * Client-side Hodge Bridge Access Polynomial Builder
 */
export function generateClientHodgeResonanceHeaders(n: number = 13): Record<string, string> {
  const fibIndices = [13, 8, 3]; // canonical non-consecutive
  const lucasVal = getLucas(n).toString();
  const detVal = (n % 2 === 1 ? -1 : 1).toString();

  return {
    "x-alharas-zeckendorf": fibIndices.join(","),
    "x-alharas-lucas-scalar": lucasVal,
    "x-alharas-power-order": n.toString(),
    "x-alharas-cassini-det": detVal,
    "x-alharas-manifold-dim": "11",
  };
}

/**
 * Express Middleware: AL HARAS Topological Gateway
 * Intercepts incoming network requests. If structural resonance fails, the request
 * is dropped silently at the socket layer (zero response / socket destroy).
 */
export function alHarasTopologicalGatewayMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  // Check if route is protected under sovereign enterprise layer (/api/sovereign/*, /api/hyba/*)
  const isProtectedPath =
    req.path.startsWith("/api/sovereign") ||
    req.path.startsWith("/api/hyba") ||
    req.path.startsWith("/api/alharas");

  if (!isProtectedPath) {
    return next();
  }

  const zeckHeader = req.headers["x-alharas-zeckendorf"] as string;
  const lucasHeader = req.headers["x-alharas-lucas-scalar"] as string;
  const orderHeader = req.headers["x-alharas-power-order"] as string;
  const detHeader = req.headers["x-alharas-cassini-det"] as string;

  // Rejection path: return a standard 401 without leaking which check failed.
  const silentDropIntoVacuum = () => {
    if (!res.headersSent) {
      res.status(401).json({ success: false, error: "Resonance validation failed" });
    }
  };

  if (!zeckHeader || !lucasHeader || !orderHeader || !detHeader) {
    // Missing resonance credentials -> Vacuum drop
    return silentDropIntoVacuum();
  }

  try {
    const indices = zeckHeader.split(",").map((s) => parseInt(s.trim(), 10));
    const powerOrder = parseInt(orderHeader.trim(), 10);
    const lucasScalar = BigInt(lucasHeader.trim());
    const reportedDet = BigInt(detHeader.trim());

    // 1. Check Zeckendorf non-consecutive canon
    if (!AlHarasTopologicalVerifier.verifyZeckendorfIndices(indices)) {
      return silentDropIntoVacuum();
    }

    // 2. Check Cassini invariant det(M^n) = (-1)^n
    if (!AlHarasTopologicalVerifier.verifyCassiniInvariant(powerOrder, reportedDet)) {
      return silentDropIntoVacuum();
    }

    // 3. Check Yang-Mills Mass Gap Vacuum Filter (Delta > 0)
    const gapResult = AlHarasTopologicalVerifier.verifyYangMillsMassGap(lucasScalar, powerOrder);
    if (!gapResult.gapPositive) {
      return silentDropIntoVacuum();
    }

    // Structural resonance established: materialize geometry
    const materialization: GeometricMaterializationResult = {
      resonance_valid: true,
      manifoldDimension: 11,
      spectralGapNum: gapResult.gapNum,
      spectralGapDen: gapResult.gapDen,
      cassiniDeterminant: reportedDet,
      resonantNodeId: `NODE-11D-ZECK-${indices.join("-")}`,
      targetSubnet: req.path.includes("compass") ? "HYBA_COMPASS" : "HYBA_CORTEX",
      materializedTimestamp: Date.now(),
    };

    // Attach materialized geometric state to request context
    (req as any).alHarasResonance = materialization;
    return next();
  } catch {
    // Any parsing anomaly or arithmetic exception -> Vacuum drop
    return silentDropIntoVacuum();
  }
}
