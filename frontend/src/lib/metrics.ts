/**
 * Prometheus metrics registry for EUCLID-CORE.
 *
 * Uses `prom-client` to expose a standards-compliant /metrics endpoint with
 * real counters, gauges, and histograms. Custom metrics are namespaced under
 * `euclid_*` and match the alert expressions in infra/prometheus/alerts.yml.
 */
import { Counter, Gauge, Histogram, Registry, collectDefaultMetrics } from "prom-client";

export const register = new Registry();
register.setDefaultLabels({ service: "euclid-core" });
collectDefaultMetrics({ register });

// HTTP request metrics
export const httpRequestsTotal = new Counter({
  name: "http_requests_total",
  help: "Total HTTP requests",
  labelNames: ["method", "route", "status"],
  registers: [register],
});

export const httpRequestDurationSeconds = new Histogram({
  name: "http_request_duration_seconds",
  help: "HTTP request duration in seconds",
  labelNames: ["method", "route", "status"],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
  registers: [register],
});

// EUCLID domain metrics (aligned with infra/prometheus/alerts.yml)
export const euclidSharesTotal = new Counter({
  name: "euclid_shares_total",
  help: "Total submitted Stratum shares",
  labelNames: ["worker", "result"],
  registers: [register],
});

export const euclidStratumConnected = new Gauge({
  name: "euclid_stratum_connected",
  help: "Stratum pool connection status (1 = connected, 0 = disconnected)",
  labelNames: ["worker"],
  registers: [register],
});

export const euclidStratumRttMs = new Histogram({
  name: "euclid_stratum_rtt_ms",
  help: "Round trip time to mining pool in ms",
  labelNames: ["worker"],
  buckets: [10, 25, 50, 100, 150, 250, 500, 1000],
  registers: [register],
});

export const euclidSessionsActive = new Gauge({
  name: "euclid_sessions_active",
  help: "Active stratum sessions count",
  labelNames: ["worker", "status"],
  registers: [register],
});

export const euclidExactMathViolations = new Counter({
  name: "euclid_exact_math_violations_total",
  help: "Count of exact mathematical invariant breaches (must be 0)",
  registers: [register],
});

export const euclidAuditHashMismatch = new Counter({
  name: "euclid_audit_hash_mismatch_total",
  help: "Count of state hash mismatches in exact audit ledger",
  registers: [register],
});

export const euclidExactAuditRows = new Counter({
  name: "euclid_exact_audit_rows_total",
  help: "Total recorded exact audit rows",
  labelNames: ["worker"],
  registers: [register],
});

export const euclidGroverRuns = new Counter({
  name: "euclid_grover_runs_total",
  help: "Total Chebyshev Grover search runs executed",
  labelNames: ["worker"],
  registers: [register],
});

export const euclidTemplateWeight = new Gauge({
  name: "euclid_template_weight_wu",
  help: "Total weight units of current candidate block template",
  registers: [register],
});

export const euclidTemplateFee = new Gauge({
  name: "euclid_template_fee_sat",
  help: "Total satoshi transaction fees in candidate block template",
  registers: [register],
});

export const euclidMempoolSize = new Gauge({
  name: "euclid_mempool_size_txs",
  help: "Count of transactions in cached mempool snapshot",
  registers: [register],
});

export const euclidMempoolSnapshotTimestamp = new Gauge({
  name: "euclid_mempool_snapshot_timestamp_seconds",
  help: "Timestamp of last mempool refresh (unix seconds)",
  registers: [register],
});

export const euclidSharesStale = new Gauge({
  name: "euclid_shares_stale",
  help: "Shares older than 5 minutes without pool ACK",
  labelNames: ["worker"],
  registers: [register],
});

// ---------------------------------------------------------------------------
// iGPU-on-11D self-telemetry. Every value here is MEASURED (counters and
// observations from work that actually completed) and never a projection, a
// scaling multiplier, or a Lucas estimate. `gpu_dispatch_ratio` and the
// device labels exist so a CPU fallback can never be reported as a GPU.
// ---------------------------------------------------------------------------

export const euclidIgpuDispatchTotal = new Counter({
  name: "euclid_chronus_dispatch_total",
  help: "iGPU dispatch batches that actually executed",
  labelNames: ["backend", "device_type", "gpu"],
  registers: [register],
});

export const euclidIgpuWorkItemsTotal = new Counter({
  name: "euclid_chronus_work_items_total",
  help: "Work items (candidates/slots) processed by iGPU dispatches",
  labelNames: ["backend"],
  registers: [register],
});

export const euclidIgpuKernelSecondsTotal = new Counter({
  name: "euclid_chronus_kernel_seconds_total",
  help: "Measured kernel time accumulated across iGPU dispatches",
  labelNames: ["backend"],
  registers: [register],
});

export const euclidIgpuGpuDispatchRatio = new Gauge({
  name: "euclid_chronus_gpu_dispatch_ratio",
  help: "Fraction of iGPU dispatches that genuinely ran on a device (1 = all GPU)",
  registers: [register],
});

export const euclidIgpuThroughputPerSecond = new Gauge({
  name: "euclid_chronus_measured_throughput_per_second",
  help: "Measured work items per second (busy kernel time only, never projected)",
  labelNames: ["backend"],
  registers: [register],
});

export const euclidIgpuManifoldPunchesTotal = new Counter({
  name: "euclid_chronus_manifold_punches_total",
  help: "Work items dispatched to 11D manifold punches (dim = 11)",
  registers: [register],
});

export const euclidIgpuManifoldIntegrity = new Gauge({
  name: "euclid_chronus_manifold_integrity_ok",
  help: "1 when the 11D fold roundtrip and ball containment held, 0 otherwise",
  registers: [register],
});

export const euclidIgpuDevicePresent = new Gauge({
  name: "euclid_chronus_device_present",
  help: "1 when a real compute device is bound, 0 when on the CPU fallback",
  labelNames: ["device_name", "device_type"],
  registers: [register],
});

// ---------------------------------------------------------------------------
// iGPU-on-11D overlay telemetry — the M32 dodecahedral/icosahedral frame.
//
// This is NOT one solver. The substrate is a 32-face polyhedral overlay on
// 11D: 12 icosahedral faces + 20 dodecahedral faces = 32, fired together each
// step as an overcomplete frame, whose unit of work is the relationship
// between two faces: C(32,2) = 496 channels.
//
// Honesty: the geometry (32/12/20/496) is a FACT and is reported as such.
// The channel OCCUPANCY is MEASURED. Any 496-based throughput figure is a
// labelled PROJECTION and is exposed only on `_projected_` series, never on
// the measured `euclid_chronus_measured_throughput_per_second` series.
// ---------------------------------------------------------------------------

export const euclidIgpuOverlayFaces = new Gauge({
  name: "euclid_chronus_overlay_faces",
  help: "Faces in the M32 overlay (12 icosahedral + 20 dodecahedral = 32)",
  labelNames: ["shell"],
  registers: [register],
});

export const euclidIgpuOverlayChannelsOccupied = new Gauge({
  name: "euclid_chronus_overlay_channels_occupied",
  help: "Face-pair channels exercised so far, out of C(32,2) = 496",
  registers: [register],
});

export const euclidIgpuOverlayChannelOccupancyRatio = new Gauge({
  name: "euclid_chronus_overlay_channel_occupancy_ratio",
  help: "Occupied face-pair channels / 496 (measured, 1 = full frame observed)",
  registers: [register],
});

export const euclidIgpuOverlayChannelUsesTotal = new Counter({
  name: "euclid_chronus_overlay_channel_uses_total",
  help: "Total face-pair channel activations across all frame steps",
  registers: [register],
});

export const euclidIgpuFrameStepsTotal = new Counter({
  name: "euclid_chronus_frame_steps_total",
  help: "Overlay frame steps executed (all faces fired together)",
  labelNames: ["fallback"],
  registers: [register],
});

export const euclidIgpuShellEnergyShare = new Gauge({
  name: "euclid_chronus_shell_energy_share_icosahedral",
  help: "Share of frame energy carried by the 12 icosahedral faces (isotropic = 0.375)",
  registers: [register],
});

export const euclidIgpuEffectiveThroughputProjected = new Gauge({
  name: "euclid_chronus_effective_throughput_projected_per_second",
  help: "PROJECTION ONLY: measured throughput x 496. Never a measurement.",
  registers: [register],
});

export function recordHttpRequest(
  method: string,
  route: string,
  status: number,
  durationSeconds: number,
): void {
  httpRequestsTotal.inc({ method, route, status: String(status) });
  httpRequestDurationSeconds.observe({ method, route, status: String(status) }, durationSeconds);
}
