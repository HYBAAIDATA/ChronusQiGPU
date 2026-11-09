# fix_mining_page.py - Remove synthetic elements from mining page.tsx
path = "c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/frontend/app/mining/page.tsx"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()


def rep(old, new):
    global c
    assert old in c, "NOT FOUND: " + old[:100]
    c = c.replace(old, new)


# 1. Remove anomalyInjected and dswHealed state declarations
rep('''  // Mode 4: Topological (Sheaf Cohomology H^1 & 1-Cycle DSW Monopole)
  const [anomalyInjected, setAnomalyInjected] = useState<boolean>(false);
  const [dswHealed, setDswHealed] = useState<boolean>(false);

''', '')

# 2. Remove simulation state declarations
rep('''  // Mode 6: Patroclus Gateway & 600 Myrmidon Searchers
  const [activePhalanx, setActivePhalanx] = useState<number>(0);
  const [simulationRunning, setSimulationRunning] = useState<boolean>(false);
  const [simulationLogs, setSimulationLogs] = useState<string[]>([]);
  const [simulationStatus, setSimulationStatus] = useState<string | null>(null);

''', '')

# 3. Remove lastMinedBlock state (hardcoded 850000)
rep('''  const [lastMinedBlock, setLastMinedBlock] = useState<number>(850000);

''', '')

# 4. Remove h1Obstruction/resonancePct/causalBoost computed from local synthetic state
rep('''  // Blockchain Resonance Metric R_block & Hashrate Boost
  const h1Obstruction = anomalyInjected && !dswHealed;
  const resonancePct = h1Obstruction ? 0.0 : 2.61;
  const causalBoost = activeIntervention === 'UNDERVOLT_1_10V' ? 15.8 : (activeIntervention === 'FAN_100_PCT' ? 8.4 : 0.0);
  const effectiveHashrate = isRunning ? Number((baseHashrate * (1 + resonancePct / 100) + causalBoost).toFixed(2)) : 0.0;''',
'''  // Effective hashrate from backend status (no fabricated resonance boost)
  const effectiveHashrate = isRunning ? Number(baseHashrate.toFixed(2)) : 0.0;''')

# 5. Remove handleInjectAnomaly function (calls removed API)
rep('''  async function handleInjectAnomaly() {
    setAnomalyInjected(true);
    setDswHealed(false);
    try {
      await ChronusAPIClient.injectMiningAnomaly();
    } catch {
      // Retain local state
    }
  }

''', '')

# 6. Remove handleHealAnomaly function (calls removed API)
rep('''  async function handleHealAnomaly() {
    setDswHealed(true);
    setAnomalyInjected(false);
    try {
      await ChronusAPIClient.healMiningAnomaly();
    } catch {
      // Retain local state
    }
  }

''', '')

# 7. Remove handleRunSimulation function (calls removed simulatePatroclusMining)
rep('''  async function handleRunSimulation() {
    setSimulationRunning(true);
    setSimulationLogs(['[Patroclus] Connecting to mock multi-pool sockets (ViaBTC, Braiins, NiceHash, CKPool)...']);
    try {
      await ChronusAPIClient.simulatePatroclusMining();
      setSimulationStatus('SUCCESS: 100% Share Acceptance Across All 4 Pools');
      setSimulationLogs([
        '[Step 1] mining.configure: Negotiated Version-Rolling Mask=1fffe000',
        '[Step 2] mining.subscribe: ExtraNonce1=a45b7889, ExtraNonce2_Size=4',
        '[Step 3] mining.extranonce.subscribe: Result=True',
        '[Step 4] mining.authorize: Worker "chronus_head_worker" (Diff Hint "d=131072")',
        '[Step 5] mining.set_difficulty PUSH: Share Difficulty=1',
        '[Step 6] mining.notify PUSH: Job ID received, PrevHash word-swapped (>8I -> <8I)',
        '[Step 7] F_257 Galois Phase Matching: Alpha=17, Beta(M=1)=120',
        '[Step 7] Myrmidon Swarm: Nonce 0x7c2bac1d isolated by Searcher #291 (Phalanx #4)',
        '[GATEKEEPER] 3µs Local SHA-256d Gatekeeper Assertion: Hash <= Target (VERIFIED)',
        '[STEALTH] Never Consecutive Blocks Rule verified for Block #850000',
        '[Step 8] mining.submit (6-Param Wire Submit): Result=True (100% Accepted)',
      ]);
    } catch {
      setSimulationStatus('Local Simulation Complete (Offline Fallback)');
      setSimulationLogs([
        '[Step 1-8] Patroclus Gateway 8-Step Handshake Verified',
        '[GATEKEEPER] 3µs Local Gatekeeper: Nonce 0x7c2bac1d Hash <= Target (3µs verified)',
        '[STEALTH] 1.0 EH/s active throttle maintained with persistent heartbeat presence',
      ]);
    } finally {
      setSimulationRunning(false);
    }
  }

''', '')

# Write
with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("OK: mining page.tsx step 1 updated")
