"""Exact graph-network observables, local maps and redundant-bond removal."""

from itertools import product
from math import prod

from .cyclotomic import Q8, ZERO8
from .exact_linalg import cr_factor
from .graph_network import ExactGraphNetwork, GraphSite


def _indices(shape):
    return product(*(range(d) for d in shape))


def _value(site, physical, indices):
    offset = physical
    for index, dim in zip(indices, site.dimensions):
        offset = offset * dim + index
    return site.data[offset]


def _network(source, sites):
    result = ExactGraphNetwork(sites, topology="tree" if source.topology == "tree" else "graph")
    result.topology = source.topology
    return result


def local_map(network, name, matrix, *, max_elements=65536, max_scalar_products=1000000):
    site = network._sites[name]
    if not matrix or any(len(row) != site.physical_dimension for row in matrix):
        raise ValueError("local map shape must match physical dimension")
    if any(not isinstance(v, Q8) for row in matrix for v in row):
        raise TypeError("local map requires Q8 entries")
    size = prod(site.dimensions)
    if (
        size * len(matrix) > max_elements
        or size * len(matrix) * site.physical_dimension > max_scalar_products
    ):
        raise MemoryError("local map exceeds declared budget")
    data = tuple(
        sum((matrix[p][q] * _value(site, q, index) for q in range(site.physical_dimension)), ZERO8)
        for p in range(len(matrix))
        for index in _indices(site.dimensions)
    )
    sites = dict(network._sites)
    sites[name] = GraphSite(len(matrix), site.bonds, site.dimensions, data)
    return _network(network, sites)


def overlap(bra, ket, *, max_elements=65536, max_scalar_products=1000000):
    if set(bra._sites) != set(ket._sites):
        raise ValueError("overlap requires identical physical site labels")
    sites, work = {}, 0
    for name, a in bra._sites.items():
        b = ket._sites[name]
        if a.physical_dimension != b.physical_dimension:
            raise ValueError("overlap physical dimensions differ")
        dimensions = a.dimensions + b.dimensions
        size = prod(dimensions)
        work += size * a.physical_dimension
        if size > max_elements or work > max_scalar_products:
            raise MemoryError("overlap local contraction exceeds declared budget")
        data = tuple(
            sum(
                (
                    _value(a, p, ix).conjugate() * _value(b, p, jx)
                    for p in range(a.physical_dimension)
                ),
                ZERO8,
            )
            for ix in _indices(a.dimensions)
            for jx in _indices(b.dimensions)
        )
        sites[name] = GraphSite(
            1,
            tuple("bra:" + x for x in a.bonds) + tuple("ket:" + x for x in b.bonds),
            dimensions,
            data,
        )
    if work == max_scalar_products and len(sites) > 1:
        raise MemoryError("overlap exhausted scalar product budget")
    result = ExactGraphNetwork(sites).amplitude(
        dict.fromkeys(sites, 0),
        max_elements=max_elements,
        max_scalar_products=max(1, max_scalar_products - work),
    )
    return result.amplitude


def compress_bond(network, bond, *, max_elements=65536, max_scalar_products=1000000):
    """Factor one site's unfolding A=C F and absorb F into its neighbour.

    Removes only exact linear dependence. Rank zero retains a single zero leg.
    No global Schmidt-minimality is asserted for graphs containing cycles.
    """
    names = sorted(name for name, site in network._sites.items() if bond in site.bonds)
    if len(names) != 2:
        raise ValueError("bond must join two sites")
    left, right = (network._sites[n] for n in names)
    la, ra = left.bonds.index(bond), right.bonds.index(bond)
    old = left.dimensions[la]
    other_dims = left.dimensions[:la] + left.dimensions[la + 1 :]
    rows = left.physical_dimension * prod(other_dims)
    if rows * old > max_elements or rows * old * old > max_scalar_products:
        raise MemoryError("rank factorization exceeds declared budget")
    row_indices = [
        (p, index) for p in range(left.physical_dimension) for index in _indices(other_dims)
    ]
    matrix = [
        [_value(left, p, index[:la] + (k,) + index[la:]) for k in range(old)]
        for p, index in row_indices
    ]
    c, f, pivots = cr_factor(matrix)
    rank = len(pivots)
    if not rank:
        c, f = [[ZERO8] for _ in matrix], [[ZERO8] * old]
    dimension = max(1, rank)
    new_dims = left.dimensions[:la] + (dimension,) + left.dimensions[la + 1 :]
    lookup = {key: i for i, key in enumerate(row_indices)}
    left_data = tuple(
        c[lookup[p, index[:la] + index[la + 1 :]]][index[la]]
        for p in range(left.physical_dimension)
        for index in _indices(new_dims)
    )
    right_dims = right.dimensions[:ra] + (dimension,) + right.dimensions[ra + 1 :]
    right_size = right.physical_dimension * prod(right_dims)
    if right_size > max_elements or rows * old * old + right_size * old > max_scalar_products:
        raise MemoryError("absorbed bond exceeds declared budget")
    right_data = tuple(
        sum(
            (
                f[index[ra]][k] * _value(right, p, index[:ra] + (k,) + index[ra + 1 :])
                for k in range(old)
            ),
            ZERO8,
        )
        for p in range(right.physical_dimension)
        for index in _indices(right_dims)
    )
    sites = dict(network._sites)
    sites[names[0]] = GraphSite(left.physical_dimension, left.bonds, new_dims, left_data)
    sites[names[1]] = GraphSite(right.physical_dimension, right.bonds, right_dims, right_data)
    return _network(network, sites), {
        "bond": bond,
        "old_dimension": old,
        "new_dimension": dimension,
        "exact_rank": rank,
        "discarded_weight": 0,
    }


def serialize(network):
    return {
        name: {
            "physical_dimension": s.physical_dimension,
            "bonds": list(s.bonds),
            "dimensions": list(s.dimensions),
            "data": [list(q.key()) for q in s.data],
        }
        for name, s in sorted(network._sites.items())
    }
