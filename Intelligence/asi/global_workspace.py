# pythagoras/asi/global_workspace.py — NEW

from dataclasses import dataclass
from typing import Any, Optional
import time


@dataclass
class WorkspaceMessage:
    source: str  # which subsystem sent this
    content: Any  # the information being broadcast
    priority: float  # salience/attention weight
    timestamp: float
    broadcast: bool = False  # was this broadcast to all modules?


class GlobalWorkspace:
    """Implements Baars' Global Workspace Theory for PYTHAGORAS.

    Specialised modules (CGP, surrogate, meta-controller, geometry, etc.)
    compete for access to the global workspace. The winning information
    is broadcast to all modules, enabling flexible, integrated responses.
    """

    def __init__(self):
        self.modules: dict[str, callable] = {}  # module_name -> handler
        self.workspace: list[WorkspaceMessage] = []
        self.broadcast_history: list[WorkspaceMessage] = []
        self.attention_threshold = 0.5

    def register_module(self, name: str, handler: callable):
        self.modules[name] = handler

    def submit(self, source: str, content: Any, priority: float = 0.5) -> WorkspaceMessage:
        """A module submits information to the workspace."""
        msg = WorkspaceMessage(source, content, priority, time.time())
        self.workspace.append(msg)
        return msg

    def broadcast_cycle(self) -> Optional[WorkspaceMessage]:
        """Select the most salient message and broadcast it to all modules."""
        if not self.workspace:
            return None

        # Competition: select highest priority message above threshold
        candidates = [m for m in self.workspace if m.priority >= self.attention_threshold]
        if not candidates:
            return None

        winner = max(candidates, key=lambda m: m.priority)
        winner.broadcast = True

        # Broadcast to all modules
        for name, handler in self.modules.items():
            if name != winner.source:  # don't send back to source
                handler(winner.content)

        self.broadcast_history.append(winner)
        self.workspace.remove(winner)
        return winner

    def get_conscious_access(self) -> list[str]:
        """Return the sequence of broadcast messages (conscious access log)."""
        return [f"{m.source}: {str(m.content)[:50]}" for m in self.broadcast_history]
