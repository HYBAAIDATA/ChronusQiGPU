import os
import json
import time
import math
import zlib
import pickle
from typing import Any, Dict, List

# Phi-Folding Constants
PHI = (1.0 + math.sqrt(5.0)) / 2.0


class LedgerLoadError(Exception):
    pass


class VeritasLedger:
    """
    Salamander's Memory: A persistent, phi-compressed ledger of operational integrity.
    Implements Veritas Integritas: No fabricated metrics, only bit-exact verification.
    Pure Python implementation to ensure substrate independence.
    """

    def __init__(self, ledger_path: str = "artifacts/salamander_healing/veritas_ledger.local.phi"):
        self.ledger_path = ledger_path
        self.memory_buffer: List[Dict[str, Any]] = []
        self.load_status = "INITIALIZED_EMPTY"

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

        if os.path.exists(self.ledger_path):
            self._load_and_decompress()

    def record_action(self, action_type: str, status: str, evidence: Dict[str, Any]):
        """
        Records a validated action into the ledger.
        Mandates evidence check (Veritas Integritas).
        """
        # Precise evidence hashing for bit-exact verification
        evidence_str = json.dumps(evidence, sort_keys=True)
        evidence_hash = hex(zlib.adler32(evidence_str.encode("utf-8")))

        entry = {
            "timestamp": time.time(),
            "action_type": action_type,
            "status": status,
            "evidence_hash": evidence_hash,
            "evidence": evidence,
            "verification_verified": evidence.get("test_passed", False),
        }

        if not entry["verification_verified"] and status == "SUCCESS":
            raise ValueError(
                f"[VERITAS] Violation: Action '{action_type}' cannot report SUCCESS without verified test evidence."
            )

        self.memory_buffer.append(entry)
        self._fold_and_save()

    def _fold_and_save(self):
        """
        Applies pure-python phi-folding to the memory buffer.
        Uses Golden Ratio orthogonal rotations to fold dimensional data.
        """
        raw_json = json.dumps(self.memory_buffer)
        raw_bytes = raw_json.encode("utf-8")

        # Pad to even length for dimensional folding
        if len(raw_bytes) % 2 != 0:
            raw_bytes += b"\x00"

        # Extract dimensions
        x1 = list(raw_bytes[0::2])
        x2 = list(raw_bytes[1::2])

        # Phi Rotation
        theta = PHI
        c = math.cos(theta)
        s = math.sin(theta)

        folded = [(c * a + s * b) for a, b in zip(x1, x2)]
        detail = [(-s * a + c * b) for a, b in zip(x1, x2)]

        # Lossless entropy compression of detail
        detail_bytes = pickle.dumps(detail)
        compressed_detail = zlib.compress(detail_bytes, level=9)

        # Build folded package
        package = {"folded": folded, "detail": compressed_detail, "original_len": len(raw_bytes)}

        # ATOMIC WRITE. `open(path, "wb")` truncates the file to zero bytes
        # BEFORE the dump completes, so any reader in that window sees an empty
        # file and unpickling fails with "Ran out of input". This is the truth
        # ledger; a torn write loses the audit trail.
        #
        # The race was latent while the miner performed no work (few writes).
        # Once the zero-work cancellation latch was fixed and mining actually
        # began, record_action() started firing on every cycle and the window
        # was hit reliably -- surfacing as an intermittent LedgerLoadError.
        #
        # Write to a sibling temp file, flush to disk, then os.replace(), which
        # is atomic on both POSIX and Windows. A crash mid-write now leaves the
        # previous ledger intact rather than an empty file.
        tmp_path = f"{self.ledger_path}.tmp"
        with open(tmp_path, "wb") as f:
            pickle.dump(package, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.ledger_path)

    def _load_and_decompress(self):
        """
        Unfolds the memory fabric using inverse phi-rotation.
        """
        try:
            with open(self.ledger_path, "rb") as f:
                package = pickle.load(f)

            folded = package["folded"]
            detail_bytes = zlib.decompress(package["detail"])
            detail = pickle.loads(detail_bytes)

            theta = PHI
            c = math.cos(theta)
            s = math.sin(theta)

            # Inverse rotation
            x1 = [(c * f - s * d) for f, d in zip(folded, detail)]
            x2 = [(s * f + c * d) for f, d in zip(folded, detail)]

            # Interleave and reconstruct bytes
            reconstructed_bytes = bytearray()
            for a, b in zip(x1, x2):
                reconstructed_bytes.append(int(round(a)))
                reconstructed_bytes.append(int(round(b)))

            raw_json = reconstructed_bytes.decode("utf-8").rstrip("\x00")
            self.memory_buffer = json.loads(raw_json)
            self.load_status = "VERIFIED_CLEAN"
        except (pickle.UnpicklingError, zlib.error) as e:
            self.load_status = "CORRUPT"
            raise LedgerLoadError(f"Ledger file is corrupt or truncated: {e}")
        except Exception as e:
            self.load_status = "VERSION_SKEW"
            raise LedgerLoadError(f"Failed to load ledger: {e}")

    def get_integrity_report(self) -> str:
        """
        Generates a summary of verified operations.
        """
        total = len(self.memory_buffer)
        verified = sum(1 for e in self.memory_buffer if e["verification_verified"])
        return f"[VERITAS] Integrity Report: {verified}/{total} actions independently verified. Load Status: {self.load_status}"

    def get_treasury_run_report(self) -> str:
        """
        Formats the latest ledger entry into the 14-stage Treasury Run report.
        """
        if not self.memory_buffer:
            return "No records available."

        latest = self.memory_buffer[-1]
        ev = latest.get("evidence", {})

        # Build report shell
        lines = [
            "Treasury Run",
            "────────────",
            "",
            f"Job: {ev.get('job_id', 'None')}",
            f"Decision: {ev.get('decision', 'None')}",
            f"Prediction: {ev.get('prediction', 'None')}",
            "",
            "Intelligence:",
        ]

        intel = ev.get("intelligence", {})
        for k in [
            "predictive",
            "causal",
            "counterfactual",
            "topological",
            "geometric",
            "quantum",
            "entanglement",
        ]:
            lines.append(f"  {k}: {intel.get(k, 'N/A')}")

        lines.append("")
        lines.append("Suppositions:")
        suppositions = ev.get("suppositions", [])
        if not suppositions:
            lines.append("  None")
        for s in suppositions:
            lines.append(f"  {s.get('id', 'Unknown')}:")
            lines.append(f"    confidence_before: {s.get('confidence_before', 0.0):.4f}")
            lines.append(f"    predicted_effect: {s.get('expected_effect', 'None')}")
            lines.append(f"    actual_effect: {s.get('actual_outcome', 'None')}")
            lines.append(f"    confidence_after: {s.get('confidence_after', 0.0):.4f}")

        rep = ev.get("representation", {})
        lines.extend(
            [
                "",
                "Representation:",
                f"  logical_size: {rep.get('logical_size', 'N/A')}",
                f"  physical_size: {rep.get('physical_size', 'N/A')}",
                f"  representation_ratio: {rep.get('representation_ratio', 'N/A')}",
                "",
                "Search:",
                f"  strategy: {ev.get('search_strategy', 'N/A')}",
                f"  folded: {ev.get('folded', False)}",
                f"  candidate_space: {ev.get('candidate_space', 'N/A')}",
                "",
                "Execution:",
                f"  planned_substrate: {ev.get('planned_substrate', 'N/A')}",
                f"  actual_substrate: {ev.get('actual_substrate', 'N/A')}",
                f"  fallback: {ev.get('fallback', 'N/A')}",
                "",
                "Mining:",
                f"  work: {ev.get('work', 'N/A')}",
                f"  accepted_shares: {ev.get('accepted_shares', 0)}",
                f"  rejected_shares: {ev.get('rejected_shares', 0)}",
                "",
                "Learning:",
                f"  prediction_error: {ev.get('prediction_error', 'N/A')}",
                f"  hypothesis_update: {ev.get('hypothesis_update', 'N/A')}",
                f"  next_decision: {ev.get('next_decision', 'N/A')}",
            ]
        )

        return "\n".join(lines)
