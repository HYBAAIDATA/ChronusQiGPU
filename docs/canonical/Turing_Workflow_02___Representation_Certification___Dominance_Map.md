# Turing Workflow 02 — Representation Certification & Dominance Map

## Purpose

Certify each Turing state/circuit representation and determine where it dominates without assuming a universal winner.

## Dimensions

Logical qubits × depth × circuit class × non-Clifford content × entanglement structure × precision/exactness × memory budget × backend.

## Candidate representations

Statevector · stabilizer · tensor-network/MPS · symbolic/algebraic · OVID-transformed/folded checkpoint forms · future owner-approved representations.

## Certification

For each representation: valid domain; exactness/approximation; conversion in/out; measurement agreement; error bounds; memory; runtime; failure limits; unsupported-domain fail-closed behavior.

## Dominance map

Record the best evidenced representation by workload region with uncertainty and crossover points. Preserve losing regions.

## Automatic selector gate

A planner may automatically select representation only after differential testing against this map demonstrates that selection cannot silently weaken semantics, precision, or supported domain. Material promotion requires owner approval.