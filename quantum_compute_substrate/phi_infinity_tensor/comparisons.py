"""Honest comparisons of the tensor to known quantities."""
from __future__ import annotations
import math
from typing import Dict, Any
from .tensor import HYBAQuantumTensorXInfinity

# Known quantities (order-of-magnitude, log10):
#   Atoms in observable universe:   ~ 80
#   Cells in universe (biology):    ~ 40  (loose)
#   Neurons in human brain:         ~ 11
#   Grains of sand on Earth:        ~ 19
#   Seconds since Big Bang:         ~ 17.6
#   Planck volumes in universe:     ~ 185
#   Chess games:                    ~ 120
#   Go positions:                   ~ 170
#   Global data storage 2025 (bytes): ~ 23 (100 ZB)
#   Landauer computations at 3K universe energy: ~ 92


def compare_to_universe(T: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    log_elements = T.log10_elements()
    return {
        "log10_tensor_elements": log_elements,
        "log10_atoms_in_universe": 80.0,
        "log10_planck_volumes": 185.0,
        "log10_neurons_in_brain": 11.0,
        "log10_seconds_since_big_bang": 17.6,
        "exceeds_neurons_in_brain": log_elements > 11.0,
        "exceeds_seconds_since_big_bang": log_elements > 17.6,
        "exceeds_atoms_in_universe": log_elements > 80.0,   # False for phi^37
        "exceeds_planck_volumes": log_elements > 185.0,      # False
        "note": ("At phi^37 the tensor has ~10^46 elements. This exceeds "
                 "neurons, seconds since the Big Bang, and cells in the universe, "
                 "but is far less than atoms in the observable universe (~10^80). "
                 "For > 10^80 elements you need scaling_exp > ~63 (phi^63 ~ 10^13 per axis)."),
    }


def compare_to_storage(T: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    global_storage_bytes = 100 * (10 ** 21)  # 100 ZB
    tensor_materialized = T.memory_bytes_if_materialized()
    tensor_actual = T.memory_bytes_actual()
    return {
        "log10_global_storage_bytes": math.log10(global_storage_bytes),
        "log10_materialized_tensor_bytes": math.log10(tensor_materialized),
        "log10_substrate_tensor_bytes": math.log10(tensor_actual),
        "materialization_infeasible": tensor_materialized > global_storage_bytes,
        # 1 PB (data-center scale)
        "substrate_representation_fits_in_ram": tensor_actual < 10 ** 15,
        "substrate_dramatically_smaller_than_materialised":
            math.log10(tensor_actual) < math.log10(tensor_materialized) - 20,
        "note": ("Materialization is physically impossible. The MPS-network representation "
                 "is small enough to hold in system memory while preserving structure."),
    }


def compare_to_computational_limits(T: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    log_elements = T.log10_elements()
    return {
        "log10_tensor_elements": log_elements,
        "log10_bremermann_universe_ops_per_second": 103.0,
        "log10_landauer_universe_ops_total": 92.0,
        "materialisation_ops_below_landauer": log_elements < 92.0,
        "note": ("A single pass over the tensor requires ~10^46 operations. "
                 "That is below the Landauer bound for total universe computation (~10^92) "
                 "but well above any practical machine. The substrate never does a full pass; "
                 "it computes on the MPS."),
    }


def honest_size_context(T: HYBAQuantumTensorXInfinity) -> Dict[str, Any]:
    log_e = T.log10_elements()
    beats = []
    losing = []
    for name, log10 in [
        ("neurons in a human brain", 11.0),
        ("grains of sand on Earth", 19.0),
        ("seconds since Big Bang", 17.6),
        ("cells in the observable universe", 40.0),
        ("proteins by 35-mer combinatorics", 45.5),
        ("atoms in observable universe", 80.0),
        ("chess games", 120.0),
        ("Go game positions", 170.0),
        ("Planck volumes in observable universe", 185.0),
    ]:
        (beats if log_e > log10 else losing).append({"quantity": name, "log10": log10})
    return {
        "log10_tensor_elements": log_e,
        "tensor_exceeds": beats,
        "tensor_below": losing,
    }
