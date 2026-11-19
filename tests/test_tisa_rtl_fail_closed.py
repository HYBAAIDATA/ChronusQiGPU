"""Regression: RTL STARK opcode must not manufacture a successful verification.

This is a source-contract test, not RTL simulation, synthesis or hardware evidence.
"""
from pathlib import Path
import re

from chronus.security.al_haras.hardware_t_isa import RTL_SEMANTICS
import pytest

pytestmark = pytest.mark.real


def test_unimplemented_stark_rtl_traps_instead_of_returning_pass():
    rtl_path = Path(__file__).resolve().parents[1] / "hardware/rtl/t_isa_coprocessor.sv"
    rtl = rtl_path.read_text(encoding="utf-8")
    opcode = re.search(r"OPC_STARK_EVAL:\s*begin(?P<body>.*?)\bend", rtl, re.DOTALL)
    assert opcode is not None
    body = opcode.group("body")
    assert re.search(r"resp_data\s*<=\s*'0\s*;", body)
    assert re.search(r"resp_exception\s*<=\s*1'b1\s*;", body)
    assert re.search(r"resp_exc_code\s*<=\s*4'h2\s*;", body)
    assert "32'h00000001" not in body
    assert RTL_SEMANTICS[0x05]["matches_model"] is False
    assert "unsupported" in RTL_SEMANTICS[0x05]["rtl"]
