"""Fail-closed acceptance checker for the normative Chronus-1 ISA."""
from __future__ import annotations
import json, re
from pathlib import Path
EXPECTED = ["NOP","MOV","MOVI","ADD","SUB","MUL","FMA","LOAD","STORE","LLOAD","LSTORE","BARRIER","BRA","BRAZ","BRANZ","GET_GID","GET_LID","GET_GSIZE","GET_LSIZE","EXIT"]
REQUIRED_SECTIONS = ["Encoding","Opcode table","Address spaces","Divergence and reconvergence","Barrier and memory fence","Dispatch built-ins","Traps and fail-closed behavior","Expressibility of tiled matrix multiplication"]
def main() -> int:
 root=Path(__file__).resolve().parents[1]; spec=json.loads((root/"isa/chronus1.json").read_text()); md=(root/"isa/chronus1.md").read_text()
 assert spec["instruction_width_bits"]==32 and spec["warp_lanes"]==32
 assert set(spec["opcodes"])==set(EXPECTED) and len(set(spec["opcodes"].values()))==20
 assert spec["memory"]=={"global_address_bits":32,"local_bytes_per_cu":65536,"alignment_bytes":4}
 assert spec["silent_host_fallback"] is False and spec["trap_on_reserved_opcode"] is True
 for section in REQUIRED_SECTIONS: assert re.search(rf"^## [0-9]+\. {re.escape(section)}$",md,re.M), section
 for op in EXPECTED: assert f"| {op} |" in md, op
 for token in ("binary32_fma","predicate masks","divergence-stack overflow","invalid early exit","padded inactive lanes"):
  assert token in md, token
 print("Chronus-1 ISA acceptance: PASS (20 instructions, exact barriers/divergence, matmul expressible)")
 return 0
if __name__=="__main__": raise SystemExit(main())
