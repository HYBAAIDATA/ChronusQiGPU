"""
AL HARAS — T-ISA: software model of a proposed RISC-V coprocessor extension
===========================================================================
"Speak friend and enter or you shall not pass." (motto from the product notes)

This module is a Python model. Nothing in it runs on, or was measured on,
hardware. The companion RTL sketch, hardware/rtl/t_isa_coprocessor.sv, has not
been simulated or synthesised in CI; ``RTL_SEMANTICS`` records, per operation,
whether that RTL implements the same function as this model.

Architectural state
-------------------
32 registers T0..T31. Each holds an element c0 + c1*z + c2*z^2 + c3*z^3 of
Z[zeta_5] with four signed 32-bit coefficients (a 16-byte register image). T0
reads as zero and ignores writes. Every architectural write also stores
Reed-Solomon parity of the register image (RS(24, 16) over GF(257), see
``reed_solomon.protect``), which T_DSW_HEAL uses. A status slot per register
records the outcome of the last check that named it as ``rd``. A model egress
gate (``MemoryBus``) is closed when a check traps; the RTL has no memory
interface, so the gate exists only in this model.

Operations (RISC-V custom-0 opcode 0x0B; funct7 selects the operation)
---------------------------------------------------------------------
0x01 T_CYCLO_ADD      rd <- rs1 + rs2, coefficient-wise.
0x02 T_CYCLO_MUL      rd <- rs1 * rs2 in Z[x]/(x^4 + x^3 + x^2 + x + 1).
0x03 T_SHEAF_INSPECT  coboundary of the constant sheaf on the edge rs1 -> rs2,
                      computed with sheaf.GraphSheaf. A non-zero coboundary
                      traps (TopologicalSheafFault) and closes the egress gate.
0x04 T_DSW_HEAL       scrub of register rd: Reed-Solomon decoding of its image
                      against the stored parity (reed_solomon.heal) corrects up
                      to 4 corrupted bytes in place and traps (RegisterECCFault)
                      when the image cannot be repaired. "DSW instanton" is the
                      notes' metaphor; the mechanism is error correction, and it
                      repairs storage corruption only: a register that was
                      written with a different value is left as written.
0x05 T_STARK_EVAL     one evaluation of a quotient identity over F_257:
                      rs1 = (P(z), Q(z), z, n) holds iff P(z) = Q(z) (z^n - 1);
                      rd <- (1, 0, 0, 0) if it holds, else 0. A single point
                      check is not a proof (see zk_neural.py).
0x06 T_RICCI_INSPECT  sign test: rd <- (1, 0, 0, 0) if c0 >= 0, else 0, and a
                      trap (RicciCurvatureNeckFault) when c0 < 0. The notes call
                      this a Ricci-curvature indicator; no curvature is computed.
0x07 T_HODGE_PROJ     coordinate projection (c0, c1, c2, c3) -> (c0, c1, 0, 0).
0x08 T_ANOSOV_PURGE   Arnold cat map (x, y) -> (2x + y, x + y) mod 257 on the
                      pairs (c0, c1) and (c2, c3). The map is invertible, so it
                      scrambles but does not erase: the input mod 257 can be
                      recovered.
Model-only operations without an RTL datapath: T_LOAD_CYCLO (the host writes an
immediate), T_STORE_CYCLO (the host reads a register) and T_NOP.

Arithmetic and cycle counts
---------------------------
ADD and MUL are computed exactly over Z and then reduced to signed 32-bit two's
complement, as the RTL datapath does; ``overflow`` reports whether that
reduction changed the exact value. ``model_cycles`` is not a measurement: it is
1 when the RTL implements the same function (its single registered stage
answers one clock edge after accepting a command) and None otherwise. No timing
closure or clock frequency has been established for the RTL.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chronus.security.al_haras import reed_solomon
from chronus.security.al_haras.cyclotomic import CyclotomicZ5
from chronus.security.al_haras.sheaf import GraphSheaf

Coeffs = Tuple[int, int, int, int]


class TISAOpcode(str, Enum):
    T_NOP = "T_NOP"
    T_LOAD_CYCLO = "T_LOAD_CYCLO"
    T_STORE_CYCLO = "T_STORE_CYCLO"
    T_CYCLO_ADD = "T_CYCLO_ADD"
    T_CYCLO_MUL = "T_CYCLO_MUL"
    T_SHEAF_INSPECT = "T_SHEAF_INSPECT"
    T_DSW_HEAL = "T_DSW_HEAL"
    T_STARK_EVAL = "T_STARK_EVAL"
    T_RICCI_INSPECT = "T_RICCI_INSPECT"
    T_HODGE_PROJ = "T_HODGE_PROJ"
    T_ANOSOV_PURGE = "T_ANOSOV_PURGE"


CUSTOM_0_OPCODE = 0x0B  # 7'b0001011, RISC-V custom-0

FUNCT7_MAP = {
    TISAOpcode.T_CYCLO_ADD: 0x01,
    TISAOpcode.T_CYCLO_MUL: 0x02,
    TISAOpcode.T_SHEAF_INSPECT: 0x03,
    TISAOpcode.T_DSW_HEAL: 0x04,
    TISAOpcode.T_STARK_EVAL: 0x05,
    TISAOpcode.T_RICCI_INSPECT: 0x06,
    TISAOpcode.T_HODGE_PROJ: 0x07,
    TISAOpcode.T_ANOSOV_PURGE: 0x08,
    TISAOpcode.T_LOAD_CYCLO: 0x09,
    TISAOpcode.T_STORE_CYCLO: 0x0A,
    TISAOpcode.T_NOP: 0x00,
}
REV_FUNCT7_MAP = {v: k for k, v in FUNCT7_MAP.items()}

NUM_REGISTERS = 32
FIELD_P = 257
WORD_MIN = -(1 << 31)
WORD_MAX = (1 << 31) - 1
REGISTER_IMAGE_BYTES = 16
ECC_N = 24
ECC_K = 16
ECC_CORRECTABLE_BYTES = (ECC_N - ECC_K) // 2

# Status slot values written by the checking instructions (0x03, 0x05, 0x06) and by
# an uncorrectable T_DSW_HEAL. A slot that no check has written reads STATUS_UNCHECKED.
STATUS_UNCHECKED = 0x00
STATUS_HARMONIC_CONSENSUS = 0x01  # the last check written to this slot passed
STATUS_FAULT = 0x02  # the last check written to this slot failed

# Registered stages between command acceptance and resp_valid in the RTL sketch.
RTL_RESPONSE_STAGES = 1

# What hardware/rtl/t_isa_coprocessor.sv does for each funct7, compared with this model.
RTL_SEMANTICS: Dict[int, Dict[str, Any]] = {
    0x01: {"matches_model": True, "rtl": "coefficient-wise add, 32-bit wrap"},
    0x02: {"matches_model": True, "rtl": "product mod Phi_5(x), 32-bit wrap"},
    0x03: {"matches_model": True, "rtl": "exception 4'hE iff rs1 != rs2; response carries the squared residual mod 2^64"},
    0x04: {"matches_model": False, "rtl": "register move rd <= rs2; no parity and no error correction"},
    0x05: {"matches_model": False, "rtl": "unsupported; illegal-instruction trap 4\'h2, no evaluation"},
    0x06: {"matches_model": True, "rtl": "exception 4'hC iff a0 < 0; rd <= 1 or 0"},
    0x07: {"matches_model": True, "rtl": "rd <= (a0, a1, 0, 0)"},
    0x08: {"matches_model": False, "rtl": "cat map on the two low bytes of a0 only, results truncated to 8 bits"},
}


# ------------------------------------------------------------------------------
# Traps
# ------------------------------------------------------------------------------


class HardwareFault(Exception):
    """Trap raised by the T-ISA model (legacy name: no hardware is involved).

    ``code`` is a stable identifier that also prefixes the message; ``details``
    carries the computed values that caused the trap.
    """

    code = "T_ISA_FAULT"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, code: Optional[str] = None) -> None:
        if code is not None:
            self.code = code
        self.details: Dict[str, Any] = dict(details or {})
        super().__init__(f"{self.code}: {message}")


class TopologicalSheafFault(HardwareFault):
    """T_SHEAF_INSPECT computed a non-zero coboundary on the edge rs1 -> rs2.

    Also raised, with code ``EGRESS_BLOCKED``, by ``MemoryBus.write`` while the
    model egress gate is closed, for callers that catch this legacy class.
    """

    code = "SHEAF_NONZERO_COBOUNDARY"


class RicciCurvatureNeckFault(HardwareFault):
    """T_RICCI_INSPECT found c0 < 0 (a sign test; the name follows the notes)."""

    code = "C0_NEGATIVE"


class RegisterECCFault(HardwareFault):
    """T_DSW_HEAL could not repair a register image from its Reed-Solomon parity."""

    code = "ECC_UNCORRECTABLE"


# ------------------------------------------------------------------------------
# Register values, images and parity
# ------------------------------------------------------------------------------


def _check_value(value: Any) -> Coeffs:
    """Four integers that each fit a signed 32-bit register word."""
    coeffs = value.coeffs() if isinstance(value, CyclotomicZ5) else tuple(value)
    if len(coeffs) != 4:
        raise ValueError("a register value has exactly four coefficients")
    for c in coeffs:
        if isinstance(c, bool) or not isinstance(c, int):
            raise TypeError(f"register coefficients must be integers, got {type(c).__name__}")
        if not WORD_MIN <= c <= WORD_MAX:
            raise ValueError(f"coefficient {c} does not fit a signed 32-bit register word")
    return (coeffs[0], coeffs[1], coeffs[2], coeffs[3])


def to_word(value: int) -> int:
    """Signed 32-bit two's-complement reduction (what one RTL coefficient lane keeps)."""
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def _wrap(exact: Sequence[int]) -> Tuple[Coeffs, bool]:
    wrapped = (to_word(exact[0]), to_word(exact[1]), to_word(exact[2]), to_word(exact[3]))
    return wrapped, wrapped != tuple(exact)


def register_image(value: Any) -> bytes:
    """16-byte image of a register: c0..c3 as signed 32-bit big-endian words."""
    return b"".join(c.to_bytes(4, "big", signed=True) for c in _check_value(value))


def image_to_register(image: bytes) -> Coeffs:
    if len(image) != REGISTER_IMAGE_BYTES:
        raise ValueError("a register image has 16 bytes")
    c = [int.from_bytes(image[i:i + 4], "big", signed=True) for i in range(0, REGISTER_IMAGE_BYTES, 4)]
    return (c[0], c[1], c[2], c[3])


def protect_register(value: Any) -> Dict[str, Any]:
    """RS(24, 16) parity envelope over GF(257) for one register image."""
    return reed_solomon.protect(register_image(value), n=ECC_N, k=ECC_K)


def ecc_decode_register(value: Any, envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Decode a possibly corrupted register value against its parity envelope.

    ``ecc_result`` is CLEAN (image consistent with its parity), CORRECTED (up to
    ``ECC_CORRECTABLE_BYTES`` bytes located and repaired, SHA-256 of the repaired
    image equal to the protected one) or UNCORRECTABLE.
    """
    healed = reed_solomon.heal(register_image(value), envelope)
    repairable = bool(healed["integrity_verified"])
    positions = list(healed["corrected_data_positions"]) if repairable else []
    if not repairable:
        result = "UNCORRECTABLE"
    elif positions:
        result = "CORRECTED"
    else:
        result = "CLEAN"
    return {
        "ecc_result": result,
        "repairable": repairable,
        "value": image_to_register(healed["repaired"]) if repairable else None,
        "corrected_byte_positions": positions,
        "code": f"RS({envelope['n']}, {envelope['k']}) over GF(257)",
    }


def cyclo5_poly_mul_mod_phi5(
    t_src1: Tuple[int, int, int, int],
    t_src2: Tuple[int, int, int, int],
) -> Tuple[int, int, int, int]:
    """Exact product in Z[zeta_5] = Z[x]/(x^4 + x^3 + x^2 + x + 1), over Z (no wrap).

    With d_k = sum_{i+j=k} a_i b_j and x^4 = -1 - x - x^2 - x^3, x^5 = 1, x^6 = x:
    c0 = d0 + d5 - d4, c1 = d1 + d6 - d4, c2 = d2 - d4, c3 = d3 - d4.
    """
    d = [0] * 7
    for i in range(4):
        for j in range(4):
            d[i + j] += t_src1[i] * t_src2[j]
    return (d[0] + d[5] - d[4], d[1] + d[6] - d[4], d[2] - d[4], d[3] - d[4])


def norm_sq_stalk(stalk: Sequence[int]) -> int:
    """Squared Euclidean norm of a coefficient vector."""
    return sum(x * x for x in stalk)


def sheaf_edge_check(stalk_u: Any, stalk_v: Any) -> Dict[str, Any]:
    """Coboundary of the constant sheaf on the single edge u -> v (sheaf.GraphSheaf).

    (delta^0 s)_e = s_v - s_u, which vanishes exactly when the two stalks agree.
    """
    u, v = _check_value(stalk_u), _check_value(stalk_v)
    sheaf = GraphSheaf(["u", "v"], [("u", "v")], 4)
    delta = sheaf.coboundary(sheaf.section({"u": list(u), "v": list(v)}))[0]
    coboundary = [int(x) for x in delta]
    return {
        "coboundary": coboundary,
        "residual_norm_sq": norm_sq_stalk(coboundary),
        "consistent": not any(coboundary),
    }


def dsw_instanton_repair_alu(state: Any, envelope: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Reed-Solomon repair of one register value (legacy name).

    Decodes the register image against the RS(24, 16) parity in ``envelope``
    (from ``protect_register``) and returns the corrected value; raises
    RegisterECCFault when the image cannot be repaired.
    """
    decoded = ecc_decode_register(state, envelope)
    if not decoded["repairable"]:
        raise RegisterECCFault(
            "register image is not repairable from its parity",
            {"value": list(_check_value(state))},
        )
    return decoded["value"]


# ------------------------------------------------------------------------------
# Instruction formats
# ------------------------------------------------------------------------------


@dataclass
class TISAInstruction:
    """Program-level instruction; ``imm`` is used by T_LOAD_CYCLO only."""

    opcode: TISAOpcode
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    imm: Optional[Tuple[int, int, int, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _check_field(name: str, value: int, width: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << width):
        raise ValueError(f"{name}={value!r} does not fit a {width}-bit field")
    return value


def encode_t_isa_instruction(inst: "TISAInstruction") -> int:
    """32-bit RoCC word (custom-0, funct3 = 0). ``imm`` does not fit and is not encoded."""
    rd = _check_field("rd", inst.rd, 5)
    rs1 = _check_field("rs1", inst.rs1, 5)
    rs2 = _check_field("rs2", inst.rs2, 5)
    funct7 = FUNCT7_MAP[TISAOpcode(inst.opcode)]
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (0x0 << 12) | (rd << 7) | CUSTOM_0_OPCODE


def decode_t_isa_instruction(word: int) -> "TISAInstruction":
    """Decode a 32-bit RoCC word; unknown funct7 values are rejected (illegal instruction)."""
    opcode = word & 0x7F
    if opcode != CUSTOM_0_OPCODE:
        raise ValueError(f"Invalid opcode 0x{opcode:02x}; expected RISC-V Custom-0 (0x0b)")
    funct7 = (word >> 25) & 0x7F
    if funct7 not in REV_FUNCT7_MAP:
        raise ValueError(f"Illegal instruction: funct7 0x{funct7:02x} is not a T-ISA operation")
    return TISAInstruction(
        opcode=REV_FUNCT7_MAP[funct7],
        rd=(word >> 7) & 0x1F,
        rs1=(word >> 15) & 0x1F,
        rs2=(word >> 20) & 0x1F,
    )


@dataclass
class RoCCInstruction:
    """RISC-V RoCC instruction descriptor (funct7 selects the T-ISA operation)."""

    funct7: int
    rs1: int = 0
    rs2: int = 0
    rd: int = 0
    opcode: int = CUSTOM_0_OPCODE
    xd: bool = True
    xs1: bool = True
    xs2: bool = True

    def encode(self) -> int:
        funct7 = _check_field("funct7", self.funct7, 7)
        rs2 = _check_field("rs2", self.rs2, 5)
        rs1 = _check_field("rs1", self.rs1, 5)
        rd = _check_field("rd", self.rd, 5)
        opcode = _check_field("opcode", self.opcode, 7)
        return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (0x0 << 12) | (rd << 7) | opcode

    @classmethod
    def decode(cls, word: int) -> "RoCCInstruction":
        return cls(
            funct7=(word >> 25) & 0x7F,
            rs1=(word >> 15) & 0x1F,
            rs2=(word >> 20) & 0x1F,
            rd=(word >> 7) & 0x1F,
            opcode=word & 0x7F,
        )


# ------------------------------------------------------------------------------
# Register file and egress gate
# ------------------------------------------------------------------------------


class CoprocessorRegisters:
    """Register file of the model: four signed 32-bit coefficients per register.

    T0 reads as zero and ignores writes. ``write_128bit`` also stores the RS
    parity used by T_DSW_HEAL; ``inject_upset`` corrupts a stored image without
    touching its parity, for fault-injection drills.
    """

    def __init__(self, num_registers: int = NUM_REGISTERS) -> None:
        if isinstance(num_registers, bool) or not isinstance(num_registers, int) or not 1 <= num_registers <= NUM_REGISTERS:
            raise ValueError(f"the register file has between 1 and {NUM_REGISTERS} registers")
        self.num_registers = num_registers
        zero: Coeffs = (0, 0, 0, 0)
        zero_envelope = protect_register(zero)
        self.regs: List[Coeffs] = [zero] * num_registers
        self.ecc: List[Dict[str, Any]] = [zero_envelope] * num_registers
        self.status_reg: Dict[int, int] = {i: STATUS_UNCHECKED for i in range(num_registers)}

    def _index(self, reg_idx: int) -> int:
        if isinstance(reg_idx, bool) or not isinstance(reg_idx, int) or not 0 <= reg_idx < self.num_registers:
            raise IndexError(f"Register T{reg_idx} out of bounds.")
        return reg_idx

    def read_128bit(self, reg_idx: int) -> Coeffs:
        return self.regs[self._index(reg_idx)]

    def write_128bit(self, reg_idx: int, val: Any) -> None:
        idx = self._index(reg_idx)
        coeffs = _check_value(val)
        if idx == 0:
            return  # T0 is hardwired to zero
        self.regs[idx] = coeffs
        self.ecc[idx] = protect_register(coeffs)

    def read_stalk(self, reg_idx: int) -> Coeffs:
        return self.read_128bit(reg_idx)

    def write_status(self, reg_idx: int, status_code: int) -> None:
        self.status_reg[self._index(reg_idx)] = status_code

    def get_status(self, reg_idx: int) -> int:
        return self.status_reg.get(reg_idx, STATUS_UNCHECKED)

    def inject_upset(self, reg_idx: int, byte_positions: Sequence[int]) -> Coeffs:
        """Fault-injection drill: XOR 0x5A into bytes of a stored image; parity is left unchanged."""
        idx = self._index(reg_idx)
        if idx == 0:
            raise ValueError("T0 is hardwired to zero and has no storage to corrupt")
        positions = sorted(set(byte_positions))
        if any(isinstance(p, bool) or not isinstance(p, int) or not 0 <= p < REGISTER_IMAGE_BYTES for p in positions):
            raise ValueError("byte positions must lie in 0..15")
        image = reed_solomon.inject_faults(register_image(self.regs[idx]), positions)
        self.regs[idx] = image_to_register(image)
        return self.regs[idx]

    def scrub(self, reg_idx: int) -> Dict[str, Any]:
        """Decode a register against its parity and write a repaired value back in place."""
        idx = self._index(reg_idx)
        decoded = ecc_decode_register(self.regs[idx], self.ecc[idx])
        if decoded["repairable"]:
            self.regs[idx] = decoded["value"]
        return decoded


class TopologicalRegisterFile(CoprocessorRegisters):
    """``CoprocessorRegisters`` with CyclotomicZ5 accessors (used by RISCVTopologicalCoprocessor)."""

    def read(self, reg_idx: int) -> CyclotomicZ5:
        return CyclotomicZ5(*self.read_128bit(reg_idx))

    def write(self, reg_idx: int, val: Any) -> None:
        self.write_128bit(reg_idx, val)

    @property
    def registers(self) -> List[CyclotomicZ5]:
        return [CyclotomicZ5(*value) for value in self.regs]


class MemoryBus:
    """Egress gate in front of memory writes (Python model only).

    The RTL sketch has no memory interface. The gate closes when a check traps
    and stays closed until the host calls ``allow_egress``.
    """

    def __init__(self) -> None:
        self.egress_blocked: bool = False
        self.block_reasons: List[str] = []
        self.writes: List[Tuple[int, bytes]] = []

    def block_egress(self, reason: str = "closed by the host") -> None:
        self.egress_blocked = True
        self.block_reasons.append(reason)

    def allow_egress(self) -> None:
        self.egress_blocked = False

    def is_egress_blocked(self) -> bool:
        return self.egress_blocked

    def write(self, address: int, data: bytes) -> bool:
        if self.egress_blocked:
            reason = self.block_reasons[-1] if self.block_reasons else "closed"
            raise TopologicalSheafFault(
                f"write to 0x{address:x} refused: egress gate closed ({reason})",
                {"address": address},
                code="EGRESS_BLOCKED",
            )
        self.writes.append((address, bytes(data)))
        return True


# ------------------------------------------------------------------------------
# Instruction semantics
# ------------------------------------------------------------------------------


def _rtl_fields(funct7: int) -> Dict[str, Any]:
    rtl = RTL_SEMANTICS.get(funct7)
    match = bool(rtl and rtl["matches_model"])
    return {"rtl_semantics_match": match, "model_cycles": RTL_RESPONSE_STAGES if match else None}


def _ok(name: str, funct7: int, rd: int, **fields: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"status": "OK", "opcode": name, "rd": rd}
    out.update(fields)
    out.update(_rtl_fields(funct7))
    return out


def _cat_map(x: int, y: int) -> Tuple[int, int]:
    return (2 * x + y) % FIELD_P, (x + y) % FIELD_P


def _cat_map_inverse(x: int, y: int) -> Tuple[int, int]:
    # [[2, 1], [1, 1]] has determinant 1; its inverse is [[1, -1], [-1, 2]].
    return (x - y) % FIELD_P, (2 * y - x) % FIELD_P


def execute_t_isa_instruction(
    rocc_inst: RoCCInstruction,
    registers: CoprocessorRegisters,
    memory_bus: MemoryBus,
) -> Dict[str, Any]:
    """Execute one RoCC instruction on the model (see the module docstring for each funct7)."""
    funct7 = rocc_inst.funct7
    rs1, rs2, rd = rocc_inst.rs1, rocc_inst.rs2, rocc_inst.rd

    if rocc_inst.opcode != CUSTOM_0_OPCODE or funct7 not in RTL_SEMANTICS:
        # The RTL raises exception 4'h2 for an unknown funct7 but does not decode the major opcode.
        rtl_match = rocc_inst.opcode == CUSTOM_0_OPCODE
        return {
            "status": "ILLEGAL_INSTRUCTION",
            "opcode": "ILLEGAL",
            "funct7": funct7,
            "major_opcode": rocc_inst.opcode,
            "rd": rd,
            "rtl_semantics_match": rtl_match,
            "model_cycles": RTL_RESPONSE_STAGES if rtl_match else None,
        }

    if funct7 == 0x01:  # T_CYCLO_ADD
        a, b = registers.read_128bit(rs1), registers.read_128bit(rs2)
        dst, overflow = _wrap([x + y for x, y in zip(a, b)])
        registers.write_128bit(rd, dst)
        return _ok("T_CYCLO_ADD", funct7, rd, dst=dst, overflow=overflow)

    if funct7 == 0x02:  # T_CYCLO_MUL
        a, b = registers.read_128bit(rs1), registers.read_128bit(rs2)
        dst, overflow = _wrap(cyclo5_poly_mul_mod_phi5(a, b))
        registers.write_128bit(rd, dst)
        return _ok("T_CYCLO_MUL", funct7, rd, dst=dst, overflow=overflow)

    if funct7 == 0x03:  # T_SHEAF_INSPECT
        check = sheaf_edge_check(registers.read_stalk(rs1), registers.read_stalk(rs2))
        details = {"rs1": rs1, "rs2": rs2, **check}
        if not check["consistent"]:
            registers.write_status(rd, STATUS_FAULT)
            memory_bus.block_egress(f"T_SHEAF_INSPECT T{rs1}->T{rs2}: non-zero coboundary")
            raise TopologicalSheafFault(
                f"coboundary on edge T{rs1}->T{rs2} is {check['coboundary']} (non-zero); egress gate closed",
                details,
            )
        registers.write_status(rd, STATUS_HARMONIC_CONSENSUS)
        return _ok(
            "T_SHEAF_INSPECT",
            funct7,
            rd,
            consistent=check["consistent"],
            coboundary=check["coboundary"],
            residual_norm_sq=check["residual_norm_sq"],
            status_code=registers.get_status(rd),
        )

    if funct7 == 0x04:  # T_DSW_HEAL: Reed-Solomon scrub of rd
        decoded = registers.scrub(rd)
        if not decoded["repairable"]:
            registers.write_status(rd, STATUS_FAULT)
            memory_bus.block_egress(f"T_DSW_HEAL T{rd}: image not repairable from its parity")
            raise RegisterECCFault(f"T{rd} image is not repairable from its RS parity; egress gate closed", {"rd": rd})
        return _ok(
            "T_DSW_HEAL",
            funct7,
            rd,
            ecc_result=decoded["ecc_result"],
            corrected_byte_positions=decoded["corrected_byte_positions"],
            repaired=registers.read_128bit(rd),
            code=decoded["code"],
        )

    if funct7 == 0x05:  # T_STARK_EVAL: P(z) == Q(z) * (z^n - 1) over F_257
        p_z, q_z, z, n = registers.read_128bit(rs1)
        if n < 0:
            raise ValueError("T_STARK_EVAL: the domain size n (coefficient c3) must be non-negative")
        vanishing = (pow(z, n, FIELD_P) - 1) % FIELD_P
        lhs = p_z % FIELD_P
        rhs = (q_z * vanishing) % FIELD_P
        holds = lhs == rhs
        registers.write_128bit(rd, (1 if holds else 0, 0, 0, 0))
        registers.write_status(rd, STATUS_HARMONIC_CONSENSUS if holds else STATUS_FAULT)
        return _ok(
            "T_STARK_EVAL",
            funct7,
            rd,
            identity_holds=holds,
            lhs=lhs,
            rhs=rhs,
            vanishing_value=vanishing,
            point=z % FIELD_P,
            domain_size=n,
        )

    if funct7 == 0x06:  # T_RICCI_INSPECT: sign test of c0
        c0 = registers.read_128bit(rs1)[0]
        nonnegative = c0 >= 0
        registers.write_128bit(rd, (1 if nonnegative else 0, 0, 0, 0))
        if not nonnegative:
            registers.write_status(rd, STATUS_FAULT)
            memory_bus.block_egress(f"T_RICCI_INSPECT T{rs1}: c0 < 0")
            raise RicciCurvatureNeckFault(f"c0 of T{rs1} is {c0} < 0; egress gate closed", {"rs1": rs1, "c0": c0})
        registers.write_status(rd, STATUS_HARMONIC_CONSENSUS)
        return _ok("T_RICCI_INSPECT", funct7, rd, c0=c0, c0_nonnegative=nonnegative)

    if funct7 == 0x07:  # T_HODGE_PROJ: coordinate projection onto (c0, c1)
        a = registers.read_128bit(rs1)
        dst = (a[0], a[1], 0, 0)
        registers.write_128bit(rd, dst)
        return _ok(
            "T_HODGE_PROJ",
            funct7,
            rd,
            dst=dst,
            removed_component=(0, 0, a[2], a[3]),
            removed_norm_sq=a[2] * a[2] + a[3] * a[3],
        )

    # funct7 == 0x08, T_ANOSOV_PURGE: invertible cat map mod 257 on (c0, c1) and (c2, c3)
    a = registers.read_128bit(rs1)
    reduced = tuple(c % FIELD_P for c in a)
    dst = _cat_map(reduced[0], reduced[1]) + _cat_map(reduced[2], reduced[3])
    recovered = _cat_map_inverse(dst[0], dst[1]) + _cat_map_inverse(dst[2], dst[3])
    registers.write_128bit(rd, dst)
    return _ok(
        "T_ANOSOV_PURGE",
        funct7,
        rd,
        dst=dst,
        input_mod_257=reduced,
        inverse_recovers_input=recovered == reduced,
    )


# ------------------------------------------------------------------------------
# Program-level model
# ------------------------------------------------------------------------------


class RISCVTopologicalCoprocessor:
    """Program-level wrapper around the T-ISA model (no hardware is involved).

    ``execute_program`` records every trap. After a trap it scrubs the source
    registers with their Reed-Solomon parity; if that corrected a storage upset
    it retries the instruction once. A trap caused by values that were written
    as they are (no upset) stays unresolved, and the egress gate stays closed
    until the host reopens it.
    """

    def __init__(self, core_id: int = 0) -> None:
        self.core_id = core_id
        self.reset()

    def reset(self) -> None:
        self.regfile = TopologicalRegisterFile(NUM_REGISTERS)
        self.bus = MemoryBus()
        self.instructions_executed = 0
        self.faults_trapped = 0
        self.model_cycles_total = 0
        self.instructions_without_rtl_cycle_model = 0

    def execute_instruction(self, inst: TISAInstruction) -> Dict[str, Any]:
        op = TISAOpcode(inst.opcode)
        if op == TISAOpcode.T_NOP:
            res: Dict[str, Any] = {"status": "OK", "opcode": op.value, "rtl_semantics_match": False, "model_cycles": None}
        elif op == TISAOpcode.T_LOAD_CYCLO:
            self.regfile.write_128bit(inst.rd, inst.imm if inst.imm is not None else (0, 0, 0, 0))
            value = self.regfile.read_128bit(inst.rd)
            res = {
                "status": "OK",
                "opcode": op.value,
                "rd": inst.rd,
                "value": value,
                "val": str(CyclotomicZ5(*value)),
                "rtl_semantics_match": False,
                "model_cycles": None,
            }
        elif op == TISAOpcode.T_STORE_CYCLO:
            value = self.regfile.read_128bit(inst.rs1)
            res = {
                "status": "OK",
                "opcode": op.value,
                "rs1": inst.rs1,
                "value": value,
                "rtl_semantics_match": False,
                "model_cycles": None,
            }
        else:
            rocc = RoCCInstruction(funct7=FUNCT7_MAP[op], rs1=inst.rs1, rs2=inst.rs2, rd=inst.rd)
            try:
                res = execute_t_isa_instruction(rocc, self.regfile, self.bus)
            except HardwareFault:
                self.faults_trapped += 1
                raise
            if "dst" in res:
                res["result"] = str(CyclotomicZ5(*res["dst"]))
        self.instructions_executed += 1
        if res["model_cycles"] is None:
            self.instructions_without_rtl_cycle_model += 1
        else:
            self.model_cycles_total += res["model_cycles"]
        return res

    def execute_program(self, program: List[TISAInstruction]) -> Dict[str, Any]:
        """Run a block of instructions, recording traps and ECC-based recoveries."""
        t0 = time.perf_counter_ns()
        cycles_before = self.model_cycles_total
        unmodelled_before = self.instructions_without_rtl_cycle_model
        faults: List[Dict[str, Any]] = []
        completed = 0

        for idx, inst in enumerate(program):
            try:
                self.execute_instruction(inst)
                completed += 1
                continue
            except HardwareFault as exc:
                record: Dict[str, Any] = {
                    "instruction_index": idx,
                    "opcode": TISAOpcode(inst.opcode).value,
                    "fault": exc.code,
                    "message": str(exc),
                    "ecc_scrub": [],
                    "recovered_by_ecc": False,
                }
            if record["fault"] != RegisterECCFault.code:
                corrected = False
                for reg in sorted({r for r in (inst.rs1, inst.rs2) if r != 0}):
                    scrub = self.regfile.scrub(reg)
                    record["ecc_scrub"].append(
                        {
                            "register": reg,
                            "ecc_result": scrub["ecc_result"],
                            "corrected_byte_positions": scrub["corrected_byte_positions"],
                        }
                    )
                    corrected = corrected or scrub["ecc_result"] == "CORRECTED"
                if corrected:
                    try:
                        self.execute_instruction(inst)
                        record["recovered_by_ecc"] = True
                        completed += 1
                    except HardwareFault as retry_exc:
                        record["retry_fault"] = str(retry_exc)
            faults.append(record)

        unresolved = sum(1 for f in faults if not f["recovered_by_ecc"])
        return {
            "core_id": self.core_id,
            "architecture": "RISC-V_TOPOLOGICAL_EXT_v1",
            "implementation": "Python software model; no hardware involved",
            "instructions_submitted": len(program),
            "instructions_completed": completed,
            "faults": faults,
            "faults_trapped": len(faults),
            "sheaf_faults_trapped": sum(1 for f in faults if f["fault"] == TopologicalSheafFault.code),
            "ecc_recoveries": sum(1 for f in faults if f["recovered_by_ecc"]),
            "unresolved_faults": unresolved,
            "egress_blocked": self.bus.is_egress_blocked(),
            "model_cycles_total": self.model_cycles_total - cycles_before,
            "instructions_without_rtl_cycle_model": self.instructions_without_rtl_cycle_model - unmodelled_before,
            "model_wall_time_ns": time.perf_counter_ns() - t0,
            "status": "COMPLETED" if unresolved == 0 else "COMPLETED_WITH_UNRESOLVED_FAULTS",
        }
