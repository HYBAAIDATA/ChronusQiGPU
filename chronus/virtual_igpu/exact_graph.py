"""JSON admission and replay for Kellogg's exact PEPS/TTN contractions."""

from __future__ import annotations

from typing import Any, Mapping


def execute_exact_graph(value: Mapping[str, Any]) -> dict[str, Any]:
    from kellogg.cyclotomic import Q8
    from kellogg.graph_network import ExactGraphNetwork, GraphSite

    if not {"sites", "physical", "topology"} <= set(value) or set(value) - {
        "sites",
        "physical",
        "topology",
        "rows",
        "cols",
        "max_elements",
        "max_scalar_products",
    }:
        raise ValueError("exact_graph requires sites, physical and topology with declared budgets")
    raw = value["sites"]
    if not isinstance(raw, dict) or not 1 <= len(raw) <= 64:
        raise ValueError("exact_graph requires 1..64 sites")
    sites, count = {}, 0
    for name, site in raw.items():
        if not isinstance(site, dict) or set(site) != {
            "physical_dimension",
            "bonds",
            "dimensions",
            "data",
        }:
            raise ValueError("site requires physical_dimension, bonds, dimensions and data")
        if (
            not isinstance(site["bonds"], list)
            or not isinstance(site["dimensions"], list)
            or len(site["bonds"]) > 8
        ):
            raise ValueError("site requires lists with at most eight virtual bonds")
        data = site["data"]
        if not isinstance(data, list):
            raise ValueError("site data must be a list")
        count += len(data)
        if count > 65536:
            raise ValueError("site data exceeds 65536 element input budget")
        if any(
            not isinstance(q, list)
            or len(q) != 5
            or any(type(c) is not int or c.bit_length() > 256 for c in q)
            or q[4] == 0
            for q in data
        ):
            raise ValueError(
                "Q8 values require five bounded integer coordinates and nonzero denominator"
            )
        sites[name] = GraphSite(
            site["physical_dimension"],
            tuple(site["bonds"]),
            tuple(site["dimensions"]),
            tuple(Q8(*q) for q in data),
        )
    topology = value["topology"]
    if topology == "peps":
        network = ExactGraphNetwork.peps(value.get("rows"), value.get("cols"), sites)
    else:
        if "rows" in value or "cols" in value:
            raise ValueError("rows/cols require PEPS topology")
        network = ExactGraphNetwork(sites, topology=topology)
    budgets = {}
    for name, maximum in (("max_elements", 65536), ("max_scalar_products", 1000000)):
        limit = value.get(name, maximum)
        if type(limit) is not int or not 1 <= limit <= maximum:
            raise ValueError(f"{name} must be in 1..{maximum}")
        budgets[name] = limit
    if not isinstance(value["physical"], dict):
        raise ValueError("physical indices must be a mapping")
    result = network.amplitude(value["physical"], **budgets)
    return {
        "amplitude_q8": list(result.amplitude.key()),
        "certificate": result.certificate.to_dict(),
        "peak_elements": result.peak_elements,
        "scalar_products": result.scalar_products,
        "arithmetic": "exact",
        "semantic_authority": "kellogg",
    }


def verify_exact_graph(value: Mapping[str, Any], output: Mapping[str, Any]) -> list[str]:
    return (
        []
        if output == execute_exact_graph(value)
        else ["exact Kellogg graph contraction replay mismatch"]
    )
