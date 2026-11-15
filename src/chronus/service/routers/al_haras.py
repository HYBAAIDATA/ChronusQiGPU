"""AL HARAS (HYBA Security) API.

Every response is computed by the AL HARAS engines for the request at hand:
state consistency (exact cellular-sheaf coboundary), Reed-Solomon trace repair,
an exactly certified Paley expander, exact braid relations, and decision
receipts signed with both Ed25519 and ML-DSA-87 (FIPS 204). Nothing here reports a certification or a hardware result.
POST endpoints require tenant authentication; GET endpoints are read-only.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from chronus.security.al_haras.hardware_t_isa import (
    RTL_SEMANTICS,
    STATUS_FAULT,
    STATUS_HARMONIC_CONSENSUS,
    STATUS_UNCHECKED,
    HardwareFault,
)
from chronus.security.al_haras.orbital_mesh import link_summary
from chronus.security.al_haras.reed_solomon import ReedSolomonError
from chronus.security.al_haras.sheaf import SheafError
from chronus.security.al_haras.sovereign import describe_key_custody
from chronus.core.seal import scrub_dict_strings
from chronus.security.al_haras.topological_os import public_self_tests, run_self_tests
from chronus.service.dependencies import get_current_tenant

from chronus.security.al_haras import (
    ALHarasSovereignProductSDK,
    DSW4DInstantonMonopoleHealer,
    RamanujanExpanderSpectralGapGuard,
    SovereignGovernanceEngine,
    TacticalSwarmMeshEngine,
    PostQuantumSubstrateEngine,
    HyperscaleDefenseSimulationEngine,
    CNISelfHealingEngine,
    StrategicDefenseCoordinator,
    AgenticSheafGuard,
    RISCVTopologicalCoprocessor,
    TISAInstruction,
    TISAOpcode,
    OrbitalConstellationMesh,
    VerifiableNeuralComputeEngine,
    FormalTopologicalProofVerifier,
    AgentDAG,
    AgentState,
    AgenticSheafImmuneSystem,
    OrbitalSatelliteDefenseMesh,
    LineRateVerifiableNeuralCompute,
    SovereignCBDCSettlementEngine,
    SovereignSettlementRejection,
    SovereignCentralBank,
    RoCCInstruction,
    CoprocessorRegisters,
    MemoryBus,
    execute_t_isa_instruction,
    RicciCurvatureDeCloaker,
    HodgeCovertChannelFilter,
    UltrametricMemorySandbox,
    AnosovColdBootScrambler,
    PicardLefschetzAntiJammingFilter,
    GrandMillenniumUnificationNexus,
)

router = APIRouter(prefix="/v1/al-haras", tags=["al-haras-security"])

_TISA_MODEL_NOTE = "Python software model of a proposed coprocessor; no hardware is involved"
_TISA_STATUS_LABELS = {
    STATUS_UNCHECKED: "UNCHECKED",
    STATUS_HARMONIC_CONSENSUS: "CHECK_PASSED",
    STATUS_FAULT: "CHECK_FAILED",
}

MAX_PAYLOAD_CHARS = 65_536
FRONTIER_IDS = ("FRONTIER_1", "FRONTIER_2", "FRONTIER_3", "FRONTIER_4", "ALL")
Numeric = Union[int, float, str]


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"error": "invalid_input", "message": str(exc)},
    )


class InspectWorkloadRequest(BaseModel):
    payload: str = Field(default="", max_length=MAX_PAYLOAD_CHARS, description="Payload text to inspect and protect")
    state_vectors: Optional[List[List[Numeric]]] = Field(
        default=None,
        description="Node or agent state vectors (numbers or exact strings such as '1/3'); omit to skip the state check",
    )
    node_names: Optional[List[str]] = Field(default=None, description="Names for the state vectors, in order")
    edges: Optional[List[Tuple[str, str]]] = Field(
        default=None, description="Graph edges between named nodes; default is a ring over the given order"
    )
    tolerance: Numeric = Field(default=0, description="Largest per-edge residual norm accepted as agreement")
    sovereign_state_id: Optional[str] = Field(default=None, description="Tenant label recorded in the receipt")


class HealTraceRequest(BaseModel):
    trace_payload: str = Field(default="", max_length=MAX_PAYLOAD_CHARS, description="Trace to protect and check")
    is_corrupted: bool = Field(
        default=True,
        description="True: run a fault-injection drill (corrupt bytes, repair, verify). False: verify the trace only.",
    )
    fault_count: int = Field(default=1, ge=0, le=64, description="Bytes to corrupt in the drill")


class ProtectTraceRequest(BaseModel):
    trace_payload: str = Field(default="", max_length=MAX_PAYLOAD_CHARS)


class RepairTraceRequest(BaseModel):
    received_hex: str = Field(description="Received (possibly corrupted) trace bytes, hex encoded", max_length=2 * MAX_PAYLOAD_CHARS)
    envelope: Dict[str, Any] = Field(description="Envelope returned by POST /v1/al-haras/protect")


class FrontierSimulationRequest(BaseModel):
    frontier_id: Optional[str] = Field(
        default="ALL",
        description="Frontier ID ('FRONTIER_1', 'FRONTIER_2', 'FRONTIER_3', 'FRONTIER_4', or 'ALL')",
    )
    node_count: int = Field(default=16, ge=2, le=256, description="Frontier 1: swarm node count")
    jamming_intensity_db: Numeric = Field(default=45, description="Frontier 1: noise bound = min(dB / 1000, 1/20) per coordinate")
    simulate_hostile_strike: bool = Field(
        default=False, description="Frontier 1: inject an outlier node; frontier 4: run the fault-injection drill"
    )
    stream_packet: str = Field(default="REFERENCE_STREAM_PACKET", max_length=MAX_PAYLOAD_CHARS, description="Frontier 2: packet to sign a receipt for")
    mach_number: Numeric = Field(default=12.5, description="Frontier 3: upstream Mach number (read exactly)")
    fault_count: int = Field(default=1, ge=0, le=63, description="Frontier 4: bytes corrupted by the drill")


@router.get("/status")
async def get_al_haras_status() -> Dict[str, Any]:
    """Self-test results and implementation status, recomputed on every call."""
    tests = run_self_tests()
    public_tests = scrub_dict_strings(
        public_self_tests(tests), context="al_haras self_tests"
    )
    expander = RamanujanExpanderSpectralGapGuard.verify_mass_gap()
    governance = SovereignGovernanceEngine.audit_sovereign_compliance("status")
    return {
        "product": "AL HARAS (HYBA Security)",
        "status": "SELF_TEST_PASSED" if all(tests.values()) else "SELF_TEST_FAILED",
        "self_tests": public_tests,
        "implemented_checks": {
            "state_consistency": "exact cellular-sheaf coboundary with residual location and nearest-section repair",
            "trace_repair": "Reed-Solomon RS(48,32) over GF(257), Berlekamp-Welch decoding",
            "expander": {
                "graph": expander["graph"],
                "degree": expander["degree"],
                "lambda_2": expander["lambda_2_decimal"],
                "ramanujan_bound": expander["ramanujan_bound_decimal"],
                "spectral_gap": expander["spectral_gap_decimal"],
                "certified_exactly": expander["satisfies_bound"],
            },
            "braid_relations": "Exact braid representation over Z[zeta_5]",
            "receipts": "Ed25519 and ML-DSA-87 (FIPS 204) over canonical JSON; both must verify",
        },
        "not_implemented": [
            "LPS Cayley graph on PSL_2(F_257)",
            "FIPS 140-3 validated cryptographic module (signatures come from pyca/cryptography over OpenSSL)",
            "HSM or cloud KMS key custody",
            "hardware enforcement or clock-cycle latency",
        ],
        "governance": {
            "principles_independently_assessed": governance["principles_independently_assessed"],
            "certifications_held": governance["certifications_held"],
            "statement": governance["statement"],
        },
        "key_custody": describe_key_custody(),
    }


@router.post("/inspect")
async def inspect_workload(req: InspectWorkloadRequest, tenant_id: Optional[str] = Depends(get_current_tenant)) -> Dict[str, Any]:
    """Check node-state consistency, protect the payload, and sign the decision."""
    sdk = ALHarasSovereignProductSDK(sovereign_state_id=req.sovereign_state_id or tenant_id or "tenant")
    try:
        result = sdk.inspect_and_admit_workload(
            payload=req.payload.encode("utf-8"),
            state_vectors=req.state_vectors,
            edges=[list(e) for e in req.edges] if req.edges else None,
            tolerance=req.tolerance,
            node_names=req.node_names,
        )
    except (SheafError, ValueError, TypeError) as exc:
        raise _unprocessable(exc)
    if result["sheaf_cohomology"].get("status") == "INVALID_STATE_INPUT":
        raise _unprocessable(ValueError(result["sheaf_cohomology"].get("error", "invalid state input")))
    return result


@router.post("/heal")
async def heal_trace(req: HealTraceRequest, tenant_id: Optional[str] = Depends(get_current_tenant)) -> Dict[str, Any]:
    """Run a Reed-Solomon fault-injection drill (or a verify-only check) on a trace."""
    return DSW4DInstantonMonopoleHealer.inspect_and_heal(
        trace_payload=req.trace_payload.encode("utf-8"),
        is_perturbed=req.is_corrupted,
        fault_count=req.fault_count,
    )


@router.post("/protect")
async def protect_trace(req: ProtectTraceRequest, tenant_id: Optional[str] = Depends(get_current_tenant)) -> Dict[str, Any]:
    """Return the Reed-Solomon protection envelope for a trace."""
    from chronus.security.al_haras import reed_solomon

    return reed_solomon.protect(req.trace_payload.encode("utf-8"))


@router.post("/repair")
async def repair_trace(req: RepairTraceRequest, tenant_id: Optional[str] = Depends(get_current_tenant)) -> Dict[str, Any]:
    """Repair a received trace against an envelope from /protect."""
    try:
        received = bytes.fromhex(req.received_hex)
        return DSW4DInstantonMonopoleHealer.inspect_and_heal(
            trace_payload=received, envelope=req.envelope, received=received
        )
    except (ReedSolomonError, ValueError, KeyError, TypeError) as exc:
        raise _unprocessable(exc)


@router.get("/frontiers")
async def get_defense_frontiers() -> Dict[str, Any]:
    """Catalogue of the four capability demonstrations; known-answer self-checks run on each call."""
    return StrategicDefenseCoordinator.get_strategic_posture_overview()


@router.post("/frontiers/simulate")
async def simulate_defense_frontier(
    req: FrontierSimulationRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Run one capability demonstration (or all four) on the request's inputs."""
    fid = (req.frontier_id or "ALL").upper()
    if fid not in FRONTIER_IDS:
        raise _unprocessable(ValueError(f"frontier_id must be one of {list(FRONTIER_IDS)}"))
    try:
        if fid == "FRONTIER_1":
            return TacticalSwarmMeshEngine.evaluate_swarm_mesh(
                node_count=req.node_count,
                jamming_intensity_db=req.jamming_intensity_db,
                injected_adversarial_vector=req.simulate_hostile_strike,
            )
        if fid == "FRONTIER_2":
            return PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt(
                c4isr_stream_packet=req.stream_packet.encode("utf-8"),
                tenant_id=tenant_id or "anonymous",
            )
        if fid == "FRONTIER_3":
            return HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(mach_number=req.mach_number)
        if fid == "FRONTIER_4":
            return CNISelfHealingEngine.audit_and_heal_cni_asset(
                simulated_cyber_physical_strike=req.simulate_hostile_strike,
                fault_count=req.fault_count,
            )
        return StrategicDefenseCoordinator.run_all_frontier_simulations()
    except (ValueError, TypeError) as exc:
        raise _unprocessable(exc)


# ------------------------------------------------------------------------------
# EXPANSION ENDPOINTS: AGENTIC SHEAF, ORBITAL MESH, T-ISA, zk-ML & FORMAL PROOFS
# ------------------------------------------------------------------------------


class AgenticPromptRequest(BaseModel):
    prompt_text: str = Field(
        default="Plan constellation telemetry transfer.",
        max_length=MAX_PAYLOAD_CHARS,
        description="Prompt text to screen with the pattern heuristic",
    )
    session_id: str = Field(default="sess_demo_01", max_length=128)


class AgenticToolRequest(BaseModel):
    agent_id: str = Field(default="agent_01", max_length=128)
    tool_name: str = Field(default="run_database_query", max_length=128)
    tool_args: Dict[str, Any] = Field(default_factory=lambda: {"limit": 10})
    simulate_poisoning: bool = Field(default=False, description="Drill: alter the tool-input copy in transit")
    observed_copies: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Tool arguments as observed at 'agent_commitment', 'gateway_log' or 'tool_input' (default: tool_args everywhere)",
    )


class OrbitalMeshRequest(BaseModel):
    num_satellites: int = Field(default=16, ge=2, le=128)
    radiation_flux: Numeric = Field(default=5e4, description="Particles per cm^2 used by the upset drill")
    seu_cross_section_cm2: Numeric = Field(
        default="1/10000", description="Drill assumption: upsets per frame = floor(flux * cross-section)"
    )
    rf_jamming: bool = Field(default=True)
    jammed_link_ratio: Numeric = Field(default=0.25, description="Share of links jammed, in [0, 1]")
    jamming_strategy: Literal["hashed", "targeted"] = Field(default="hashed")
    seed: str = Field(default="al-haras-orbital", max_length=256)
    frame_bytes: int = Field(default=64, ge=1, le=4096)


class ZKMLInferenceRequest(BaseModel):
    layer_name: str = Field(default="layer_dense_0", max_length=128)
    input_values: List[int] = Field(default_factory=lambda: [10, 20, 30, 40], max_length=4096)
    weights_fingerprint: str = Field(
        default="a" * 64,
        max_length=256,
        description="Weight commitment; the demo registry holds placeholder strings for layer_dense_0 and layer_dense_1",
    )
    simulate_backdoor: bool = Field(
        default=False,
        description="Drill: alter one trace value after the honest run; the verifier has to detect it",
    )


@router.post("/agentic/intercept-prompt")
async def intercept_agent_prompt(
    req: AgenticPromptRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Screen a prompt with the pattern heuristic (a heuristic, not a sheaf or cohomology check)."""
    guard = AgenticSheafGuard(sovereign_authority=tenant_id or "anonymous")
    return guard.intercept_user_prompt(req.prompt_text, session_id=req.session_id)


@router.post("/agentic/intercept-tool")
async def intercept_agent_tool(
    req: AgenticToolRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Gate a tool call: pattern heuristic plus an exact comparison of three copies of the call."""
    guard = AgenticSheafGuard(sovereign_authority=tenant_id or "anonymous")
    try:
        return guard.intercept_tool_execution(
            agent_id=req.agent_id,
            tool_name=req.tool_name,
            tool_args=req.tool_args,
            simulate_poisoning=req.simulate_poisoning,
            observed_copies=req.observed_copies,
        )
    except (ValueError, TypeError) as exc:
        raise _unprocessable(exc)


@router.post("/orbital/simulate")
async def simulate_orbital_mesh(
    req: OrbitalMeshRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Jam links of a Paley-graph mesh and run a Reed-Solomon upset drill; every result is recomputed."""
    try:
        mesh = OrbitalConstellationMesh.create_reference_constellation(req.num_satellites)
        return mesh.simulate_space_weather_and_jamming(
            radiation_flux_particles_cm2=req.radiation_flux,
            anti_satellite_rf_jamming=req.rf_jamming,
            jammed_link_ratio=req.jammed_link_ratio,
            seu_cross_section_cm2=req.seu_cross_section_cm2,
            jamming_strategy=req.jamming_strategy,
            seed=req.seed.encode("utf-8"),
            frame_bytes=req.frame_bytes,
        )
    except (ValueError, TypeError) as exc:
        raise _unprocessable(exc)


@router.post("/zk-ml/verify")
async def verify_zk_ml_inference(
    req: ZKMLInferenceRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Build an F_257 trace receipt for the demo layer and verify it by exact recomputation.

    Not zero-knowledge and not succinct: the verifier re-derives the trace polynomial, the
    quotient and every evaluation from the disclosed trace (see zk_neural.py).
    """
    engine = VerifiableNeuralComputeEngine()
    try:
        package = engine.generate_inference_proof(
            layer_name=req.layer_name,
            input_data=req.input_values,
            weights_root=req.weights_fingerprint,
            simulate_tampering=req.simulate_backdoor,
        )
    except (TypeError, ValueError) as exc:
        raise _unprocessable(exc)
    result = engine.verify_inference_proof(package)
    result["claimed_output"] = package["claimed_output"]
    result["simulation"] = package["simulation"]
    return result


@router.get("/hardware/t-isa-diagnostics")
async def get_t_isa_diagnostics() -> Dict[str, Any]:
    """Run a fixed program and a Reed-Solomon scrub drill on the T-ISA software model."""
    coproc = RISCVTopologicalCoprocessor()
    z = 5
    q_z = (3 + z) % 257  # Q(X) = 3 + X evaluated at z
    p_z = q_z * (pow(z, 8, 257) - 1) % 257  # P = Q * (X^8 - 1) evaluated at z
    program = [
        TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(1, 2, 0, 0)),
        TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=2, imm=(3, 1, 0, 0)),
        TISAInstruction(TISAOpcode.T_CYCLO_ADD, rd=3, rs1=1, rs2=2),
        TISAInstruction(TISAOpcode.T_CYCLO_MUL, rd=4, rs1=1, rs2=2),
        TISAInstruction(TISAOpcode.T_SHEAF_INSPECT, rs1=1, rs2=1),
        TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=5, imm=(p_z, q_z, z, 8)),
        TISAInstruction(TISAOpcode.T_STARK_EVAL, rd=6, rs1=5),
    ]
    result = coproc.execute_program(program)
    upset_positions = [2, 9]
    corrupted = coproc.regfile.inject_upset(4, upset_positions)
    scrub = coproc.execute_instruction(TISAInstruction(TISAOpcode.T_DSW_HEAL, rd=4))
    result["ecc_drill"] = {
        "register": "T4",
        "corrupted_byte_positions": upset_positions,
        "corrupted_value": list(corrupted),
        "scrub": scrub,
        "value_after": list(coproc.regfile.read_128bit(4)),
    }
    result["registers"] = {f"T{i}": list(coproc.regfile.read_128bit(i)) for i in range(1, 7)}
    result["rtl_semantics"] = {f"0x{funct7:02x}": dict(entry) for funct7, entry in RTL_SEMANTICS.items()}
    return result


@router.get("/formal/theorems")
async def get_formal_theorems() -> Dict[str, Any]:
    """Run the executable exact checks (the path is kept for compatibility).

    Sheaf coboundary criterion, cycle-sum obstruction, braid relations and Reed-Solomon repair are
    computed at request time with exact arithmetic on finite instances. The Lean source
    formal/lean4/ChronusAlHaras.lean is a specification that is not machine-checked in CI.
    """
    return FormalTopologicalProofVerifier.verify_all_theorems()


# ------------------------------------------------------------------------------
# 5 FUTURE APPLICATION PRODUCTION REST ENDPOINTS
# ------------------------------------------------------------------------------


class SheafTurnRequest(BaseModel):
    agent_states: Dict[str, List[Numeric]] = Field(
        default_factory=lambda: {node: [1, 0, 0, 1] for node in ("Planner", "Coder", "Executor", "Tool")},
        description="Context vector per agent (numbers or exact strings such as '1/3')",
    )
    stalk_dim: int = Field(default=4, ge=1, le=64)
    baselines: Optional[Dict[str, List[Numeric]]] = Field(
        default=None, description="Optional known-good vectors, tried first when repairing a located node"
    )


class OrbitalTransmitRequest(BaseModel):
    packet_payload: str = Field(default="REFERENCE_TELEMETRY_PACKET_001", max_length=MAX_PAYLOAD_CHARS)
    source_sat: str = Field(default="SAT_00", max_length=32)
    target_sat: str = Field(default="SAT_07", max_length=32)
    constellation_size: int = Field(default=16, ge=1, le=257)
    jammed_links: List[Tuple[str, str]] = Field(
        default_factory=list, description="Laser links to mark jammed (both directions) before sending"
    )


class ZKMLProveAndVerifyRequest(BaseModel):
    sensor_input: List[int] = Field(default_factory=lambda: [12, 24, 36, 48], max_length=4096)
    weights_commitment: str = Field(
        default="demo-weight-commitment",
        min_length=1,
        max_length=256,
        description="Arbitrary commitment string; the demo layer's parameters are derived from its SHA-256",
    )


class CBDCCrossBorderRequest(BaseModel):
    sender_bank: str = Field(default="CENTRAL_BANK_A")
    receiver_bank: str = Field(default="CENTRAL_BANK_B")
    amount_tokens: int = Field(default=10_000_000)
    simulate_double_spend: bool = Field(default=False)


class TISAExecuteRequest(BaseModel):
    funct7: int = Field(
        default=0x02,
        ge=0,
        le=0x7F,
        description=(
            "0x01 ADD, 0x02 MUL, 0x03 SHEAF_INSPECT, 0x04 DSW_HEAL (Reed-Solomon scrub of rd), "
            "0x05 STARK_EVAL, 0x06 RICCI_INSPECT (sign test of c0), 0x07 HODGE_PROJ, 0x08 ANOSOV_PURGE"
        ),
    )
    rs1: int = Field(default=1, ge=0, le=31)
    rs2: int = Field(default=2, ge=0, le=31)
    rd: int = Field(default=3, ge=0, le=31)
    rs1_val: Tuple[int, int, int, int] = Field(default=(1, 2, 0, 0))
    rs2_val: Tuple[int, int, int, int] = Field(default=(3, 1, 0, 0))
    upset_register: Optional[int] = Field(
        default=None,
        ge=1,
        le=31,
        description="Fault-injection drill: register whose stored bytes are corrupted after loading, without updating its parity",
    )
    upset_byte_positions: List[int] = Field(
        default_factory=list,
        max_length=16,
        description="Byte positions 0..15 of that register image to corrupt (XOR 0x5A)",
    )


@router.post("/applications/agentic-sheaf/verify-turn")
async def execute_agentic_sheaf_turn(
    req: SheafTurnRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Check one Planner -> Coder -> Executor -> Tool turn exactly; on disagreement locate and repair."""
    try:
        system = AgenticSheafImmuneSystem(AgentDAG.create_canonical_pipeline(), stalk_dim=req.stalk_dim)
        for node, vec in (req.baselines or {}).items():
            system.register_baseline_state(node, vec)
        states = {node: AgentState(context_vector=vec, agent_id=node) for node, vec in req.agent_states.items()}
        return system.verify_and_execute_turn(states).as_dict()
    except (SheafError, ValueError, TypeError) as exc:
        raise _unprocessable(exc)


@router.post("/applications/orbital-mesh/transmit")
async def transmit_orbital_telemetry(
    req: OrbitalTransmitRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Send one packet over the Paley-graph mesh; the status is computed from the routes actually available."""
    try:
        mesh = OrbitalSatelliteDefenseMesh(constellation_nodes=[f"SAT_{i:02d}" for i in range(req.constellation_size)])
        hops = mesh.expander_graph.hops
        for a, b in req.jammed_links:
            if (a, b) not in hops:
                raise ValueError(f"no laser link between {a} and {b}")
            hops[(a, b)].jammed = True
            hops[(b, a)].jammed = True
        packet = req.packet_payload.encode("utf-8")
        outcome = mesh.transmit_telemetry_packet(packet, source_sat=req.source_sat, target_sat=req.target_sat)
    except (ValueError, TypeError) as exc:
        raise _unprocessable(exc)
    graph = mesh.expander_graph
    return {
        "status": outcome.value,
        "spectral_gap": graph.spectral_gap,
        "degree": graph.degree,
        "source_sat": req.source_sat,
        "target_sat": req.target_sat,
        "packet_len": len(packet),
        "transmission": mesh.last_transmission,
        "mesh": link_summary(mesh),
    }


@router.post("/applications/zk-neural/prove-and-verify")
async def execute_zk_neural_prove_and_verify(
    req: ZKMLProveAndVerifyRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Run the demo layer, build its F_257 trace receipt and check it by exact recomputation."""
    try:
        engine = LineRateVerifiableNeuralCompute(model_weights_commitment=req.weights_commitment)
        y_inf, proof = engine.execute_and_prove_inference(req.sensor_input)
    except (TypeError, ValueError) as exc:
        raise _unprocessable(exc)
    return {
        "inference_output": y_inf,
        "proof_receipt": proof,
        "verified": proof["verified"],
        "proof_type": proof["proof_type"],
        "challenge_z": proof["challenge_z"],
        "properties": proof["properties"],
    }


@router.post("/applications/cbdc-settlement/process")
async def process_cbdc_settlement(
    req: CBDCCrossBorderRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Check one settlement instruction with the exact boundary operator (in-memory model)."""
    nodes = [bank.value for bank in SovereignCentralBank]
    engine = SovereignCBDCSettlementEngine(central_bank_nodes=nodes)

    try:
        receipt = engine.process_cross_border_settlement(
            sender_bank=req.sender_bank,
            receiver_bank=req.receiver_bank,
            amount_tokens=req.amount_tokens,
            simulate_double_spend=req.simulate_double_spend,
        )
        return {
            "status": receipt.status,
            "settlement_id": receipt.settlement_id,
            "sender_bank": receipt.sender_bank,
            "receiver_bank": receipt.receiver_bank,
            "amount_tokens": receipt.amount_tokens,
            "boundary_defect": receipt.boundary_defect,
            "hecke_eigenvalue_ap": receipt.hecke_eigenvalue_ap,
            "weil_bound": receipt.weil_bound,
            "receipt_digest": receipt.receipt_digest,
        }
    except SovereignSettlementRejection as e:
        return {"status": "SETTLEMENT_REJECTED", **e.to_dict()}


@router.post("/applications/t-isa/execute")
async def execute_t_isa_microcode(
    req: TISAExecuteRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Execute one instruction on the T-ISA software model (no hardware is involved)."""
    regs = CoprocessorRegisters(32)
    bus = MemoryBus()
    try:
        regs.write_128bit(req.rs1, req.rs1_val)
        regs.write_128bit(req.rs2, req.rs2_val)
        if req.upset_register is not None:
            regs.inject_upset(req.upset_register, req.upset_byte_positions)
        rocc_inst = RoCCInstruction(funct7=req.funct7, rs1=req.rs1, rs2=req.rs2, rd=req.rd)
        execution = execute_t_isa_instruction(rocc_inst, regs, bus)
    except HardwareFault as exc:
        execution = {"status": "TRAPPED", "fault": exc.code, "error": str(exc), "details": exc.details}
    except (IndexError, TypeError, ValueError) as exc:
        raise _unprocessable(exc)
    rd_status = regs.get_status(req.rd)
    return {
        "execution": execution,
        "rd": req.rd,
        "rd_val": regs.read_128bit(req.rd),
        "rd_status": rd_status,
        "rd_status_label": _TISA_STATUS_LABELS.get(rd_status, "UNKNOWN"),
        "memory_egress_blocked": bus.is_egress_blocked(),
        "implementation": _TISA_MODEL_NOTE,
    }


# ------------------------------------------------------------------------------
# LEGACY "MILLENNIUM" PATHS: EXACT GRAPH AND ARITHMETIC CHECKS
# ------------------------------------------------------------------------------
# Path names are kept for existing clients. Each endpoint returns what
# chronus.security.al_haras.millennium_security / millennium_unification compute;
# routes with nothing to compute answer 501 with a NOT_IMPLEMENTED report. No
# Millennium Prize Problem is addressed by any of them.

MAX_MILLENNIUM_EDGES = 512
MAX_MILLENNIUM_SAMPLES = 4096


class GraphEdgeInput(BaseModel):
    source: str = Field(min_length=1, max_length=256)
    target: str = Field(min_length=1, max_length=256)
    traffic_weight: Numeric = Field(default=1, description="Positive weight (number or exact string such as '3/2')")


class RicciSurgeryRequest(BaseModel):
    edges: List[GraphEdgeInput] = Field(
        default_factory=lambda: [
            GraphEdgeInput(source=a, target=b)
            for a, b in (("a1", "a2"), ("a2", "a3"), ("a3", "a1"), ("b1", "b2"), ("b2", "b3"), ("b3", "b1"), ("a1", "b1"))
        ],
        max_length=MAX_MILLENNIUM_EDGES,
        description="Undirected edges; repeated pairs are merged by adding their weights",
    )
    curvature_threshold: Numeric = Field(default="-2/5", description="Edges with curvature strictly below this are removed")
    idleness: Numeric = Field(default=0, description="Random-walk idleness alpha, 0 <= alpha < 1")


class HodgeProjectRequest(BaseModel):
    bus_trace: List[Numeric] = Field(
        default_factory=lambda: [1.2, 3.4, 1.1, 8.9, 1.3, 3.5, 1.2, 8.8],
        max_length=MAX_MILLENNIUM_SAMPLES,
        description="Samples (numbers or exact strings), read as an edge signal on the cycle graph C_n",
    )


class UltrametricSandboxRequest(BaseModel):
    enclave_a: str = Field(default="enclave_a", min_length=1, max_length=256)
    enclave_b: str = Field(default="enclave_b", min_length=1, max_length=256)
    base_address_a: int = Field(default=0x1000, ge=0, lt=2**64)
    base_address_b: int = Field(default=0x5000, ge=0, lt=2**64)
    ball_exponent_a: int = Field(default=1, ge=1, le=64, description="Enclave a is the residue class of base_address_a mod p^k")
    ball_exponent_b: int = Field(default=1, ge=1, le=64, description="Enclave b is the residue class of base_address_b mod p^k")
    prime_p: int = Field(default=257, ge=2, le=65537, description="Must be prime")


class AnosovPurgeRequest(BaseModel):
    secret_hex: str = Field(
        default="414c5f48415241535f534f5645524549474e5f4b4559",
        max_length=2 * MAX_PAYLOAD_CHARS,
        description="Hex bytes copied into a server-side buffer that is then zeroised and read back",
    )


class PicardLefschetzFilterRequest(BaseModel):
    samples: List[Tuple[Numeric, Numeric]] = Field(
        default_factory=lambda: [(1.0, 0.5), (0.8, -0.3), (-0.4, 0.9)],
        max_length=MAX_MILLENNIUM_SAMPLES,
    )
    jamming_phase_intensity: Numeric = Field(default=2.5, description="Accepted for compatibility; not used")


@router.post("/millennium/ricci-surgery")
async def execute_ricci_surgery(
    req: RicciSurgeryRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Exact Ollivier-Ricci curvature of every edge, then removal of the edges below the threshold.

    A threshold rule on a graph statistic; it does not identify malicious traffic.
    """
    try:
        decloaker = RicciCurvatureDeCloaker(curvature_threshold=req.curvature_threshold, idleness=req.idleness)
        for edge in req.edges:
            decloaker.add_edge(edge.source, edge.target, edge.traffic_weight)
        return decloaker.execute_perelman_surgery()
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise _unprocessable(exc)


@router.post("/millennium/hodge-project")
async def execute_hodge_projection(
    req: HodgeProjectRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Exact Hodge decomposition of a trace on the cycle graph C_n: trace minus its mean, plus the mean.

    It does not detect, bound or remove side channels.
    """
    try:
        return HodgeCovertChannelFilter.sanitize_side_channels(req.bus_trace)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise _unprocessable(exc)


@router.post("/millennium/ultrametric-sandbox")
async def verify_ultrametric_sandbox(
    req: UltrametricSandboxRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Decide exactly whether two p-adic balls of integer addresses intersect.

    Arithmetic of residue classes only; not a memory-isolation control.
    """
    if req.enclave_a == req.enclave_b:
        raise _unprocessable(ValueError("enclave_a and enclave_b must be different names"))
    try:
        sandbox = UltrametricMemorySandbox(prime_p=req.prime_p)
        sandbox.register_enclave(req.enclave_a, req.base_address_a, req.ball_exponent_a)
        sandbox.register_enclave(req.enclave_b, req.base_address_b, req.ball_exponent_b)
        return sandbox.verify_non_overlapping_isolation(req.enclave_a, req.enclave_b)
    except (ValueError, TypeError) as exc:
        raise _unprocessable(exc)


@router.post("/millennium/anosov-purge")
async def execute_anosov_purge(
    req: AnosovPurgeRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> Dict[str, Any]:
    """Copy the hex bytes into a server-side bytearray, zeroise it in place and verify by read-back.

    Only that buffer is zeroised; the request body and any other copies are not erased.
    """
    try:
        buffer = bytearray.fromhex(req.secret_hex)
    except ValueError as exc:
        raise _unprocessable(exc)
    return AnosovColdBootScrambler.emergency_ram_purge(buffer)


@router.post("/millennium/picard-lefschetz-filter")
async def execute_picard_lefschetz_filter(
    req: PicardLefschetzFilterRequest, tenant_id: Optional[str] = Depends(get_current_tenant)
) -> JSONResponse:
    """Not implemented: validates the samples and answers 501 with the NOT_IMPLEMENTED report."""
    try:
        result = PicardLefschetzAntiJammingFilter.filter_jammed_waveform(
            req.samples, jamming_phase_intensity=req.jamming_phase_intensity
        )
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise _unprocessable(exc)
    return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content=result)


@router.get("/millennium/unification")
async def get_grand_millennium_unification() -> JSONResponse:
    """Not implemented: there is no Millennium Prize Problem unification to verify.

    Answers 501 with the NOT_IMPLEMENTED report and the results of exact AL HARAS self-checks.
    """
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content=GrandMillenniumUnificationNexus.verify_grand_millennium_unification(),
    )
