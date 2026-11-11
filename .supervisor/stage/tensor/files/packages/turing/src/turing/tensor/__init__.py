"""Exact tensor networks: dense tensors, CR factorisation, tensor trains and matrix product states.

Every entry is an exact element of a field (:data:`QQ` or :func:`cyclotomic`),
every factorisation is exact, every bond dimension is the exact rank it
represents, and nothing is rounded, truncated or compressed lossily. Where an
exact representation would exceed an explicit bound (:data:`MAX_DENSE_ENTRIES`
for dense tensors, ``max_bond`` for matrix product states) the operation is
refused with ``ValueError`` instead.

* :mod:`.field` - the field protocol, :data:`QQ` and :func:`cyclotomic`
* :mod:`.dense` - :class:`ExactTensor`
* :mod:`.linalg` - :func:`rref`, :func:`rank`, :func:`cr_factorization`
* :mod:`.train` - :class:`TensorTrain`
* :mod:`.mps` - :class:`ExactMPS`, :class:`ExactAmplitude`
* :mod:`.circuit` - :func:`evaluate_circuit`

See ``packages/turing/docs/TENSOR.md`` for guarantees, costs and limits.
"""

from .circuit import evaluate_circuit
from .dense import MAX_DENSE_ENTRIES, ExactTensor
from .field import QQ, CyclotomicNumberField, Field, RationalField, cyclotomic
from .linalg import CRFactorization, cr_factorization, matmul, rank, rref
from .mps import DEFAULT_MAX_BOND, GATE_NAMES, ExactAmplitude, ExactMPS
from .train import TensorTrain

__all__ = [
    "CRFactorization",
    "CyclotomicNumberField",
    "DEFAULT_MAX_BOND",
    "ExactAmplitude",
    "ExactMPS",
    "ExactTensor",
    "Field",
    "GATE_NAMES",
    "MAX_DENSE_ENTRIES",
    "QQ",
    "RationalField",
    "TensorTrain",
    "cr_factorization",
    "cyclotomic",
    "evaluate_circuit",
    "matmul",
    "rank",
    "rref",
]
