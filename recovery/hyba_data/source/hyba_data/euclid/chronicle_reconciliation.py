"""Chronicle Reconciliation — DAG-based partition healing. 19 July 2026."""
import hashlib, time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

@dataclass
class ChronicleEvent:
    event_id: str = ""; predecessor_hash: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0; event_hash: str = ""
    def calculate_hash(self) -> str:
        d = f"{self.event_id}:{self.predecessor_hash}:{str(self.payload)}:{self.timestamp}"
        return hashlib.sha256(d.encode()).hexdigest()

@dataclass
class MergeChronicleEvent(ChronicleEvent):
    divergent_predecessor_hash: str = ""
    common_ancestor_hash: str = ""
    def calculate_hash(self) -> str:
        d = f"MERGE:{self.event_id}:{self.predecessor_hash}:{self.divergent_predecessor_hash}:{self.common_ancestor_hash}:{str(self.payload)}:{self.timestamp}"
        return hashlib.sha256(d.encode()).hexdigest()

class ReconcilableChronicle:
    def __init__(self):
        self.events: List[ChronicleEvent] = []
        self.event_map: Dict[str, ChronicleEvent] = {}
        self.event_indices: Dict[str, int] = {}

    def append_event(self, event: ChronicleEvent):
        if not event.event_hash: event.event_hash = event.calculate_hash()
        i = len(self.events); self.events.append(event)
        self.event_map[event.event_hash] = event; self.event_indices[event.event_id] = i

    def find_last_common_ancestor(self, remote: List[ChronicleEvent]) -> Optional[str]:
        lh = {e.event_hash for e in self.events}
        for rev in reversed(remote):
            if rev.event_hash in lh: return rev.event_hash
        return None

    def reconcile_diverged_branch(self, remote: List[ChronicleEvent], payload: Dict[str, Any]) -> Tuple[bool, str, Optional[MergeChronicleEvent]]:
        if not self.events or not remote: return (False, "Empty.", None)
        lca = self.find_last_common_ancestor(remote)
        if not lca: return (False, "No shared ancestor.", None)
        div: List[ChronicleEvent] = []; found = False
        for rev in remote:
            if found: div.append(rev)
            if rev.event_hash == lca: found = True
        exp = lca
        for rev in div:
            if rev.predecessor_hash != exp: return (False, f"Broken link {rev.event_id}.", None)
            if rev.event_hash != rev.calculate_hash(): return (False, f"Hash mismatch {rev.event_id}.", None)
            exp = rev.event_hash
        for rev in div:
            if rev.event_hash not in self.event_map: self.append_event(rev)
        ba = self.events[-1 - len(div)].event_hash if div else self.events[-1].event_hash
        bb = div[-1].event_hash if div else lca
        me = MergeChronicleEvent(event_id=f"merge_{int(time.time())}", predecessor_hash=ba, payload=payload, timestamp=time.time(), divergent_predecessor_hash=bb, common_ancestor_hash=lca)
        me.event_hash = me.calculate_hash(); self.append_event(me)
        return (True, "Chronicle merged via DAG.", me)
