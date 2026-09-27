// LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
// inline below. MUST NOT import from any sibling algorithm.
// Substrate route: amplitude

import { ExactSequenceMath } from "./exact_math";

/**
 * EUCLID-CORE: Cortex Intelligence Adapter
 *
 * Bridges the HYBA cortex modules (golden transform, topological context,
 * spectral context, gauge training) and the UniversalPredictor into the
 * TypeScript backend via src/cortex_bridge.py.
 *
 * Order of Truth: COMPUTATIONAL. Availability is probed honestly — if the
 * Python runtime or a module is missing, `available: false` is returned
 * rather than simulated output.
 */

import { execFile } from "child_process";
import * as path from "path";

const BRIDGE_PATH = path.resolve(__dirname, "..", "cortex_bridge.py");
const TIMEOUT_MS = 8000;

export interface CortexModuleStatus {
  cortex_golden_transform: boolean;
  cortex_topological_context: boolean;
  cortex_spectral_context: boolean;
  cortex_gauge_training: boolean;
  universal_predictor: boolean;
}

export interface CortexStatus {
  available: boolean;
  reason?: string;
  modules?: CortexModuleStatus;
}

export interface CortexAssessment {
  available: boolean;
  reason?: string;
  golden?: Record<string, unknown>;
  topological?: Record<string, unknown>;
  spectral?: Record<string, unknown>;
}

export interface PredictorProfile {
  available: boolean;
  reason?: string;
  profile?: Record<string, unknown>;
}

async function runBridge(command: string, payload?: unknown): Promise<any> {
  const args = [BRIDGE_PATH, command];
  if (payload !== undefined) args.push(JSON.stringify(payload));

  return new Promise((resolve, reject) => {
    execFile(
      process.env.PYTHON_BIN || "python",
      args,
      {
        timeout: TIMEOUT_MS,
        maxBuffer: 4 * 1024 * 1024,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      },
      (err, stdout, stderr) => {
        // The bridge prints dependency warnings before the JSON payload;
        // the result is the last non-empty stdout line.
        const lines = stdout
          .trim()
          .split(/\r?\n/)
          .filter((l) => l.trim());
        const jsonLine = lines[lines.length - 1] ?? "";
        let parsed: any;
        try {
          parsed = JSON.parse(jsonLine);
        } catch {
          return reject(
            new Error(
              `cortex_bridge parse failure: ${err?.message ?? stderr ?? stdout.slice(0, 400)}`,
            ),
          );
        }
        if (err && !parsed.success) {
          return reject(new Error(parsed.error ?? err.message));
        }
        resolve(parsed);
      },
    );
  });
}

export class CortexIntelligence {
  private static cachedStatus: CortexStatus | null = null;

  static async status(): Promise<CortexStatus> {
    if (this.cachedStatus) return this.cachedStatus;
    try {
      const res = await runBridge("status");
      this.cachedStatus = { available: true, modules: res.modules };
    } catch (e: any) {
      this.cachedStatus = { available: false, reason: e.message };
    }
    return this.cachedStatus;
  }

  static async assess(context: number[], epoch = 0): Promise<CortexAssessment> {
    const status = await this.status();
    if (!status.available) return { available: false, reason: status.reason };
    try {
      const res = await runBridge("assess", { context, epoch });
      return {
        available: true,
        golden: res.golden,
        topological: res.topological,
        spectral: res.spectral,
      };
    } catch (e: any) {
      return { available: false, reason: e.message };
    }
  }

  static async predict(entityData: Record<string, unknown>): Promise<PredictorProfile> {
    const status = await this.status();
    if (!status.available) return { available: false, reason: status.reason };
    try {
      const res = await runBridge("predict", { entity_data: entityData });
      return { available: true, profile: res.profile };
    } catch (e: any) {
      return { available: false, reason: e.message };
    }
  }

  /** For tests: forget the cached availability probe. */
  static resetCache() {
    this.cachedStatus = null;
  }
}
export function lucasBound(n = 10): { module: string; n: number; lucasBound: number; route: string; theoremProven: false } {
  return { module: "cortex_intelligence", n, lucasBound: Number(ExactSequenceMath.lucas(n)), route: "amplitude", theoremProven: false };
}
