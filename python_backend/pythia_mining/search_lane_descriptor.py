DEFAULT_STRUCTURE_PRIOR = "truncated_icosahedron_32f"
FLAT_STRUCTURE_PRIOR = "flat"


def build_lane_descriptor(
    ordering=None, structure_prior=None, budget=None, prepass_limit=None, execution=None
):
    prior = structure_prior or DEFAULT_STRUCTURE_PRIOR
    d = {
        "requested_ordering": ordering,
        "structure_prior": prior,
        "status": "pending",
        "mode": "pending",
        "ordering_heuristic": "not_dispatched",
        "execution_substrate": "not_dispatched",
        "execution_substrates": [],
        "budget": budget,
        "prepass_limit": prepass_limit,
        "quantum": None,
        "formalism": None,
        "simulator_iterations": 0,
        "degraded": False,
        "degraded_reason": None,
    }
    if execution is not None:
        d["status"] = "executed"
        d["execution_substrate"] = execution.get("execution_substrate", "unknown")
        d["execution_substrates"] = execution.get("execution_substrates", [])
        d["ordering_heuristic"] = execution.get("ordering_heuristic", "unknown")
        d["simulator_iterations"] = execution.get("simulator_iterations", 0)
        if execution.get("degraded_reason"):
            d["degraded"] = True
            d["degraded_reason"] = execution["degraded_reason"]
        simulated = bool(execution.get("simulator_iterations", 0) > 0)
        if simulated:
            d["mode"] = (
                "structured_grover" if prior == DEFAULT_STRUCTURE_PRIOR else "unstructured_grover"
            )
            d["quantum"] = {
                "execution_type": "classical_simulation",
                "physical_execution": False,
                "simulator_iterations": execution.get("simulator_iterations", 0),
            }
            d["formalism"] = "grover"
        else:
            d["mode"] = "exhaustive_scan"
            d["quantum"] = None
    return d


def legacy_search_label(descriptor=None):
    if not descriptor:
        return None
    mode = descriptor.get("mode")
    if mode == "structured_grover":
        return "grover_lucas"
    if mode == "unstructured_grover":
        return "grover_flat"
    order = descriptor.get("ordering_heuristic")
    if order and order not in ("not_dispatched", "unknown"):
        return order
    return None


def format_lane_label(descriptor=None):
    if not descriptor:
        return "not_dispatched"
    return (
        f"execution_substrate={descriptor.get('execution_substrate', 'not_dispatched')}|"
        f"ordering_heuristic={descriptor.get('ordering_heuristic', 'not_dispatched')}"
    )
