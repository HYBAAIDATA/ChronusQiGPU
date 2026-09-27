import { create } from "zustand";
import {
  fetchHealth,
  fetchStatus,
  fetchIntelligenceStatus,
  fetchFabricMap,
  fetchTelemetry,
  postMiningControl,
  postAgenticControl,
  postIntelSelfTest,
  type BackendHealth,
  type MlaStatus,
  type IntelligenceStatus,
  type FabricMap,
  type TelemetrySummary,
} from "./backend";

const POLL_MS = 2_000;
const STALE_MS = 15_000;
const FAIL_THRESHOLD = 3;

export type RecoveryState =
  | "ok"
  | "degraded"
  | "recovering"
  | "circuit_open"
  | "fail_closed";

export interface RecoveryInfo {
  state: RecoveryState;
  consecutiveFailures: number;
  lastFault: string | null;
  lastFaultAt: number | null;
  salamanderNotified: boolean;
}

export interface BackendState {
  health: BackendHealth;
  status: MlaStatus | null;
  intelligenceStatus: IntelligenceStatus | null;
  fabricMap: FabricMap | null;
  telemetry: TelemetrySummary | null;
  loading: boolean;
  polling: boolean;
  lastUpdated: number | null;
  recovery: RecoveryInfo;
  // Actions
  refresh: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
  startMining: () => Promise<void>;
  stopMining: () => Promise<void>;
  startAgentic: () => Promise<void>;
  stopAgentic: () => Promise<void>;
  runSelfTest: () => Promise<void>;
  reportFault: (kind: string, detail?: string) => Promise<void>;
}

let _timer: ReturnType<typeof setInterval> | null = null;

async function postSalamanderFault(kind: string, detail?: string): Promise<boolean> {
  try {
    const res = await fetch("/api/v1/salamander/fault", {
      method: "POST",
      headers: { accept: "application/json", "content-type": "application/json" },
      body: JSON.stringify({
        source: "pythia_frontend",
        kind,
        detail: detail ?? null,
        at: new Date().toISOString(),
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

function nextRecovery(
  prev: RecoveryInfo,
  ok: boolean,
  fault: string | null,
): RecoveryInfo {
  if (ok) {
    return {
      state: "ok",
      consecutiveFailures: 0,
      lastFault: prev.lastFault,
      lastFaultAt: prev.lastFaultAt,
      salamanderNotified: false,
    };
  }
  const failures = prev.consecutiveFailures + 1;
  let state: RecoveryState = "degraded";
  if (failures >= FAIL_THRESHOLD * 2) state = "fail_closed";
  else if (failures >= FAIL_THRESHOLD) state = "circuit_open";
  else if (failures > 1) state = "recovering";
  return {
    state,
    consecutiveFailures: failures,
    lastFault: fault ?? prev.lastFault,
    lastFaultAt: Date.now(),
    salamanderNotified: prev.salamanderNotified,
  };
}

export const useBackend = create<BackendState>((set, get) => ({
  health: { ok: false },
  status: null,
  intelligenceStatus: null,
  fabricMap: null,
  telemetry: null,
  loading: false,
  polling: false,
  lastUpdated: null,
  recovery: {
    state: "ok",
    consecutiveFailures: 0,
    lastFault: null,
    lastFaultAt: null,
    salamanderNotified: false,
  },

  refresh: async () => {
    set({ loading: true });
    const [health, status, intelligenceStatus, fabricMap, telemetry] =
      await Promise.all([
        fetchHealth(),
        fetchStatus(),
        fetchIntelligenceStatus(),
        fetchFabricMap(),
        fetchTelemetry(),
      ]);

    const ok = health.ok;
    const fault = ok ? null : health.error ?? "unreachable";
    let recovery = nextRecovery(get().recovery, ok, fault);

    // Stale status: backend responds but last payload is too old
    if (ok && get().lastUpdated && Date.now() - (get().lastUpdated ?? 0) > STALE_MS * 3) {
      recovery = nextRecovery(recovery, false, "stale_status");
    }

    // Notify Salamander once when circuit opens (governed recovery trigger)
    if (
      (recovery.state === "circuit_open" || recovery.state === "fail_closed") &&
      !recovery.salamanderNotified
    ) {
      const notified = await postSalamanderFault(
        recovery.lastFault ?? "frontend_backend_boundary",
        `consecutiveFailures=${recovery.consecutiveFailures}`,
      );
      recovery = { ...recovery, salamanderNotified: notified };
    }

    set({
      health,
      status: status ?? null,
      intelligenceStatus: intelligenceStatus ?? null,
      fabricMap: fabricMap ?? null,
      telemetry: telemetry ?? null,
      loading: false,
      lastUpdated: ok ? Date.now() : get().lastUpdated,
      recovery,
    });
  },

  startPolling: () => {
    if (_timer !== null) return;
    set({ polling: true });
    void get().refresh();
    _timer = setInterval(() => void get().refresh(), POLL_MS);
  },

  stopPolling: () => {
    if (_timer !== null) {
      clearInterval(_timer);
      _timer = null;
    }
    set({ polling: false });
  },

  startMining: async () => {
    const ok = await postMiningControl("start");
    if (!ok) await get().reportFault("mining_start_failed");
    setTimeout(() => void get().refresh(), 500);
  },

  stopMining: async () => {
    await postMiningControl("stop");
    setTimeout(() => void get().refresh(), 500);
  },

  startAgentic: async () => {
    const ok = await postAgenticControl("start");
    if (!ok) await get().reportFault("agentic_start_failed");
    setTimeout(() => void get().refresh(), 500);
  },

  stopAgentic: async () => {
    await postAgenticControl("stop");
    setTimeout(() => void get().refresh(), 500);
  },

  runSelfTest: async () => {
    const ok = await postIntelSelfTest();
    if (!ok) await get().reportFault("selftest_failed");
    setTimeout(() => void get().refresh(), 800);
  },

  reportFault: async (kind: string, detail?: string) => {
    const recovery = nextRecovery(get().recovery, false, kind);
    const notified = await postSalamanderFault(kind, detail);
    set({
      recovery: {
        ...recovery,
        salamanderNotified: notified || recovery.salamanderNotified,
      },
    });
  },
}));
