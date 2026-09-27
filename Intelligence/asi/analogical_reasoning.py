# pythagoras/asi/analogical_reasoning.py — NEW

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StructureMapping:
    source_domain: str
    target_domain: str
    entity_mappings: dict  # source entity -> target entity
    relation_mappings: dict  # source relation -> target relation
    mapping_score: float
    transferable_knowledge: list = field(default_factory=list)


class AnalogicalReasoningEngine:
    """Implements Gentner's Structure Mapping Engine for PYTHAGORAS.

    The system recognises structural similarities between codebases and
    transfers transformation patterns from one to another.
    """

    def __init__(self):
        self.known_structures: dict[str, dict] = {}  # domain -> structural representation

    def represent_structure(self, domain: str, ast_tree) -> dict:
        """Extract structural representation from an AST."""
        import ast

        structure = {
            "entities": [],  # function/class names
            "relations": [],  # calls/imports/inheritance
            "attributes": [],  # parameters/returns
        }
        for node in ast.walk(ast_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                structure["entities"].append(
                    {"name": node.name, "type": "function", "args": len(node.args.args)}
                )
            elif isinstance(node, ast.ClassDef):
                structure["entities"].append(
                    {
                        "name": node.name,
                        "type": "class",
                        "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                    }
                )
            elif isinstance(node, ast.Call):
                if hasattr(node.func, "id"):
                    structure["relations"].append({"type": "call", "target": node.func.id})
        self.known_structures[domain] = structure
        return structure

    def map_structures(self, source: str, target: str) -> Optional[StructureMapping]:
        """Find structural mapping between two domains (Gentner's SME)."""
        s = self.known_structures.get(source)
        t = self.known_structures.get(target)
        if not s or not t:
            return None

        # Match entities by structural role (not by name)
        entity_map = {}
        s_funcs = [e for e in s["entities"] if e["type"] == "function"]
        t_funcs = [e for e in t["entities"] if e["type"] == "function"]
        for sf, tf in zip(s_funcs, t_funcs):
            if sf["args"] == tf["args"]:  # structural match by argument count
                entity_map[sf["name"]] = tf["name"]

        # Match relations
        relation_map = {}
        s_calls = set(r["target"] for r in s["relations"] if r["type"] == "call")
        t_calls = set(r["target"] for r in t["relations"] if r["type"] == "call")
        for sc in s_calls:
            for tc in t_calls:
                if sc in entity_map.values() or tc in entity_map.values():
                    relation_map[sc] = tc

        # Compute mapping score
        score = len(entity_map) / max(len(s_funcs), 1)

        return StructureMapping(source, target, entity_map, relation_map, score)

    def transfer_knowledge(self, mapping: StructureMapping, source_primitives: list) -> list:
        """Transfer learned primitives from source to target domain using the mapping."""
        transferred = []
        for prim in source_primitives:
            # Map the primitive's target to the new domain
            mapped_name = mapping.entity_mappings.get(
                prim.get("target", ""), prim.get("target", "")
            )
            transferred.append(
                {**prim, "mapped_target": mapped_name, "source_domain": mapping.source_domain}
            )
        return transferred
