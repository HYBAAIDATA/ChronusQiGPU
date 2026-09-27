# pythagoras/asi/hierarchical_planning.py — NEW

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskNode:
    name: str
    level: int  # 0 = primitive, higher = more abstract
    children: list = field(default_factory=list)
    parent: Optional[str] = None
    is_primitive: bool = False
    status: str = "pending"  # pending, in_progress, done, failed
    estimated_cost: float = 0.0


class HierarchicalPlanner:
    """Decomposes high-level goals into hierarchical action trees.

    Level 0: Primitive mutations (add annotation, rename variable)
    Level 1: Refactoring patterns (extract function, split class)
    Level 2: Architectural changes (introduce pattern, restructure module)
    Level 3: Strategic goals (improve maintainability, reduce complexity)
    """

    def __init__(self):
        self.task_tree: Optional[TaskNode] = None

    def decompose_goal(self, goal: str, current_state: dict) -> TaskNode:
        """Decompose a high-level goal into a hierarchical task tree."""
        root = TaskNode(name=goal, level=3, estimated_cost=1.0)

        if "maintainability" in goal:
            # Level 2: architectural changes
            for sub in ["reduce_complexity", "improve_naming", "add_documentation"]:
                node = TaskNode(name=sub, level=2, parent=goal, estimated_cost=0.3)
                root.children.append(node)

                # Level 1: refactoring patterns
                if sub == "reduce_complexity":
                    for ref in ["extract_function", "simplify_condition", "split_class"]:
                        ref_node = TaskNode(name=ref, level=1, parent=sub, estimated_cost=0.1)
                        node.children.append(ref_node)

                        # Level 0: primitive mutations
                        if ref == "extract_function":
                            ref_node.children.append(
                                TaskNode(
                                    "identify_block",
                                    level=0,
                                    parent=ref,
                                    is_primitive=True,
                                    estimated_cost=0.02,
                                )
                            )
                            ref_node.children.append(
                                TaskNode(
                                    "create_function",
                                    level=0,
                                    parent=ref,
                                    is_primitive=True,
                                    estimated_cost=0.02,
                                )
                            )
                            ref_node.children.append(
                                TaskNode(
                                    "replace_call",
                                    level=0,
                                    parent=ref,
                                    is_primitive=True,
                                    estimated_cost=0.02,
                                )
                            )

        self.task_tree = root
        return root

    def get_next_primitive(self) -> Optional[TaskNode]:
        """Get the next primitive action to execute (depth-first, left-to-right)."""
        if not self.task_tree:
            return None
        return self._find_next_pending_primitive(self.task_tree)

    def _find_next_pending_primitive(self, node: TaskNode) -> Optional[TaskNode]:
        if node.is_primitive and node.status == "pending":
            return node
        for child in node.children:
            if child.status != "done":
                result = self._find_next_pending_primitive(child)
                if result:
                    return result
        return None

    def mark_done(self, task_name: str):
        """Mark a task as done and update parent status."""
        self._mark_done_recursive(self.task_tree, task_name)

    def _mark_done_recursive(self, node: TaskNode, name: str) -> bool:
        if node.name == name:
            node.status = "done"
            return True
        for child in node.children:
            if self._mark_done_recursive(child, name):
                # Check if all children are done
                if all(c.status == "done" for c in node.children):
                    node.status = "done"
                return True
        return False
