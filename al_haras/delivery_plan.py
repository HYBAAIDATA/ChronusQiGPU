"""Evidence-gated §63 sprint and release-train definitions."""
from dataclasses import dataclass
from typing import Callable,Mapping
@dataclass(frozen=True)
class Sprint:id:int;outcome:str;deliverables:tuple[str,...];gates:tuple[str,...];evidence:tuple[str,...];rollback:str
_OUTCOMES=("Baseline and scope lock","Canonical contracts","Assembly Compiler v0.1","PRIME-DB authoritative transaction core","Identity, policy, tenancy, keys","HYBA Evidence and compliance receipts","Multimodel query and semantic plane","Governed RAG and agent memory","Industry and Assurance Packs","Heterogeneous execution and movement truth","High availability, backup, cyber recovery","Regulated design-partner pilot","Production hardening and release candidate")
SPRINTS=tuple(Sprint(i,name,(f"sprint_{i}_deliverables",),(f"sprint_{i}_gate",),(f"sprint_{i}_evidence",),f"rollback_sprint_{i}") for i,name in enumerate(_OUTCOMES))
RELEASE_TRAINS={"R0":(0,1,2),"R1":(3,4,5),"R2":(6,7,8),"R3":(9,10),"R4":(11,12)}
class SprintGateFailed(RuntimeError):pass
def run_sprint(sprint:Sprint,actions:Mapping[str,Callable[[],object]],sign:Callable[[str,object],str]):
 outputs={}
 for name in sprint.deliverables:
  if name not in actions:raise SprintGateFailed(f"missing deliverable action: {name}")
  outputs[name]=actions[name]()
 for gate in sprint.gates:
  if gate not in actions or not actions[gate]():raise SprintGateFailed(f"sprint {sprint.id}: {gate}")
 evidence={name:sign(name,outputs) for name in sprint.evidence};return {"sprint":sprint.id,"outputs":outputs,"evidence":evidence,"rollback":sprint.rollback}
