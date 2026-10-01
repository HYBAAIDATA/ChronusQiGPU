"""Persistent cross-file primitive repository for production PYTHAGORAS evolution."""

import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from pythagoras.core.primitives import compose


class CrossFilePrimitiveRepository:
    """Persist promoted composite recipes, reuse evidence and adaptive state."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path
        self.repository: Dict[str, Dict[str, Any]] = {}
        self.primitive_functions: Dict[
            str, Callable[[str, int], Tuple[str, str]]
        ] = {}
        self.cross_file_reuses: Dict[str, List[str]] = {}
        self.provenance_events: List[Dict[str, Any]] = []
        self.adaptive_state: Dict[str, Any] = {}
        self.last_save_error: Optional[str] = None
        self._load_from_storage()

    def _load_from_storage(self) -> None:
        """Restore persisted recipe-backed operators and their evidence metadata."""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
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

    def _save_to_storage(self) -> None:
        if not self.storage_path:
            return
        try:
            parent_dir = os.path.dirname(self.storage_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "repository": self.repository,
                        "cross_file_reuses": self.cross_file_reuses,
                        "provenance_events": self.provenance_events,
                        "adaptive_state": self.adaptive_state,
                    },
                    handle,
                    indent=2,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.storage_path)
            self.last_save_error = None
        except OSError as exc:
            self.last_save_error = str(exc)

    def register_promoted_primitive(
        self,
        name: str,
        op_func: Callable[[str, int], Tuple[str, str]],
        origin_target: str,
        cum_gain: float,
    ) -> None:
        if name in self.repository:
            return
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

    def record_cross_file_use(self, name: str, target_name: str, delta_phi: float) -> None:
        if name not in self.repository:
            return
        if target_name not in self.repository[name]["targets_reused_on"]:
            self.repository[name]["targets_reused_on"].append(target_name)
        self.cross_file_reuses.setdefault(name, [])
        if target_name not in self.cross_file_reuses[name]:
            self.cross_file_reuses[name].append(target_name)
        self.repository[name]["cumulative_delta_phi"] = round(
            self.repository[name]["cumulative_delta_phi"] + delta_phi,
            6,
        )
        self._record_event(
            "primitive_reused",
            name,
            target_name,
            delta_phi,
            self.repository[name].get("recipe", []),
        )
        self._save_to_storage()

    def _record_event(
        self,
        event_type: str,
        primitive: str,
        target: str,
        delta_phi: float,
        recipe: List[str],
    ) -> None:
        previous = (
            self.provenance_events[-1]["event_hash"]
            if self.provenance_events
            else "GENESIS"
        )
        payload = {
            "sequence": len(self.provenance_events) + 1,
            "event_type": event_type,
            "primitive": primitive,
            "target": target,
            "delta_phi": round(float(delta_phi), 6),
            "recipe": list(recipe),
            "previous_hash": previous,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payload["event_hash"] = hashlib.sha256(encoded).hexdigest()
        self.provenance_events.append(payload)

    def save_adaptive_state(self, state: Dict[str, Any]) -> None:
        self.adaptive_state = dict(state)
        self._save_to_storage()

    def get_adaptive_state(self) -> Dict[str, Any]:
        return dict(self.adaptive_state)

    def get_all_transfer_primitives(
        self,
    ) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
        return list(self.primitive_functions.items())

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_repository_primitives": len(self.repository),
            "primitives_detail": self.repository,
            "cross_file_reuse_counts": {
                key: len(values) for key, values in self.cross_file_reuses.items()
            },
            "provenance_event_count": len(self.provenance_events),
            "provenance_head": (
                self.provenance_events[-1]["event_hash"]
                if self.provenance_events
                else None
            ),
            "adaptive_state_persisted": bool(self.adaptive_state),
            "last_save_error": self.last_save_error,
        }
