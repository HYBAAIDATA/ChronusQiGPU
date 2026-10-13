# Elevation moves status

## Move 1 — Dispatch tile ladder
DONE. `_plan_matmul` starts at the largest power-of-two tile that fits the device limits.

## Move 2 — Rung-selected memory envelope
OPEN. `chronus/seam/scale.py:snap_to_ladder` returns the nearest ladder stop inside a bound. It is not wired into the dispatch planner. Test before implementing.

## Move 3 — phi_vqc decorative pocket
RESOLVED. The Clifford skeleton is labelled capability-demonstration only. It does not enter the ranking forward path.

## Move 4 — Physical accelerator lane certification
EXTERNAL. Requires a real device and a device-bound AcceleratorCertification artifact. Native mode remains complete without it.

## Move 5 — Independent verification of the exact quantum lane
EXTERNAL. Requires a subsequent independent team review. This work does not self-issue that verification.

## TOE lane selection
SCAFFOLDED. `chronus/mla1517/mining/toe_lane_decision.py` constructs the domain-neutral Problem for lane-order selection. Reward is bound only from real pool responses. Not yet wired into the production call graph. The rule-based chooser remains the fallback.

theorem_proven: False
