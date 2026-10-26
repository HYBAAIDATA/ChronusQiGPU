"""PEPS/TTN contractions checked against independent bond enumeration."""

from itertools import product

import pytest

from kellogg.cyclotomic import Q8, ZERO8
from kellogg.graph_network import ExactGraphNetwork, GraphSite


def brute_force(sites, physical):
    dims = {bond: dim for s in sites.values() for bond, dim in zip(s.bonds, s.dimensions)}
    bonds = sorted(dims)
    total = ZERO8
    for indices in product(*(range(dims[b]) for b in bonds)):
        assignment = dict(zip(bonds, indices))
        term = Q8(1)
        for name, s in sites.items():
            offset = physical[name]
            for b, d in zip(s.bonds, s.dimensions):
                offset = offset * d + assignment[b]
            term = term * s.data[offset]
        total = total + term
    return total


def rectangle():
    legs = {
        "0,0": ("top", "left"),
        "0,1": ("top", "right"),
        "1,0": ("left", "bottom"),
        "1,1": ("right", "bottom"),
    }
    return {
        name: GraphSite(2, bonds, (2, 2), tuple(Q8(i - 3, i % 2, 1, -1, 3) for i in range(8)))
        for name, bonds in legs.items()
    }


def test_peps_all_amplitudes_equal_full_bond_sum_and_certificates_bind_inputs():
    sites = rectangle()
    network = ExactGraphNetwork.peps(2, 2, sites)
    certificates = set()
    for bits in product(range(2), repeat=4):
        physical = dict(zip(sorted(sites), bits))
        result = network.amplitude(physical)
        assert result.amplitude == brute_force(sites, physical)
        assert result.certificate.invariants["discarded_weight"] == 0
        certificates.add(result.certificate.digest)
    assert len(certificates) == 16


def test_tree_exact_branch_contraction():
    sites = {"root": GraphSite(2, ("a", "b", "c"), (2, 2, 2), tuple(Q8(i) for i in range(16)))}
    for b in ("a", "b", "c"):
        sites[b] = GraphSite(2, (b,), (2,), tuple(Q8(i, 1, 0, 0, 2) for i in range(4)))
    network = ExactGraphNetwork(sites, topology="tree")
    physical = dict.fromkeys(sites, 1)
    assert network.amplitude(physical).amplitude == brute_force(sites, physical)
    with pytest.raises(MemoryError, match="budget"):
        network.amplitude(physical, max_elements=1)
    with pytest.raises(MemoryError, match="budget"):
        network.amplitude(physical, max_scalar_products=1)


def test_topology_shape_domain_and_exactness_refusals():
    with pytest.raises(ValueError, match="acyclic"):
        ExactGraphNetwork(rectangle(), topology="tree")
    with pytest.raises(ValueError, match="rectangle"):
        ExactGraphNetwork.peps(1, 4, rectangle())
    with pytest.raises(ValueError, match="rectangle"):
        ExactGraphNetwork.peps(10**100, 10**100, rectangle())
    with pytest.raises(ValueError, match="two sites"):
        ExactGraphNetwork({"x": GraphSite(1, ("dangling",), (1,), (Q8(1),))})
    with pytest.raises(ValueError, match="Q8"):
        GraphSite(1, (), (), (0.5,))
    network = ExactGraphNetwork({"x": GraphSite(2, (), (), (Q8(0), Q8(1)))}, topology="tree")
    assert network.amplitude({"x": 0}).amplitude == ZERO8
    with pytest.raises(ValueError, match="physical index"):
        network.amplitude({"x": True})
