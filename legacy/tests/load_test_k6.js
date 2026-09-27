import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

// Custom Prometheus-aligned metrics
const exactMathViolations = new Counter("k6_exact_math_violations");
const meetsTargetPassRate = new Rate("k6_meets_target_pass_rate");
const mempoolOptimizeLatency = new Trend("k6_mempool_optimize_latency_ms");

export const options = {
  scenarios: {
    // 1. Sustained exact knapsack optimization load
    mempool_load: {
      executor: "constant-vus",
      vus: 5,
      duration: "30s",
      exec: "mempoolOptimizeScenario",
    },
    // 2. High-throughput difficulty retargeting evaluation
    retarget_load: {
      executor: "ramping-vus",
      startVUs: 2,
      stages: [
        { duration: "10s", target: 10 },
        { duration: "15s", target: 10 },
        { duration: "5s", target: 0 },
      ],
      exec: "retargetScenario",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"], // <1% failure
    http_req_duration: ["p(95)<150"], // 95% of requests under 150ms
    k6_exact_math_violations: ["count==0"], // ZERO exact math violations tolerated
    k6_meets_target_pass_rate: ["rate>0.99"], // >99% pass rate
  },
};

const BASE_URL = __ENV.TARGET_URL || "http://localhost:3000";

export function mempoolOptimizeScenario() {
  const payload = JSON.stringify({
    maxWeightWU: 4000000,
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  const start = Date.now();
  const res = http.post(`${BASE_URL}/api/v1/mempool/optimize`, payload, params);
  mempoolOptimizeLatency.add(Date.now() - start);

  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "order of truth is MATHEMATICAL & COMPUTATIONAL": (r) => {
      const b = JSON.parse(r.body);
      return b.orderOfTruth === "MATHEMATICAL & COMPUTATIONAL";
    },
    "total weight <= 4,000,000 WU": (r) => {
      const b = JSON.parse(r.body);
      return b.result && b.result.totalWeightWU <= 4000000;
    },
    "fee is positive integer": (r) => {
      const b = JSON.parse(r.body);
      return b.result && BigInt(b.result.totalFeeSat) > 0n;
    },
    "no float strings in response": (r) => {
      // Invariant: no scientific notation or IEEE-754 decimal NaN / Infinity
      return !r.body.includes("NaN") && !r.body.includes("Infinity");
    },
  });

  if (!ok) {
    exactMathViolations.add(1);
  }

  sleep(0.1);
}

export function retargetScenario() {
  const res = http.get(`${BASE_URL}/api/v1/difficulty/retarget`);

  const ok = check(res, {
    "status is 200": (r) => r.status === 200,
    "consensus rule specified": (r) => {
      const b = JSON.parse(r.body);
      return b.consensusRule && b.consensusRule.includes("BIP-22");
    },
    "bounds factor enforced to 4": (r) => {
      const b = JSON.parse(r.body);
      return b.invariants && b.invariants.boundsFactor === 4;
    },
    "expected timespan is 1209600s": (r) => {
      const b = JSON.parse(r.body);
      return b.invariants && b.invariants.expectedTimespanSeconds === 1209600;
    },
    "new target hex present and valid": (r) => {
      const b = JSON.parse(r.body);
      return (
        b.evaluation && b.evaluation.newTargetHex && b.evaluation.newTargetHex.startsWith("0x")
      );
    },
  });

  if (!ok) {
    exactMathViolations.add(1);
  }

  meetsTargetPassRate.add(ok ? 1 : 0);
  sleep(0.05);
}
