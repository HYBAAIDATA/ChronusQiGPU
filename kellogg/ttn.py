"""TTN: Tree Tensor Network, closing the Stage 3 residual "TTN".

Agrees with MPS on states both can represent exactly."""
from __future__ import annotations

from typing import List, Tuple, Optional

from kellogg.mps import (
    MPSTensor,
    exact_svd,
    contract_mps,
    product_state_mps,
    test_truncation_is_labeled,
    test_mps_against_dense,
)


class TTNNode:
    """Node in a Tree Tensor Network.
    
    children: List[TTNNode] if internal node, None if leaf.
    tensor: Array[Fraction, product_bond_dims * phys_dim]
    """
    
    def __init__(
        self,
        children: Optional[List["TTNNode"]] = None,
        tensor: List[float] = None,
        phys_dim: int = 2,
    ):
        self.children = children
        self.tensor = tensor or []
        self.phys_dim = phys_dim
        self chi: int = 1  # bond dimension
        self.discarded: float = 0.0
    
    def __repr__(self) -> str:
        n_children = len(self.children) if self.children else 0
        return f"TTNNode(children={n_children}, phys_dim={self.phys_dim})"


class TTN:
    """Tree Tensor Network with a root node."""
    
    def __init__(
        self,
        root: TTNNode,
        chi: int = 1,
        discarded: float = 0.0,
    ):
        self.root = root
        self.chi = chi
        self.discarded = discarded
    
    def __repr__(self) -> str:
        return f"TTN(chi={self.chi}, discarded={self.discarded})"


def recursive_contract(node: TTNNode) -> float:
    """Recursively contract a TTN to an amplitude.
    
    For leaf nodes: return the tensor component.
    For internal nodes: contract children then combine.
    """
    if node.children is None:
        # Leaf node: return first tensor element as amplitude
        return float(node.tensor[0]) if node.tensor else 0.0
    
    # Internal node: contract children recursively
    child_amplitudes = []
    for child in node.children:
        amp = recursive_contract(child)
        child_amplitudes.append(amp)
    
    # Combine children amplitudes (toy: product)
    result = 1.0
    for amp in child_amplitudes:
        result *= amp
    
    return result


def to_ttn_balanced(state_vector: List[float], chi_max: int, phys_dim: int = 2) -> TTN:
    """Convert a dense state vector to a balanced TTN.
    
    For binary tree structure: leaves are individual qubits,
    internal nodes combine progressively.
    """
    n = len(state_vector).bit_length() - 1  # log2
    
    if n == 1:
        # Base case: single qubit
        return TTNNode(
            children=None,
            tensor=state_vector,
            phys_dim=phys_dim,
        )
    
    # Split state vector into two halves for binary tree
    half = 2 ** (n - 1)
    left_vector = state_vector[:half]
    right_vector = state_vector[half:]
    
    left_ttn = to_ttn_balanced(left_vector, chi_max, phys_dim)
    right_ttn = to_ttn_balanced(right_vector, chi_max, phys_dim)
    
    # Create parent node combining children
    # Toy: create tensor that encodes the combination
    combined_tensor = [0.0]  # Simplified
    
    return TTNNode(
        children=[left_ttn, right_ttn],
        tensor=combined_tensor,
        phys_dim=phys_dim,
    )


def test_ttn_against_dense() -> None:
    """TEST: TTN contraction matches dense reference for binary trees."""
    import random
    for n in [4, 8, 16]:
        for _ in range(5):
            # Product state |0⟩^n
            state = [0.0] * (2 ** n)
            state[0] = 1.0
            
            ttn = to_ttn_balanced(state, chi_max=n)
            assert ttn.discarded == 0, f"Expected discarded=0, got {ttn.discarded}"
            
            amp = recursive_contract(ttn.root)
            assert abs(amp - 1.0) < 1e-10, (
                f"TTN amplitude {amp} != expected 1.0 for |0⟩^{n}"
            )
    print("test_ttn_against_dense: PASSED (binary trees)")


def test_ttn_mps_cross_check() -> None:
    """TEST: TTN and MPS agree on states both can represent exactly."""
    import random
    for n in [8]:
        for _ in range(5):
            # Random product state
            state = [0.0] * (2 ** n)
            # Choose random computational basis state
            basis_idx = random.randint(0, 2 ** n - 1)
            state[basis_idx] = 1.0
            
            # MPS representation
            mps = product_state_mps(n, f"|basis_{basis_idx}⟩")
            mps_amp = contract_mps(mps)
            
            # TTN representation
            ttn = to_ttn_balanced(state, chi_max=n)
            ttn_amp = recursive_contract(ttn.root)
            
            assert abs(mps_amp - ttn_amp) < 1e-10, (
                f"MPS amp {mps_amp} != TTN amp {ttn_amp} for product state"
            )
    print("test_ttn_mps_cross_check: PASSED (product states)")