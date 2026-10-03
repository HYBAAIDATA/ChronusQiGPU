"""
EUCLID Persistent Cross-Session Primitive Repository v16.0
===============================================================
Persists declarative primitive transformation schemas, pattern hashes, content signatures,
provenance, and validation history across process restarts and independent sessions.
Eliminates un-sandboxed exec() vulnerabilities by executing allowlisted AST NodeTransformers only.
"""

import os
import ast
import json
import hmac
import hashlib
import logging
from typing import Dict, List, Tuple, Any, Optional, Callable
from euclid.core.primitives import ASTPrimitives

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = "var/euclid/registry/primitive_repository.json"
DEFAULT_SECRET_KEY = b"EUCLID_CRYPTOGRAPHIC_REGISTRY_KEY_V16"

class PersistentPrimitiveRepository:
    """
    Persistent Primitive Repository.
    Serializes declarative AST transformation schemas and cryptographic signatures to disk.
    Executes allowlisted AST NodeTransformers on session reload without raw exec().
    """
    def __init__(self, storage_path: Optional[str] = None, secret_key: bytes = DEFAULT_SECRET_KEY):
        self.storage_path = storage_path or DEFAULT_REGISTRY_PATH
        self.secret_key = secret_key
        self.repository: Dict[str, Dict[str, Any]] = {}
        self.primitive_functions: Dict[str, Callable[[str, int], Tuple[str, str]]] = {}
        self.load_from_disk()

    def _compute_hmac_signature(self, name: str, pattern_hash: str, rule_type: str) -> str:
        msg = f"{name}:{pattern_hash}:{rule_type}".encode('utf-8')
        return hmac.new(self.secret_key, msg, hashlib.sha256).hexdigest()

    def register_primitive(
        self, 
        name: str, 
        op_func: Callable[[str, int], Tuple[str, str]], 
        rule_type: str,
        origin_target: str, 
        cum_gain: float,
        pattern_hash: Optional[str] = None
    ):
        p_hash = pattern_hash or hashlib.sha256(rule_type.encode('utf-8')).hexdigest()[:16]
        sig = self._compute_hmac_signature(name, p_hash, rule_type)
        
        self.repository[name] = {
            "primitive_id": name,
            "version": "16.0",
            "pattern_hash": p_hash,
            "rule_type": rule_type,
            "origin_target": origin_target,
            "cumulative_delta_phi": round(cum_gain, 6),
            "targets_reused_on": [origin_target],
            "hmac_signature": sig
        }
        self.primitive_functions[name] = op_func
        self.save_to_disk()

    def record_cross_file_reuse(self, name: str, target_name: str, delta_phi: float):
        if name in self.repository:
            if target_name not in self.repository[name]["targets_reused_on"]:
                self.repository[name]["targets_reused_on"].append(target_name)
            self.repository[name]["cumulative_delta_phi"] = round(
                self.repository[name]["cumulative_delta_phi"] + delta_phi, 6
            )
            self.save_to_disk()

    def get_all_primitives(self) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
        return [(name, func) for name, func in self.primitive_functions.items()]

    def save_to_disk(self):
        """Serializes registry to JSON file with explicit error logging."""
        if not self.storage_path:
            return
        try:
            abs_path = os.path.abspath(self.storage_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(self.repository, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save primitive repository to '{self.storage_path}': {str(e)}")

    def load_from_disk(self):
        """
        Loads registry and maps rule types to allowlisted AST primitives.
        Validates HMAC signatures and rejects unsigned or tampered entries.
        """
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            allowlisted_ops = dict(ASTPrimitives.get_all_operators())

            for name, meta in data.items():
                p_hash = meta.get("pattern_hash", "")
                rule_type = meta.get("rule_type", "ADD:AnnAssign")
                sig = meta.get("hmac_signature", "")

                # HMAC Signature Validation
                expected_sig = self._compute_hmac_signature(name, p_hash, rule_type)
                if not sig or not hmac.compare_digest(sig, expected_sig):
                    logger.warning(f"Signature mismatch for primitive '{name}'. Entry rejected for security.")
                    continue

                # Map rule_type to allowlisted AST operator function
                if rule_type in allowlisted_ops:
                    self.repository[name] = meta
                    self.primitive_functions[name] = allowlisted_ops[rule_type]
                else:
                    # Default to AnnAssign if unknown rule_type
                    self.repository[name] = meta
                    self.primitive_functions[name] = ASTPrimitives.apply_type_annotations

        except Exception as e:
            logger.error(f"Failed to load primitive repository from '{self.storage_path}': {str(e)}")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_repository_primitives": len(self.repository),
            "storage_path": self.storage_path,
            "primitives_detail": self.repository
        }

# Alias for backward compatibility
CrossFilePrimitiveRepository = PersistentPrimitiveRepository
