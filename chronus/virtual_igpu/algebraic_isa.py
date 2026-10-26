"""Bounded exact software ISA for Z[phi] and GF(256) dot-product arrays."""

from hashlib import sha256
import json
from kellogg.scales import Zphi


def _admit(value):
    if (
        set(value) != {"schema", "field", "left", "right"}
        or value["schema"] != "chronus.algebraic-isa/v1"
    ):
        raise ValueError("algebraic ISA requires schema, field, left and right")
    field, left, right = value["field"], value["left"], value["right"]
    if field not in ("zphi", "gf256"):
        raise ValueError("unknown algebraic ISA field")
    for matrix in (left, right):
        if not isinstance(matrix, list) or not 1 <= len(matrix) <= 64:
            raise ValueError("matrix requires 1..64 rows")
        if any(not isinstance(row, list) or not 1 <= len(row) <= 64 for row in matrix):
            raise ValueError("matrix requires 1..64 columns")
        if len({len(row) for row in matrix}) != 1:
            raise ValueError("matrix must be rectangular")
        for row in matrix:
            for v in row:
                if field == "zphi":
                    if (
                        not isinstance(v, list)
                        or len(v) != 2
                        or any(type(c) is not int or c.bit_length() > 256 for c in v)
                    ):
                        raise ValueError("Zphi operands require two bounded exact integers")
                elif type(v) is not int or not 0 <= v <= 255:
                    raise ValueError("GF256 operands require bytes")
    if len(left[0]) != len(right):
        raise ValueError("dot-product inner dimensions differ")
    return field, left, right


def _gf_mul(a, b):
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = (a << 1) ^ (0x11B if a & 128 else 0)
        b >>= 1
    return result


def _result(field, rows, products):
    digest = sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    return {
        "rows": rows,
        "digest": digest,
        "field": field,
        "scalar_products": products,
        "arithmetic": "exact",
        "overflow": "unbounded_integer" if field == "zphi" else "polynomial_mod_0x11b",
    }


def execute_algebraic(value):
    field, left, right = _admit(value)
    rows = []
    for row in left:
        output = []
        for col in zip(*right):
            if field == "zphi":
                total = sum((Zphi(*a) * Zphi(*b) for a, b in zip(row, col)), Zphi())
                output.append([total.a, total.b])
            else:
                total = 0
                for a, b in zip(row, col):
                    total ^= _gf_mul(a, b)
                output.append(total)
        rows.append(output)
    return _result(field, rows, len(left) * len(right) * len(right[0]))


def verify_algebraic(value, output):
    field, left, right = _admit(value)
    rows = []
    for row in left:
        result_row = []
        for col in zip(*right):
            if field == "zphi":
                # Multiply formal polynomials, then reduce x^2-x-1.
                coeff = [0, 0, 0]
                for a, b in zip(row, col):
                    for i in range(2):
                        for j in range(2):
                            coeff[i + j] += a[i] * b[j]
                result_row.append([coeff[0] + coeff[2], coeff[1] + coeff[2]])
            else:
                polynomial = 0
                for a, b in zip(row, col):
                    for bit in range(8):
                        if (b >> bit) & 1:
                            polynomial ^= a << bit
                while polynomial.bit_length() > 8:
                    polynomial ^= 0x11B << (polynomial.bit_length() - 9)
                result_row.append(polynomial)
        rows.append(result_row)
    expected = _result(field, rows, len(left) * len(right) * len(right[0]))
    return [] if output == expected else ["algebraic ISA polynomial oracle mismatch"]
