"""
V6.4 Engine: Cross-File Primitive Reuse & Transfer Learning
"""
import ast
import time
import json
import os
import hashlib
from typing import Dict, List, Tuple, Any, Optional, Callable
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core import sandbox
from pythagoras.core.primitives import ASTPrimitives, compose
from pythagoras.engine.v6_1_surrogate import NeuralSurrogateEvaluator
from pythagoras.engine.v6_2_geometry import CGPGeometryState
from pythagoras.engine.v6_3_primitive_discovery import DiscoveredPrimitiveCandidate, PrimitiveDiscoveryEngine

class CrossFilePrimitiveRepository:
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.repository: Dict[str, Dict[str, Any]] = {}
        self.primitive_functions: Dict[str, Callable[[str, int], Tuple[str, str]]] = {}
        self.cross_file_reuses: Dict[str, List[str]] = {}
        self.provenance_events: List[Dict[str, Any]] = []
        self.adaptive_state: Dict[str, Any] = {}
        self.last_save_error: Optional[str] = None
        self._load_from_storage()

    def _load_from_storage(self):
        """Restores persisted primitives from their recipes. Entries without a recipe
        (e.g. written by v12.0) keep their metadata but are not restored as operators."""
        if self.storage_path and os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                return
            self.repository = data.get("repository", {})
            self.cross_file_reuses = data.get("cross_file_reuses", {})
            self.provenance_events = data.get("provenance_events", [])
            self.adaptive_state = data.get("adaptive_state", {})
            for name, meta in self.repository.items():
                recipe = meta.get("recipe")
                if recipe:
                    try:
                        self.primitive_functions[name] = compose(recipe, name)
                        meta["restorable"] = True
                        continue
                    except ValueError:
                        pass
                meta["restorable"] = False

    def _save_to_storage(self):
        if self.storage_path:
            try:
                parent_dir = os.path.dirname(self.storage_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "repository": self.repository,
                        "cross_file_reuses": self.cross_file_reuses,
                        "provenance_events": self.provenance_events,
                        "adaptive_state": self.adaptive_state,
                    }, f, indent=2)
            except OSError as e:
                self.last_save_error = str(e)

    def register_promoted_primitive(self, name: str, op_func: Callable[[str, int], Tuple[str, str]], origin_target: str, cum_gain: float):
        if name not in self.repository:
            recipe = list(getattr(op_func, "recipe", []) or [])
            self.repository[name] = {
                "primitive_name": name,
                "origin_target": origin_target,
                "cumulative_delta_phi": round(cum_gain, 6),
                "targets_reused_on": [origin_target],
                "recipe": recipe,
                "restorable": bool(recipe),
            }
            self.primitive_functions[name] = op_func
            self.cross_file_reuses[name] = [origin_target]
            self._record_event("primitive_registered", name, origin_target, cum_gain, recipe)
            self._save_to_storage()

    def record_cross_file_use(self, name: str, target_name: str, delta_phi: float):
        if name in self.repository:
            if target_name not in self.repository[name]["targets_reused_on"]:
                self.repository[name]["targets_reused_on"].append(target_name)
            if target_name not in self.cross_file_reuses[name]:
                self.cross_file_reuses[name].append(target_name)
            self.repository[name]["cumulative_delta_phi"] = round(
                self.repository[name]["cumulative_delta_phi"] + delta_phi, 6
            )
            self._record_event("primitive_reused", name, target_name, delta_phi,
                               self.repository[name].get("recipe", []))
            self._save_to_storage()

    def _record_event(self, event_type: str, primitive: str, target: str,
                      delta_phi: float, recipe: List[str]) -> None:
        previous = self.provenance_events[-1]["event_hash"] if self.provenance_events else "GENESIS"
        payload = {
            "sequence": len(self.provenance_events) + 1,
            "event_type": event_type,
            "primitive": primitive,
            "target": target,
            "delta_phi": round(float(delta_phi), 6),
            "recipe": list(recipe),
            "previous_hash": previous,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload["event_hash"] = hashlib.sha256(encoded).hexdigest()
        self.provenance_events.append(payload)

    def save_adaptive_state(self, state: Dict[str, Any]) -> None:
        self.adaptive_state = state
        self._save_to_storage()

    def get_adaptive_state(self) -> Dict[str, Any]:
        return dict(self.adaptive_state)

    def get_all_transfer_primitives(self) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
        return [(name, func) for name, func in self.primitive_functions.items()]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_repository_primitives": len(self.repository),
            "primitives_detail": self.repository,
            "cross_file_reuse_counts": {k: len(v) for k, v in self.cross_file_reuses.items()},
            "provenance_event_count": len(self.provenance_events),
            "provenance_head": self.provenance_events[-1]["event_hash"] if self.provenance_events else None,
            "adaptive_state_persisted": bool(self.adaptive_state),
        }

class V64CrossFileReuseEngine:
    def __init__(self, repository: Optional[CrossFilePrimitiveRepository] = None, target_phi: float = 0.618033988749895, seed: int = 42):
        self.seed = seed
        self.calculator = PhiResonanceCalculator(target_phi)
        self.base_operators = ASTPrimitives.get_all_operators()
        self.surrogate = NeuralSurrogateEvaluator(learning_rate=0.05)
        self.discovery_engine = PrimitiveDiscoveryEngine()
        self.cross_file_repo = repository or CrossFilePrimitiveRepository()

    def verify_validity(self, code_str: str, external_test_runner: Optional[Callable[[str], bool]] = None) -> Tuple[bool, bool, bool]:
        """Delegates to the AL HARAS isolated validity gate (pythagoras.core.sandbox)."""
        return sandbox.verify_validity(code_str, external_test_runner)

    def run_optimization(
        self, 
        target_name: str, 
        initial_code: str, 
        max_generations: int = 20,
        external_test_runner: Optional[Callable[[str], bool]] = None
    ) -> Dict[str, Any]:
        current_code = initial_code
        current_score = self.calculator.compute_phi(current_code)
        initial_score = current_score

        geometry = CGPGeometryState(initial_n_cols=12, initial_levels_back=3, pop_size=10)
        accepted_steps = []
        discovery_events = []
        promoted_primitives_summary = []
        cross_file_reuses_triggered = []

        total_evals_attempted = 0
        total_evals_valid = 0

        transferred_primitives = self.cross_file_repo.get_all_transfer_primitives()
        for pname, pfunc in transferred_primitives:
            self.discovery_engine.promoted_vocabulary[pname] = pfunc

        for gen in range(1, max_generations + 1):
            features = self.calculator.extract_features(current_code)
            gen_start_score = current_score

            active_ops = list(self.base_operators)
            for pname, pfunc in self.discovery_engine.promoted_vocabulary.items():
                if (pname, pfunc) not in active_ops:
                    active_ops.append((pname, pfunc))

            for sname, scand in self.discovery_engine.sandbox_pool.items():
                if not scand.is_promoted and (sname, scand.op_func) not in active_ops:
                    active_ops.append((sname, scand.op_func))

            ranked_ops = []
            for op_name, op_func in active_ops:
                if self.surrogate.is_anti_primitive(op_name):
                    continue
                pred_gain = self.surrogate.predict_gain(features, op_name)
                ranked_ops.append((pred_gain, op_name, op_func))

            ranked_ops.sort(key=lambda x: x[0], reverse=True)
            valid_candidates = []

            for pred_gain, op_name, op_func in ranked_ops:
                total_evals_attempted += 1
                cand_code, _ = op_func(current_code, self.seed + gen)
                p_v, c_v, r_v = self.verify_validity(cand_code, external_test_runner)

                if p_v and c_v and r_v:
                    total_evals_valid += 1
                    cand_score = self.calculator.compute_phi(cand_code)
                    actual_delta = round(cand_score - current_score, 6)
                else:
                    cand_score = 0.1000
                    actual_delta = -0.5000

                if op_name in self.discovery_engine.sandbox_pool:
                    cand = self.discovery_engine.sandbox_pool[op_name]
                    cand.record_trial(actual_delta, p_v, r_v)
                    if cand.check_promotion_eligibility():
                        self.discovery_engine.promoted_vocabulary[op_name] = cand.op_func
                        self.cross_file_repo.register_promoted_primitive(
                            op_name, cand.op_func, target_name, cand.cumulative_delta_phi
                        )
                        promoted_primitives_summary.append({
                            "primitive_name": op_name,
                            "promotion_gen": gen,
                            "cumulative_delta_phi": round(cand.cumulative_delta_phi, 6)
                        })

                self.surrogate.update(features, op_name, actual_delta, p_v, r_v)

                if (cand_score > current_score) and p_v and c_v and r_v:
                    valid_candidates.append({
                        "candidate_code": cand_code,
                        "candidate_score": cand_score,
                        "delta_phi": actual_delta,
                        "op_name": op_name
                    })

            if valid_candidates:
                valid_candidates.sort(key=lambda x: x["candidate_score"], reverse=True)
                winner = valid_candidates[0]
                prev_code = current_code
                current_code = winner["candidate_code"]
                current_score = winner["candidate_score"]

                is_transferred_reuse = winner["op_name"] in self.cross_file_repo.repository
                if is_transferred_reuse:
                    self.cross_file_repo.record_cross_file_use(winner["op_name"], target_name, winner["delta_phi"])
                    cross_file_reuses_triggered.append({
                        "generation": gen,
                        "primitive_name": winner["op_name"],
                        "target_reused_on": target_name,
                        "delta_phi": winner["delta_phi"]
                    })

                accepted_steps.append({
                    "generation": gen,
                    "winning_operator": winner["op_name"],
                    "is_transferred_reuse": is_transferred_reuse,
                    "delta_phi": winner["delta_phi"],
                    "new_phi": current_score
                })

                disc = self.discovery_engine.discover_from_transformation(
                    prev_code, current_code, winner["op_name"], gen, target_name
                )
                if disc:
                    discovery_events.append({
                        "generation": gen,
                        "discovered_primitive": disc.name
                    })

            gen_velocity = current_score - gen_start_score
            geometry.adapt(gen_velocity)

        return {
            "target": target_name,
            "seed": self.seed,
            "initial_phi": initial_score,
            "final_phi": current_score,
            "total_delta_phi": round(current_score - initial_score, 6),
            "total_evals_attempted": total_evals_attempted,
            "total_evals_valid": total_evals_valid,
            "accepted_steps_count": len(accepted_steps),
            "discovery_events_count": len(discovery_events),
            "cross_file_reuses_count": len(cross_file_reuses_triggered),
            "final_code": current_code
        }
