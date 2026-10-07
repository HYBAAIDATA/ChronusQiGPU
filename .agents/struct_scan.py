import pathlib
def show(title, path):
    p = pathlib.Path(path)
    print(f"=== {title}: {path} ===")
    print(f"  exists={p.exists()} is_dir={p.is_dir() if p.exists() else '-'}")
    if p.is_dir():
        kids = sorted(p.iterdir())
        for k in kids:
            if "__pycache__" in str(k) or ".pytest_cache" in str(k):
                continue
            tag = "DIR " if k.is_dir() else "file"
            print(f"    {tag} {k.name}")
    print()
show("spec dir", "chronus/spec")
show("kernels", "chronus/kernels")
show("deploy", "chronus/deploy")
show("paradigm", "chronus/paradigm")
show("seam (top)", "chronus/seam")
show("measurement (top)", "chronus/measurement")
show("mla1517 (top)", "chronus/mla1517")
show("mla1517_platform", "chronus/mla1517_platform")
show("mla1517_platform/python", "chronus/mla1517_platform/python")
show("v33 (top)", "chronus/v33")
show("virtual_igpu", "chronus/virtual_igpu")
show("chronos facade", "chronos")
