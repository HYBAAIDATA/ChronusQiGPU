import {
  AlHarasTopologicalVerifier,
  generateClientHodgeResonanceHeaders,
} from "../src/security/al_haras_gateway";

async function runAlHarastTest() {
  console.log("==================================================");
  console.log("AL HARAS STRUCTURAL RESONANCE HANDSHAKE TEST SUITE");
  console.log("==================================================\n");

  const powerOrder = 13;
  console.log(`[+] Generating client Hodge-Resonance Headers for n=${powerOrder}...`);
  const headers = generateClientHodgeResonanceHeaders(powerOrder);
  console.log(JSON.stringify(headers, null, 2));

  // 1. Verify Zeckendorf Indices
  console.log("\n[1] Verifying Zeckendorf Canonical Non-Consecutive Rule...");
  const zeckendorfStr = headers["x-alharas-zeckendorf"];
  const indices = zeckendorfStr.split(",").map((s) => parseInt(s.trim(), 10));
  const zeckValid = AlHarasTopologicalVerifier.verifyZeckendorfIndices(indices);
  console.log(`  -> Indices: [${indices.join(", ")}]`);
  console.log(`  -> Valid: ${zeckValid ? "PASS (No consecutive Fibonacci indices)" : "FAIL"}`);

  // 2. Verify Cassini Invariant
  console.log("\n[2] Verifying Cassini Exact Invariant det(M^n) = (-1)^n...");
  const reportedDet = BigInt(headers["x-alharas-cassini-det"]);
  const cassiniValid = AlHarasTopologicalVerifier.verifyCassiniInvariant(powerOrder, reportedDet);
  console.log(`  -> Reported det: ${reportedDet}`);
  console.log(
    `  -> Valid: ${cassiniValid ? "PASS (Zero-cost structural integrity confirmed)" : "FAIL"}`,
  );

  // 3. Verify Yang-Mills Mass Gap
  console.log("\n[3] Verifying Yang-Mills Mass Gap Vacuum Filter (Δ > 0)...");
  const lucasScalar = BigInt(headers["x-alharas-lucas-scalar"]);
  const gapResult = AlHarasTopologicalVerifier.verifyYangMillsMassGap(lucasScalar, powerOrder);
  console.log(`  -> Lucas Scalar (n=${powerOrder}): ${lucasScalar}`);
  console.log(
    `  -> Spectral Gap (Δλ): ${gapResult.gapNum}/${gapResult.gapDen} = ${Number(gapResult.gapNum) / Number(gapResult.gapDen)}`,
  );
  console.log(
    `  -> Vacuum Positivity: ${gapResult.gapPositive ? "PASS (Δ > 0, Request materialized out of vacuum)" : "FAIL (Silent Drop)"}`,
  );

  console.log("\n==================================================");
  if (zeckValid && cassiniValid && gapResult.gapPositive) {
    console.log("[✓] AUTHENTICATION SUCCESS: 11D Manifold geometric routing materialized.");
  } else {
    console.log("[x] AUTHENTICATION FAILURE: Request dropped into the vacuum.");
  }
}

runAlHarastTest().catch(console.error);
