"""Wire-integrated generation cycle. Every leader->specialist->leader
hop — contract sync, dispatch, patch return, fitness report — is a
folded QT frame round-tripping through encode_frame/decode_frame.
T=6 tasks, A=4 agents -> 4^6 = 4096 amplitudes.

    python loop.py        (from this directory)
"""

from __future__ import annotations

import numpy as np

from team.agents import Specialist, breed
from team.contracts import ContractRegistry
from team.fitness import FitnessEvaluator
from team.tool import QuantumTool
from team.wire import (ContractSyncMessage, FitnessReportMessage,
                       MessageKind, PatchMessage, TaskMessage,
                       decode_frame, encode_frame)

SPECIALTIES = ["api", "connectivity", "tests"]


def run(generations: int = 4, T: int = 6, seed: int = 7):
    rng = np.random.default_rng(seed)
    tool = QuantumTool()

    # --- bootstrap: freeze contracts, sync to team over the wire ---------
    reg = ContractRegistry()
    reg.freeze("core_api", {"type": "object",
                            "required": ["endpoints", "errors"],
                            "properties": {"endpoints": {"type": "array"},
                                           "errors": {"type": "array"}}})
    reg.freeze("wire_format", {"type": "object",
                               "required": ["magic", "header_bytes"],
                               "properties": {"magic": {"type": "string"},
                                              "header_bytes":
                                                  {"type": "integer"}}})
    kind, sync = decode_frame(encode_frame(ContractSyncMessage(reg.export())))
    assert kind is MessageKind.CONTRACT_SYNC

    fit = FitnessEvaluator(reg)
    team = [Specialist(f"{SPECIALTIES[i % 3]}-agent-{i}", SPECIALTIES[i % 3],
                       float(rng.uniform(0.5, 0.95))) for i in range(4)]
    tasks = [TaskMessage(task_id=i, generation=0, specialty=SPECIALTIES[i % 3],
                         module=f"module_{i}",
                         description=f"implement module_{i}",
                         required_digests=tuple(sorted(reg.live_digests())))
             for i in range(T)]
    base_cost = np.array([[0.1 + (1 - a.skill)
                           + (0.5 if a.specialty != t.specialty else 0.0)
                           for a in team] for t in tasks])
    coupled = [(i, i + 1) for i in range(T - 1)]   # adjacent modules: never co-locate
    cost = base_cost.copy()

    patches: list = []
    log = []
    for gen in range(generations):
        alloc = tool.solve_allocation(cost=cost, coupled=coupled, load_limit=2)

        if gen == 0:                               # fresh dispatch, all via wire
            patches = []
            for t, task in enumerate(tasks):
                kind, decoded = decode_frame(encode_frame(task))
                assert kind is MessageKind.TASK
                agent = team[alloc["assignments"][t]]
                patch = agent.execute(decoded, reg, rng)
                kind, patch = decode_frame(encode_frame(patch))
                assert kind is MessageKind.PATCH
                patches.append(patch)

        scores = []                                # fitness reports, via wire
        for p in patches:
            report = fit.evaluate(p)
            kind, back = decode_frame(encode_frame(report))
            assert kind is MessageKind.FITNESS_REPORT
            scores.append(back.raw_score)

        sel = tool.select_generation(scores, k=max(2, len(patches) // 2), rng=rng)
        parents = [patches[i] for i in sel["parent_indices"]]
        children = [breed(parents[i], parents[-(i + 1)])
                    for i in range(len(parents) // 2)]
        patches = parents + children               # lineage persists

        per_agent = {}                             # empirical skill re-estimator
        for p, s in zip(patches, scores):
            per_agent.setdefault(alloc["assignments"][p.task_id], []).append(s)
        for a_i, vals in per_agent.items():
            cost[:, a_i] = base_cost[:, a_i] + (1.0 - float(np.mean(vals)))

        log.append({"gen": gen, "best": max(scores),
                    "rounds": sel["rounds"],
                    "mass": round(sel["born_mass_on_topk"], 3)})
        print(f"gen {gen}: best={max(scores):.2f} rounds={sel['rounds']} "
              f"mass={sel['born_mass_on_topk']:.3f}")
    return log


if __name__ == "__main__":
    run()
