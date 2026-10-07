import pathlib
groups = {
    "engine": ["chronus/engine.py", "chronus/v33/engine.py"],
    "client": ["chronus/client.py", "chronus/virtual_igpu/client.py"],
    "runtime": ["chronus/runtime.py", "chronus/virtual_igpu/runtime.py", "chronus/mla1517/runtime.py"],
    "conformance": ["chronus/conformance.py", "chronus/paradigm/conformance.py"],
    "telemetry": ["chronus/telemetry.py", "chronus/mla1517/telemetry.py"],
    "report": ["chronus/report.py", "chronus/v33/academic/report.py", "chronus/v33/memory/report.py", "chronus/v33/theory/report.py"],
    "evidence": ["chronus/measurement/store/evidence.py", "chronus/virtual_igpu/evidence.py"],
    "memory": ["chronus/measurement/topology/memory.py", "chronus/virtual_igpu/memory.py"],
    "scale": ["chronus/mla1517/scale.py", "chronus/seam/scale.py"],
    "store": ["chronus/mla1517/store.py", "chronus/seam/store.py"],
    "workflow": ["chronus/mla1517/mining/workflow.py", "chronus/seam/workflow.py"],
    "run": ["chronus/measurement/run.py", "chronus/seam/run.py"],
    "query": ["chronus/measurement/store/query.py", "chronus/mla1517/query.py"],
    "compute": ["chronus/measurement/roofline/compute.py", "chronus/measurement/topology/compute.py"],
    "thermal": ["chronus/measurement/efficiency/thermal.py", "chronus/v33/environment/thermal.py"],
    "execution": ["chronus/measurement/system/execution.py", "chronus/mla1517/mining/execution.py"],
    "coordinator": ["chronus/mla1517/mining/coordinator.py", "chronus/mla1517_platform/python/coordinator.py"],
}
for stem, paths in groups.items():
    print(f"===== [{stem}] =====")
    for rel in paths:
        p = pathlib.Path(rel)
        if not p.is_file():
            print(f"  MISSING: {rel}")
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"  --- {rel} ({len(lines)} lines)")
        for i, l in enumerate(lines[:12], 1):
            print(f"      {i:3d}: {l[:120]}")
    print()
