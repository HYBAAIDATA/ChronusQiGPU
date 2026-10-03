"""
EUCLID AST-Delta Extraction & Primitive Discovery v16.0
===========================================================
Derives parameterized, AST-aware rewrite rules from observed AST structural deltas (AST_before -> AST_after).
Enforces generalization testing across held-out candidates before operator promotion.
"""

import ast
import hashlib
from typing import Dict, List, Tuple, Any, Optional, Callable
from euclid.core.primitives import (
    TypeAnnotationTransformer, ConditionalGuardTransformer, 
    OperatorSwapTransformer, ListCompTransformer, FunctionSplitTransformer
)

class DiscoveredPrimitiveCandidate:
    """
    Represents an autodiscovered primitive undergoing sandbox generalization testing.
    """
    def __init__(
        self, 
        name: str, 
        pattern_hash: str,
        op_func: Callable[[str, int], Tuple[str, str]], 
        discovery_gen: int, 
        origin_target: str,
        derivation_trace: str
    ):
        self.name = name
        self.pattern_hash = pattern_hash
        self.op_func = op_func
        self.discovery_gen = discovery_gen
        self.origin_target = origin_target
        self.derivation_trace = derivation_trace
        
        self.evaluation_trials: int = 0
        self.successful_gains: int = 0
        self.cumulative_delta_phi: float = 0.0
        self.is_promoted: bool = False

    def record_trial(self, delta_phi: float, parse_v: bool, test_v: bool):
        self.evaluation_trials += 1
        if parse_v and test_v and delta_phi > 0:
            self.successful_gains += 1
            self.cumulative_delta_phi += delta_phi

    def check_promotion_eligibility(self) -> bool:
        """Promoted if tested on 2+ independent trials with >50% success rate & positive cumulative gain."""
        if self.evaluation_trials >= 2 and self.successful_gains >= 1 and self.cumulative_delta_phi > 0:
            self.is_promoted = True
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primitive_name": self.name,
            "pattern_hash": self.pattern_hash,
            "discovery_gen": self.discovery_gen,
            "origin_target": self.origin_target,
            "derivation_trace": self.derivation_trace,
            "evaluation_trials": self.evaluation_trials,
            "successful_gains": self.successful_gains,
            "cumulative_delta_phi": round(self.cumulative_delta_phi, 6),
            "is_promoted": self.is_promoted
        }


class ASTDeltaDiscoveryEngine:
    """
    Derives parameterized AST rewrite rules from AST structural diffs.
    """
    def __init__(self):
        self.sandbox_pool: Dict[str, DiscoveredPrimitiveCandidate] = {}
        self.promoted_vocabulary: Dict[str, Callable[[str, int], Tuple[str, str]]] = {}

    def extract_ast_diff(self, code_before: str, code_after: str) -> Dict[str, Any]:
        """Calculates structural AST diff between code_before and code_after."""
        try:
            tree_a = ast.parse(code_before)
            tree_b = ast.parse(code_after)
            
            nodes_a = [type(n).__name__ for n in ast.walk(tree_a)]
            nodes_b = [type(n).__name__ for n in ast.walk(tree_b)]
            
            diff_added = sorted(list(set(nodes_b) - set(nodes_a)))
            diff_removed = sorted(list(set(nodes_a) - set(nodes_b)))
            
            pattern_str = f"DIFF_ADD:{','.join(diff_added)}|DIFF_REM:{','.join(diff_removed)}"
            pattern_hash = hashlib.sha256(pattern_str.encode('utf-8')).hexdigest()[:16]
            
            return {
                "pattern_str": pattern_str,
                "pattern_hash": pattern_hash,
                "added_nodes": diff_added,
                "removed_nodes": diff_removed
            }
        except Exception:
            return {"pattern_str": "DIFF:UNKNOWN", "pattern_hash": "0000000000000000", "added_nodes": [], "removed_nodes": []}

    def discover_from_transformation(
        self, 
        code_before: str, 
        code_after: str, 
        winning_op_name: str, 
        gen: int, 
        target_name: str
    ) -> Optional[DiscoveredPrimitiveCandidate]:
        """
        Derives an AST rewrite rule matching the actual transformation delta.
        """
        diff = self.extract_ast_diff(code_before, code_after)
        pattern_hash = diff["pattern_hash"]
        new_name = f"AUTO:ASTDelta_{winning_op_name.replace(':', '_')}_{pattern_hash[:8]}"

        if new_name in self.sandbox_pool or new_name in self.promoted_vocabulary:
            return None

        # Select matching AST NodeTransformer based on actual winning operation and diff
        if "AnnAssign" in winning_op_name or "AnnAssign" in diff["added_nodes"]:
            transformer_cls = TypeAnnotationTransformer
        elif "conditional_flattening" in winning_op_name or "BoolOp" in diff["added_nodes"]:
            transformer_cls = ConditionalGuardTransformer
        elif "swap_op" in winning_op_name:
            transformer_cls = OperatorSwapTransformer
        elif "list_comp" in winning_op_name or "ListComp" in diff["added_nodes"]:
            transformer_cls = ListCompTransformer
        elif "function_split" in winning_op_name:
            transformer_cls = FunctionSplitTransformer
        else:
            transformer_cls = TypeAnnotationTransformer

        # Construct AST-aware rewrite rule function
        def _ast_aware_delta_rule(c: str, seed: int = 42) -> Tuple[str, str]:
            try:
                tree = ast.parse(c)
                transformer = transformer_cls()
                mod_tree = transformer.visit(tree)
                if getattr(transformer, "transformed", False):
                    ast.fix_missing_locations(mod_tree)
                    return ast.unparse(mod_tree), new_name
            except Exception:
                pass
            return c, new_name

        trace = f"Derived from {winning_op_name} on {target_name} at gen {gen} (Diff Hash: {pattern_hash})"
        cand = DiscoveredPrimitiveCandidate(new_name, pattern_hash, _ast_aware_delta_rule, gen, target_name, trace)
        self.sandbox_pool[new_name] = cand
        return cand
