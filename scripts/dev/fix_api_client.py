# fix_api_client.py - Remove synthetic methods from api-client.ts
path = "c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/frontend/lib/api-client.ts"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()


def rep(old, new):
    global c
    assert old in c, "NOT FOUND: " + old[:100]
    c = c.replace(old, new)


# 1. Remove executeAgenticSheafTurn (demo method unrelated to mining)
rep('''  static executeAgenticSheafTurn = (agentStates?: Record<string, number[]>, stalkDim = 4) =>
    post<ApiRecord>('v1/al-haras/applications/agentic-sheaf/verify-turn', {
      agent_states: agentStates || {
        Planner: [1.0, 0.0, 0.0, 1.0],
        Coder: [1.0, 0.0, 0.0, 1.0],
        Executor: [1.0, 0.0, 0.0, 1.0],
        Tool: [1.0, 0.0, 0.0, 1.0],
      },
      stalk_dim: stalkDim,
    });

''', '')

# 2. Remove transmitOrbitalTelemetry (demo method unrelated to mining)
rep('''  static transmitOrbitalTelemetry = (
    packetPayload = 'SDA_PWSA_TELEMETRY_STREAM_PACKET_001',
    sourceSat = 'SAT_00',
    targetSat = 'SAT_07',
    constellationSize = 16
  ) =>
    post<ApiRecord>('v1/al-haras/applications/orbital-mesh/transmit', {
      packet_payload: packetPayload,
      source_sat: sourceSat,
      target_sat: targetSat,
      constellation_size: constellationSize,
    });

''', '')

# 3. Remove executeZkNeuralProveAndVerify (demo method unrelated to mining)
rep('''  static executeZkNeuralProveAndVerify = (
    sensorInput: number[] = [12, 24, 36, 48],
    weightsCommitment = 'sovereign_weights_merkle_root_v4_7f9c2b'
  ) =>
    post<ApiRecord>('v1/al-haras/applications/zk-neural/prove-and-verify', {
      sensor_input: sensorInput,
      weights_commitment: weightsCommitment,
    });

''', '')

# 4. Remove processCBDCCrossBorderSettlement (demo method unrelated to mining)
rep('''  static processCBDCCrossBorderSettlement = (
    senderBank = 'FEDERAL_RESERVE',
    receiverBank = 'BANK_OF_ENGLAND',
    amountTokens = 10000000,
    simulateDoubleSpend = false
  ) =>
    post<ApiRecord>('v1/al-haras/applications/cbdc-settlement/process', {
      sender_bank: senderBank,
      receiver_bank: receiverBank,
      amount_tokens: amountTokens,
      simulate_double_spend: simulateDoubleSpend,
    });

''', '')

# 5. Remove executeTISAMicrocode (demo method unrelated to mining)
rep('''  static executeTISAMicrocode = (
    funct7 = 0x02,
    rs1Val: [number, number, number, number] = [1, 2, 0, 0],
    rs2Val: [number, number, number, number] = [3, 1, 0, 0],
    rs1 = 1,
    rs2 = 2,
    rd = 3
  ) =>
    post<ApiRecord>('v1/al-haras/applications/t-isa/execute', {
      funct7,
      rs1,
      rs2,
      rd,
      rs1_val: rs1Val,
      rs2_val: rs2Val,
    });

''', '')

# 6. Remove injectMiningAnomaly (synthetic - backend method removed)
rep('''  static injectMiningAnomaly = () => post<ApiRecord>('v1/mining/admin/anomaly/inject', {});
  static healMiningAnomaly = () => post<ApiRecord>('v1/mining/admin/anomaly/heal', {});
''', '')

# 7. Remove simulatePatroclusMining (synthetic fake pool simulation)
rep('''  static simulatePatroclusMining = (pools?: string[]) =>
    post<ApiRecord>('v1/mining/admin/patroclus/simulate', { pools });
''', '')

# Write
with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("OK: api-client.ts updated")
