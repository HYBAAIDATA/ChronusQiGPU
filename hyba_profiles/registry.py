from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    dependencies: tuple[str, ...] = ()
    research_gated: bool = False


MODULE_REGISTRY = {
    "core": ModuleSpec("core"),
    "mla1517": ModuleSpec("mla1517", ("core",)),
    "primedb": ModuleSpec("primedb", ("core", "mla1517")),
    "al_haras": ModuleSpec("al_haras", ("core",)),
    "proof_service": ModuleSpec("proof_service", ("core", "primedb")),
    "observe": ModuleSpec("observe", ("core",)),
    "flow": ModuleSpec("flow", ("core", "primedb")),
    "ontology": ModuleSpec("ontology", ("core", "primedb")),
    "quality": ModuleSpec("quality", ("core", "observe")),
    "model_gateway": ModuleSpec("model_gateway", ("al_haras", "observe")),
    "agent_fabric": ModuleSpec("agent_fabric", ("al_haras", "quality")),
    "evidence": ModuleSpec("evidence", ("proof_service", "observe")),
    "share": ModuleSpec("share", ("al_haras", "primedb")),
    "federate": ModuleSpec("federate", ("al_haras", "share")),
    "vault": ModuleSpec("vault", ("primedb", "evidence")),
    "edge": ModuleSpec("edge", ("al_haras", "vault")),
    "studio": ModuleSpec("studio", ("al_haras",)),
    "functions": ModuleSpec("functions", ("al_haras",)),
    "insight": ModuleSpec("insight", ("quality", "observe")),
    "deploy": ModuleSpec("deploy", ("al_haras", "evidence")),
    "metering": ModuleSpec("metering", ("observe", "primedb")),
    "privacy_compute": ModuleSpec("privacy_compute", ("al_haras",), True),
    "quantum_access": ModuleSpec("quantum_access", ("mla1517", "proof_service"), True),
    "autonomous_ops": ModuleSpec("autonomous_ops", ("agent_fabric", "observe"), True),
    "energy": ModuleSpec("energy", ("observe",), True),
}


def dependency_closure(requested: tuple[str, ...]) -> tuple[str, ...]:
    missing = sorted(set(requested) - MODULE_REGISTRY.keys())
    if missing:
        raise ValueError(f"unknown modules: {','.join(missing)}")
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise ValueError(f"module dependency cycle at {name}")
        if name in visited:
            return
        visiting.add(name)
        for dep in MODULE_REGISTRY[name].dependencies:
            visit(dep)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in requested:
        visit(name)
    return tuple(ordered)
