"""JSON admission and replay for Kellogg's exact PEPS/TTN contractions."""

from __future__ import annotations

from typing import Any, Mapping


def execute_exact_graph(value: Mapping[str, Any]) -> dict[str, Any]:
    from kellogg.cyclotomic import Q8
    from kellogg.graph_network import ExactGraphNetwork, GraphSite

    operation = value.get("op", "amplitude")
    fields = {
        "amplitude": {"physical"},
        "norm": set(),
        "compress_bond": {"bond"},
        "local_map": {"site", "matrix"},
        "expectation": {"site", "matrix"},
    }
    if not isinstance(operation, str) or operation not in fields:
        raise ValueError("unknown exact graph operation")
    required = {"sites", "topology"} | fields[operation]
    optional = {"rows", "cols", "max_elements", "max_scalar_products", "op"}
    if not required <= set(value) or set(value) - required - optional:
        raise ValueError("exact_graph fields must match the declared operation")
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
    operation = value.get("op", "amplitude")
    if operation != "amplitude":
        from kellogg.graph_operations import overlap, local_map, compress_bond, serialize
        from kellogg.certificate import certify, cex_digest

        parameters = {"op": operation}
        if operation == "norm":
            output = {"norm_squared_q8": list(overlap(network, network, **budgets).key())}
        elif operation == "compress_bond":
            reduced, evidence = compress_bond(network, value.get("bond"), **budgets)
            output = {"sites": serialize(reduced), "compression": evidence}
            parameters["bond"] = value.get("bond")
        elif operation in ("local_map", "expectation"):
            raw_matrix = value.get("matrix")
            if not isinstance(raw_matrix, list) or not 1 <= len(raw_matrix) <= 256:
                raise ValueError("bounded Q8 matrix required")
            if any(not isinstance(row, list) or not 1 <= len(row) <= 256 for row in raw_matrix):
                raise ValueError("bounded matrix rows required")
            if any(
                not isinstance(q, list)
                or len(q) != 5
                or any(type(c) is not int or c.bit_length() > 256 for c in q)
                or q[4] == 0
                for row in raw_matrix
                for q in row
            ):
                raise ValueError("matrix entries require bounded Q8 coordinates")
            mapped = local_map(
                network, value.get("site"), [[Q8(*q) for q in row] for row in raw_matrix], **budgets
            )
            if operation == "expectation":
                from math import prod

                site = network._sites[value["site"]]
                map_work = prod(site.dimensions) * len(raw_matrix) * site.physical_dimension
                if map_work >= budgets["max_scalar_products"]:
                    raise MemoryError("expectation exhausted scalar product budget")
                budgets["max_scalar_products"] -= map_work
            output = (
                {"sites": serialize(mapped)}
                if operation == "local_map"
                else {"expectation_q8": list(overlap(network, mapped, **budgets).key())}
            )
            parameters.update(site=value.get("site"), matrix=raw_matrix)
        else:
            raise ValueError("unknown exact graph operation")
        certificate = certify(
            operation,
            "Q(zeta8)",
            "kellogg.exact_graph/v1",
            cex_digest(value),
            cex_digest(output),
            parameters=parameters,
            invariants={"discarded_weight": 0},
        )
        return {
            **output,
            "certificate": certificate.to_dict(),
            "arithmetic": "exact",
            "semantic_authority": "kellogg",
        }
    if not isinstance(value.get("physical"), dict):
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
