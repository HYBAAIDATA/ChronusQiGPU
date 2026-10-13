from dataclasses import asdict,dataclass
from typing import Mapping,Any
from format.chronus1_executable import Executable,pack,unpack
from tools.asm import assemble_source
from .control_flow import construct,validate_reconvergence
from .geometry import choose_geometry
from .ir import ChronusIR
from .lowering import lower,memory_layout
from .regalloc import allocate
@dataclass(frozen=True)
class Compilation:
 ir:ChronusIR;assembly:str;container:bytes;geometry:object;allocation:object;memory:dict;control_flow:tuple
 def report(self):return {'schema':'chronus.compiler-report.v0.1','ir':self.ir.__dict__,'geometry':asdict(self.geometry),'allocation':asdict(self.allocation),'memory':self.memory,'control_flow':[asdict(b) for b in self.control_flow],'code_words':len(unpack(self.container).code)}
def compile_ir_to_asm(value:ChronusIR|Mapping[str,Any]):
 ir=value if isinstance(value,ChronusIR) else ChronusIR.from_dict(value);asm=lower(ir);validate_reconvergence(ir,asm);return asm
def compile_ir(value):
 ir=value if isinstance(value,ChronusIR) else ChronusIR.from_dict(value);asm=compile_ir_to_asm(ir);raw=unpack(assemble_source(asm));memory=memory_layout(ir);container=pack(Executable(raw.code,raw.entry,memory["required_bytes"],raw.flags,raw.symbols,raw.reconvergence,raw.major,raw.minor));return Compilation(ir,asm,container,choose_geometry(ir),allocate(ir),memory,construct(ir))
