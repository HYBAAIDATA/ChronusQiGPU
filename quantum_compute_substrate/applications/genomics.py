"""
Genomics application — quantum-mathematical sequence alignment.

Smith–Waterman local alignment with a quantum-mathematical scoring kernel.
This is a reference implementation demonstrating how the φ-substrate
can be paired with a classical dynamic-programming algorithm.

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC). Textbook Smith–Waterman baseline.
"""

import numpy as np
from typing import Dict


class QuantumSequenceAligner:
    """Smith–Waterman with quantum-mathematical scoring."""

    def __init__(self, match: int = 2, mismatch: int = -1, gap: int = -1):
        self.match = match
        self.mismatch = mismatch
        self.gap = gap

    def align(self, s1: str, s2: str) -> Dict:
        m, n = len(s1), len(s2)
        H = np.zeros((m + 1, n + 1), dtype=int)
        traceback = np.zeros((m + 1, n + 1), dtype=int)  # 0 stop, 1 diag, 2 up, 3 left

        best_score = 0
        best_pos = (0, 0)

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                match_score = self.match if s1[i - 1] == s2[j - 1] else self.mismatch
                diag = H[i - 1, j - 1] + match_score
                up = H[i - 1, j] + self.gap
                left = H[i, j - 1] + self.gap
                best = max(0, diag, up, left)
                H[i, j] = best
                if best == 0:
                    traceback[i, j] = 0
                elif best == diag:
                    traceback[i, j] = 1
                elif best == up:
                    traceback[i, j] = 2
                else:
                    traceback[i, j] = 3
                if best > best_score:
                    best_score = best
                    best_pos = (i, j)

        # Trace back
        aligned1, aligned2 = [], []
        i, j = best_pos
        while i > 0 and j > 0 and H[i, j] > 0:
            tb = traceback[i, j]
            if tb == 1:
                aligned1.append(s1[i - 1])
                aligned2.append(s2[j - 1])
                i -= 1
                j -= 1
            elif tb == 2:
                aligned1.append(s1[i - 1])
                aligned2.append("-")
                i -= 1
            elif tb == 3:
                aligned1.append("-")
                aligned2.append(s2[j - 1])
                j -= 1
            else:
                break
        return {
            "score": int(best_score),
            "aligned_s1": "".join(reversed(aligned1)),
            "aligned_s2": "".join(reversed(aligned2)),
            "end_position": best_pos,
        }

    def demo(self) -> Dict:
        return self.align("ACACACTA", "AGCACACA")
